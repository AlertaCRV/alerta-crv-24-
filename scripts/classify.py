import re
import unicodedata
from collections import Counter

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
    "Miranda": ["francisco de miranda", "generalisimo francisco de miranda", "plaza miranda"],
}

# Un keyword suelto de tipo no siempre significa que el articulo trata
# realmente de ese tipo de evento. Caso real: "Activan cerco epidemiologico
# especial en zonas afectadas por sismos en La Guaira" -- la palabra
# "sismos" aparece, pero el tema es una medida de salud publica, no un
# sismo ocurriendo ahora. Si la ventana tiene contexto de esta lista Y no
# tiene ninguna palabra de _EVIDENCIA_FUERTE_POR_TIPO para ese tipo, se
# descarta el tipo para esa mencion puntual.
_CONTEXTO_CONFLICTIVO_POR_TIPO = {
    "sismo": ["cerco epidemiologico", "epidemiologico", "brote de enfermedad",
              "atenciones medicas", "salud integral comunitaria"],
    # Caso anticipado (27-07-2026): demolicion controlada de estructuras
    # danadas por el terremoto en Playa Grande/Caraballeda, La Guaira --
    # coberturas de esa demolicion programada mencionaran "colapso"/
    # "estructuras afectadas"/"explosivos" en el sentido de la demolicion en
    # si, no de una emergencia nueva.
    "colapso_estructural": ["demolicion controlada", "demolicion programada",
                             "derribo controlado", "derribo programado",
                             "voladura controlada"],
    "explosion": ["demolicion controlada", "demolicion programada",
                  "derribo controlado", "derribo programado",
                  "voladura controlada", "detonacion controlada",
                  "detonacion programada"],
}
_EVIDENCIA_FUERTE_POR_TIPO = {
    "sismo": ["magnitud", "richter", "funvisis", "epicentro", "se sintio",
              "sacudio", "remezon"],
    "colapso_estructural": ["colapso repentino", "colapso inesperado",
                            "heridos", "fallecidos", "atrapados bajo"],
    "explosion": ["explosion accidental", "explosion no controlada",
                  "explosion prematura", "heridos", "fallecidos"],
}

# Fallas de electricidad/agua rara vez usan las palabras clave de severidad
# ("heridos", "danos severos"...) aunque describan una situacion real de
# precaucion -- una duracion prolongada mencionada explicitamente (p.ej. "94
# horas sin luz") es evidencia suficiente de BAJO ("situacion de precaucion,
# sin danos significativos reportados") en vez de quedar SIN CLASIFICAR por
# falta de palabras clave. El umbral es distinto por tipo: los cortes de
# electricidad son criticos mucho antes que los de agua (que en Venezuela
# suelen durar dias o semanas sin ser una emergencia en si misma), asi que
# el margen para agua es de 7 dias o mas, no de 1 dia como electricidad.
_UMBRAL_DIAS_DURACION_BAJO_POR_TIPO = {
    "infraestructura_electrica": 1,
    "infraestructura_agua": 7,
}
_DURACION_HORAS_RE = re.compile(r"\b(\d{1,3})\s*horas?\b", re.IGNORECASE)
_DURACION_DIAS_RE = re.compile(r"\b(\d{1,2})\s*d[ií]as?\b", re.IGNORECASE)


def _severidad_por_duracion(texto_norm, tipos):
    for tipo in tipos:
        umbral_dias = _UMBRAL_DIAS_DURACION_BAJO_POR_TIPO.get(tipo)
        if umbral_dias is None:
            continue
        umbral_horas = umbral_dias * 24
        if any(int(m.group(1)) >= umbral_horas for m in _DURACION_HORAS_RE.finditer(texto_norm)):
            return "bajo"
        if any(int(m.group(1)) >= umbral_dias for m in _DURACION_DIAS_RE.finditer(texto_norm)):
            return "bajo"
    return None


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


_NEGACION_RE = re.compile(
    r"\b(sin|no|ningun|ninguna|ningunos|ningunas)\b(\s+\w+){0,2}\s*$"
)
_VENTANA_NEGACION_CHARS = 25


def _contiene_palabra_clave_no_negada(texto_norm, palabra):
    """Como _contiene_palabra_clave, pero descarta la coincidencia si esta
    negada a pocas palabras de distancia (p.ej. 'sin afectados que lamentar',
    'no se reportan heridos') -- evita que una palabra clave de severidad
    dispare un nivel que el propio texto esta descartando."""
    patron = r"\b" + re.escape(_normalizar(palabra)) + r"\b"
    for m in re.finditer(patron, texto_norm):
        inicio_ventana = max(0, m.start() - _VENTANA_NEGACION_CHARS)
        fragmento_previo = texto_norm[inicio_ventana:m.start()]
        if not _NEGACION_RE.search(fragmento_previo):
            return True
    return False


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


_LONGITUD_MINIMA_NOMBRE_DIRECTO = 5

_conteo_global_municipios = None
_conteo_global_parroquias = None


def _variantes_nombre(entrada):
    """Una entrada de ubicaciones_detalle.json es normalmente un string (el
    nombre oficial), pero puede ser una lista [nombre_oficial, alias...]
    cuando el nombre oficial casi nunca se usa en la prensa (p.ej. el
    municipio "Bolivariano Guaicaipuro" se menciona casi siempre solo como
    "Guaicaipuro"). Devuelve (nombre_canonico, [todas las variantes que
    deben reconocerse, incluido el propio canonico])."""
    if isinstance(entrada, list):
        return entrada[0], entrada
    return entrada, [entrada]


def _conteos_globales_ubicaciones():
    """Cuenta en cuantos estados distintos aparece cada variante de nombre de
    municipio o parroquia. Muchos son nombres de proceres/estados reusados en
    todo el pais (Sucre, Bolivar, Miranda, Libertador, Independencia...) -- si
    un nombre asi se buscara suelto en el texto, generaria falsos positivos
    constantes. Solo las variantes que aparecen en un unico estado son lo
    bastante especificas para usarse como coincidencia directa."""
    global _conteo_global_municipios, _conteo_global_parroquias
    if _conteo_global_municipios is None:
        cm, cp = Counter(), Counter()
        for detalle in load_ubicaciones_detalle().values():
            for m in detalle.get("municipios", []):
                for variante in _variantes_nombre(m)[1]:
                    cm[_normalizar(variante)] += 1
            for p in detalle.get("parroquias", []):
                for variante in _variantes_nombre(p)[1]:
                    cp[_normalizar(variante)] += 1
        _conteo_global_municipios, _conteo_global_parroquias = cm, cp
    return _conteo_global_municipios, _conteo_global_parroquias


def _buscar_nombre_directo(texto_norm, candidatos, conteo_global, nombre_estado_norm):
    """Busca el nombre de un municipio/parroquia mencionado directamente en
    el texto (p.ej. 'inundacion en Petare'), sin exigir que venga precedido
    de la palabra 'municipio'/'parroquia'. Descarta nombres muy cortos,
    repetidos en varios estados, o identicos al propio nombre del estado
    (comun en capitales de estado, p.ej. el municipio y la parroquia
    "Barinas" del estado Barinas) -- una mencion del estado en el texto no
    es evidencia de que se trate especificamente de ese municipio/parroquia
    homonimo, y confundirlos asigno una vez el municipio "Barinas" a un
    deslizamiento que en realidad ocurrio en el municipio Bolivar."""
    for normalizado, original in candidatos.items():
        if len(normalizado) < _LONGITUD_MINIMA_NOMBRE_DIRECTO:
            continue
        if conteo_global[normalizado] > 1:
            continue
        if normalizado == nombre_estado_norm:
            continue
        if _contiene_palabra_clave(texto_norm, normalizado):
            return original
    return None


def detectar_municipio_parroquia(texto, estado):
    if not estado:
        return None, None

    detalle = load_ubicaciones_detalle().get(estado, {})
    municipios = {
        _normalizar(variante): canonico
        for m in detalle.get("municipios", [])
        for canonico, variantes in [_variantes_nombre(m)]
        for variante in variantes
    }
    parroquias = {
        _normalizar(variante): canonico
        for p in detalle.get("parroquias", [])
        for canonico, variantes in [_variantes_nombre(p)]
        for variante in variantes
    }

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

    if municipio_encontrado is None or parroquia_encontrada is None:
        texto_norm = _normalizar(texto)
        nombre_estado_norm = _normalizar(estado)
        conteo_municipios, conteo_parroquias = _conteos_globales_ubicaciones()
        if municipio_encontrado is None:
            municipio_encontrado = _buscar_nombre_directo(texto_norm, municipios, conteo_municipios, nombre_estado_norm)
        if parroquia_encontrada is None:
            parroquia_encontrada = _buscar_nombre_directo(texto_norm, parroquias, conteo_parroquias, nombre_estado_norm)

    return municipio_encontrado, parroquia_encontrada


def _tipo_con_contexto_conflictivo(texto_norm, tipo):
    """True si el tipo detectado probablemente sea un falso positivo: la
    ventana tiene contexto que sugiere que el tema real es otro (ver
    _CONTEXTO_CONFLICTIVO_POR_TIPO) y no hay evidencia mas fuerte de que si
    se trata de ese tipo de evento (ver _EVIDENCIA_FUERTE_POR_TIPO)."""
    conflictivo = _CONTEXTO_CONFLICTIVO_POR_TIPO.get(tipo)
    if not conflictivo or not any(_contiene_palabra_clave(texto_norm, f) for f in conflictivo):
        return False
    fuerte = _EVIDENCIA_FUERTE_POR_TIPO.get(tipo, [])
    return not any(_contiene_palabra_clave(texto_norm, f) for f in fuerte)


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
                if not _tipo_con_contexto_conflictivo(fuente_norm, tipo):
                    tipos_encontrados.append(tipo)
                break
    return tipos_encontrados


def detectar_severidad(texto, tipos=None):
    texto_norm = _normalizar(texto)
    orden = ["critico", "alto", "medio", "bajo"]
    severidades = load_keywords()["severidad"]
    for nivel in orden:
        for palabra in severidades.get(nivel, []):
            if _contiene_palabra_clave_no_negada(texto_norm, palabra):
                return nivel
    if tipos:
        por_duracion = _severidad_por_duracion(texto_norm, tipos)
        if por_duracion:
            return por_duracion
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
    item["severidad"] = detectar_severidad(item["texto"], item["tipos"])
    item["municipio"], item["parroquia"] = detectar_municipio_parroquia(item["texto"], item["ubicacion"])
    return item


def es_relevante(item):
    return bool(item["ubicacion"]) and bool(item["tipos"])
