import re

from config_loader import load_keywords, load_estados

_HASHTAG_RE = re.compile(r"#(\w+)", re.UNICODE)


def _normalizar(texto):
    return texto.lower()


def detectar_ubicacion(texto):
    """Solo reconoce ubicación si el texto trae un hashtag que coincida con un estado.
    Formato fijo requerido, ej: '#Zulia' o '#Miranda'."""
    estados = load_estados()
    hashtags = [h.lower() for h in _HASHTAG_RE.findall(texto)]
    if not hashtags:
        return None

    for nombre_estado, alias in estados.items():
        for tag in hashtags:
            if tag in alias or tag == nombre_estado.lower().replace(" ", ""):
                return nombre_estado
    return None


def detectar_tipo(texto):
    texto_norm = _normalizar(texto)
    tipos_encontrados = []
    for tipo, palabras in load_keywords()["tipos"].items():
        for palabra in palabras:
            if palabra in texto_norm:
                tipos_encontrados.append(tipo)
                break
    return tipos_encontrados


def detectar_severidad(texto):
    texto_norm = _normalizar(texto)
    orden = ["critico", "alto", "medio", "bajo"]
    severidades = load_keywords()["severidad"]
    for nivel in orden:
        for palabra in severidades.get(nivel, []):
            if palabra in texto_norm:
                return nivel
    return "sin_clasificar"


def clasificar_item(item):
    item["ubicacion"] = detectar_ubicacion(item["texto"])
    item["tipos"] = detectar_tipo(item["texto"])
    item["severidad"] = detectar_severidad(item["texto"])
    return item


def es_relevante(item):
    """Un item solo es candidato a emergencia si tiene ubicación (formato fijo) y al menos un tipo detectado."""
    return bool(item["ubicacion"]) and bool(item["tipos"])
