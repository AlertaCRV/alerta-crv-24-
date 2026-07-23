import re
import unicodedata

from config_loader import load_keywords, load_estados, load_ubicaciones_detalle

_HASHTAG_RE = re.compile(r"#(\w+)", re.UNICODE)
_MUNICIPIO_RE = re.compile(r"municipio\s+([A-ZÁÉÍÓÚÑ][\wÀ-ÿ' ]{2,40}?)(?=[.,;:\n]|$)", re.IGNORECASE)
_PARROQUIA_RE = re.compile(r"parroquia\s+([A-ZÁÉÍÓÚÑ][\wÀ-ÿ' ]{2,40}?)(?=[.,;:\n]|$)", re.IGNORECASE)

VENTANA_PROXIMIDAD_PALABRAS = 15

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
    return _normalizar(texto).split()


def detectar_ubicacion(texto):
    estados = load_estados()
    hashtags = [h.lower() for h in _HASHTAG_RE.findall(texto)]

    for nombre_estado, alias in estados.items():
        for tag in hashtags:
            if tag in alias or tag == nombre_estado.lower().replace(" ", ""):
                return nombre_estado

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

            if _hay_palabra_clave_cerca(tokens, candidato_norm, palabras_tipo):
                return nombre_estado

    return None


def _hay_palabra_clave_cerca(tokens, candidato_norm, palabras_tipo):
    candidato_tokens = candidato_norm.split()
    primera_palabra = candidato_tokens[0]

    posiciones = [i for i, t in enumerate(tokens) if t == primera_palabra]
    for pos in posiciones:
        inicio = max(0, pos - VENTANA_PROXIMIDAD_PALABRAS)
        fin = min(len(tokens), pos + VENTANA_PROXIMIDAD_PALABRAS)
        ventana = " ".join(tokens[inicio:fin])
        for palabra in palabras_tipo:
            if _normalizar(palabra) in ventana:
                return True
    return False


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


def detectar_tipo(texto):
    texto_norm = _normalizar(texto)
    tipos_encontrados = []
    for tipo, palabras in load_keywords()["tipos"].items():
        for palabra in palabras:
            if _normalizar(palabra) in texto_norm:
                tipos_encontrados.append(tipo)
                break
    return tipos_encontrados


def detectar_severidad(texto):
    texto_norm = _normalizar(texto)
    orden = ["critico", "alto", "medio", "bajo"]
    severidades = load_keywords()["severidad"]
    for nivel in orden:
        for palabra in severidades.get(nivel, []):
            if _normalizar(palabra) in texto_norm:
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

    item["ubicacion"] = detectar_ubicacion(item["texto"])
    item["tipos"] = detectar_tipo(item["texto"])
    item["severidad"] = detectar_severidad(item["texto"])
    item["municipio"], item["parroquia"] = detectar_municipio_parroquia(item["texto"], item["ubicacion"])
    return item


def es_relevante(item):
    return bool(item["ubicacion"]) and bool(item["tipos"])
