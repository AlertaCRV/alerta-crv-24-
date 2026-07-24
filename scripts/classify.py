import re
import unicodedata

from config_loader import load_keywords, load_estados, load_ubicaciones_detalle

_HASHTAG_RE = re.compile(r"#(\w+)", re.UNICODE)
_MUNICIPIO_RE = re.compile(r"municipio\s+([A-ZÁÉÍÓÚÑ][\wÀ-ÿ' ]{2,40}?)(?=[.,;:\n]|$)", re.IGNORECASE)
_PARROQUIA_RE = re.compile(r"parroquia\s+([A-ZÁÉÍÓÚÑ][\wÀ-ÿ' ]{2,40}?)(?=[.,;:\n]|$)", re.IGNORECASE)

# Una oracion realista que describe el evento y luego da la jerarquia completa
# "parroquia X, municipio Y del estado Z" (a veces con nombres compuestos, p.ej.
# "parroquia J. Vidal Marcano") puede superar facilmente las 25-30 palabras.
VENTANA_PROXIMIDAD_PALABRAS = 35

LISTA_NEGRA_POR_ESTADO = {
    "Bolivar": ["simon bolivar", "plaza bolivar", "avenida bolivar", "aeropuerto", "moneda",
                "billete de", "banco central", "libertador simon bolivar"],
    "Sucre": ["antonio jose de sucre", "mariscal sucre", "moneda", "billete de"],
    "Miranda": ["francisco de miranda", "generalisimo miranda", "plaza miranda"],
}


def _normalizar(texto):
    texto = texto.strip().lower()
    return "".join(c for c in unicodedata.normalize("NFD", texto) if unicodedata.category(c) != "Mn")


def _tokens(texto):
    """Tokeniza por palabras, ignorando puntuacion pegada (p.ej. 'Miranda.'
    o 'Miranda,' deben dar el token 'miranda', no 'miranda.'/'miranda,')."""
    return re.findall(r"\w+", _normalizar(texto))


def _contiene_palabra_clave(texto_norm, palabra):
    """Busca `palabra` como palabra completa (no como substring de otra
    palabra, p.ej. 'alud' dentro de 'salud')."""
    patron = r"\b" + re.escape(_normalizar(palabra)) + r"\b"
    return re.search(patron, texto_norm) is not None


def detectar_ubicacion(texto):
    """Devuelve (nombre_estado, ventana_cercana) o (None, None).

    ventana_cercana es el fragmento de texto alrededor de la mención del
    estado que confirmó la ubicación; detectar_tipo() lo usa para no
    clasificar el tipo de emergencia a partir de palabras clave sueltas en
    otra parte del artículo. Es None cuando la ubicación viene de un hashtag
    (no hay una "mención en el texto" de la cual tomar una ventana).
    """
    estados = load_estados()
    hashtags = [h.lower() for h in _HASHTAG_RE.findall(texto)]

    for nombre_estado, alias in estados.items():
        for tag in hashtags:
            if tag in alias or tag == nombre_estado.lower().replace(" ", ""):
                return nombre_estado, None

    return _detectar_ubicacion_texto_plano(texto, estados)


def _detectar_ubicacion_texto_plano(texto, estados):
    texto_norm = _normalizar(texto)
    palabras_tipo = [p for lista in load_keywords()["tipos"].values() for p in lista]
    tokens = _tokens(texto)

    for nombre_estado, alias in estados.items():
        candidatos = set(alias) | {_normalizar(nombre_estado)}
        for candidato in candidatos:
            candidato_norm = _normalizar(candidato)
            patron = r"\b" + re.escape(candidato_norm) + r"\b"
            match = re.search(patron, texto_norm)
            if not match:
                continue

            lista_negra = LISTA_NEGRA_POR_ESTADO.get(nombre_estado, [])
            if any(frase in texto_norm for frase in lista_negra):
                continue

            ventana = _ventana_cerca(tokens, candidato_norm, palabras_tipo)
            if ventana:
                return nombre_estado, ventana

    return None, None


_CALIFICADORES_SUBESTATALES = {"municipio", "parroquia"}

# Secuencias de palabras que, justo antes de "Caracas", indican que se usa
# como referencia de sentido/direccion vial ("sentido Caracas", "rumbo a
# Caracas"), no como la ubicacion real del suceso -- muy comun en reportes
# de transito de cualquier estado, ya que "caracas" es alias de Distrito
# Capital.
_CALIFICADORES_DIRECCIONALES_CARACAS = [
    ("sentido",), ("via",), ("vía",), ("hacia",),
    ("rumbo", "a"), ("direccion", "a"), ("dirección", "a"),
]


def _es_mencion_subestatal(tokens, pos):
    """True si el token en `pos` esta precedido por 'municipio'/'parroquia',
    p.ej. 'municipio Sucre'. Varios municipios/parroquias de Venezuela
    comparten nombre con un estado distinto (Sucre, Miranda, Bolivar...),
    asi que esa mencion no debe contarse como evidencia de que el estado
    homonimo es la ubicacion del evento."""
    return pos > 0 and tokens[pos - 1] in _CALIFICADORES_SUBESTATALES


def _es_mencion_direccional(tokens, pos, candidato_tokens):
    """True si el token en `pos` es 'caracas' usado como referencia de
    sentido/direccion vial (ver _CALIFICADORES_DIRECCIONALES_CARACAS)."""
    if candidato_tokens != ["caracas"]:
        return False
    for calificador in _CALIFICADORES_DIRECCIONALES_CARACAS:
        n = len(calificador)
        if pos - n >= 0 and tuple(tokens[pos - n:pos]) == calificador:
            return True
    return False


def _ventana_cerca(tokens, candidato_norm, palabras_tipo):
    """Devuelve la ventana de texto alrededor de candidato_norm si contiene
    alguna palabra clave de tipo, o None si no hay ninguna cerca."""
    candidato_tokens = candidato_norm.split()
    primera_palabra = candidato_tokens[0]

    posiciones = [
        i for i, t in enumerate(tokens)
        if t == primera_palabra
        and not _es_mencion_subestatal(tokens, i)
        and not _es_mencion_direccional(tokens, i, candidato_tokens)
    ]
    for pos in posiciones:
        inicio = max(0, pos - VENTANA_PROXIMIDAD_PALABRAS)
        fin = min(len(tokens), pos + VENTANA_PROXIMIDAD_PALABRAS)
        ventana = " ".join(tokens[inicio:fin])
        for palabra in palabras_tipo:
            if _contiene_palabra_clave(ventana, palabra):
                return ventana
    return None


def detectar_municipio_parroquia(texto, estado):
    if not estado:
        return None, None

    detalle = load_ubicaciones_detalle().get(estado, {})
    municipios = {_normalizar(m): m for m in detalle.get("municipios", [])}
    parroquias = {_normalizar(p): p for p in detalle.get("parroquias", [])}

    municipio_encontrado = None
    parroquia_encontrada = None

    m = _MUNICIPIO_RE.search(texto)
    if m:
        candidato = _normalizar(m.group(1).strip())
        municipio_encontrado = municipios.get(candidato)

    p = _PARROQUIA_RE.search(texto)
    if p:
        candidato = _normalizar(p.group(1).strip())
        parroquia_encontrada = parroquias.get(candidato)

    return municipio_encontrado, parroquia_encontrada


def detectar_tipo(texto, ventana=None):
    """Detecta tipos de emergencia por palabra clave.

    Si se da `ventana` (el fragmento cercano a la ubicación detectada, ver
    detectar_ubicacion), la búsqueda se limita a ese fragmento en vez de
    todo el texto, para no tomar palabras clave de otra parte del artículo
    que no tiene relación con la ubicación detectada.
    """
    fuente_norm = ventana if ventana is not None else _normalizar(texto)
    tipos_encontrados = []
    for tipo, palabras in load_keywords()["tipos"].items():
        for palabra in palabras:
            if _contiene_palabra_clave(fuente_norm, palabra):
                tipos_encontrados.append(tipo)
                break
    return tipos_encontrados


def detectar_severidad(texto):
    texto_norm = _normalizar(texto)
    orden = ["critico", "alto", "medio", "bajo"]
    severidades = load_keywords()["severidad"]
    for nivel in orden:
        for palabra in severidades.get(nivel, []):
            if _contiene_palabra_clave(texto_norm, palabra):
                return nivel
    return "sin_clasificar"


def clasificar_item(item):
    pre = item.pop("_preclasificado", None)
    if pre:
        item["ubicacion"] = pre["ubicacion"]
        item["tipos"] = pre["tipos"]
        item["severidad"] = pre["severidad"]
        item["municipio"] = None
        item["parroquia"] = None
        return item

    item["ubicacion"], ventana = detectar_ubicacion(item["texto"])
    item["tipos"] = detectar_tipo(item["texto"], ventana)
    item["severidad"] = detectar_severidad(item["texto"])
    item["municipio"], item["parroquia"] = detectar_municipio_parroquia(item["texto"], item["ubicacion"])
    return item


def es_relevante(item):
    return bool(item["ubicacion"]) and bool(item["tipos"])
