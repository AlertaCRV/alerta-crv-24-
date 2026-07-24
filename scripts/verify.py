import difflib
import re

_AGENCIAS = ["efe", "afp", "reuters", "dpa", "ansa", "xinhua", "europa press", "sputnik"]
_AGENCIA_RE = re.compile(
    r"\b(?:con informaci[oó]n de|informaci[oó]n de|agencia|nota de|v[ií]a|seg[uú]n)\s+"
    r"(" + "|".join(_AGENCIAS) + r")\b"
    r"|\((" + "|".join(_AGENCIAS) + r")\)",
    re.IGNORECASE,
)

UMBRAL_SIMILITUD_TEXTO = 0.6


def _clave_cluster(item):
    tipo_principal = item["tipos"][0]
    return (tipo_principal, item["ubicacion"])


def _detectar_agencia(texto):
    """Devuelve el nombre de la agencia de noticias (EFE, AFP...) si el texto
    la cita explicitamente como fuente/creditos, o None."""
    m = _AGENCIA_RE.search(texto.lower())
    if not m:
        return None
    return (m.group(1) or m.group(2)).lower()


def _mismo_origen(a, b):
    """True si dos fuentes probablemente comparten el mismo origen (mismo
    cable de agencia, o texto casi identico republicado por otro medio) y no
    deberian contarse como confirmaciones independientes."""
    agencia_a = _detectar_agencia(a["texto"])
    agencia_b = _detectar_agencia(b["texto"])
    if agencia_a and agencia_b and agencia_a == agencia_b:
        return True
    similitud = difflib.SequenceMatcher(None, a["texto"].lower(), b["texto"].lower()).ratio()
    return similitud >= UMBRAL_SIMILITUD_TEXTO


def _agrupar_por_independencia(fuentes):
    """Agrupa fuentes de un mismo cluster que probablemente comparten el
    mismo origen (mismo cable de agencia, o texto casi identico republicado).
    Devuelve una lista de grupos (cada grupo es una lista de fuentes que
    comparten origen), ordenados por el peso de su miembro mas pesado,
    descendente. La verificacion de plausibilidad con IA (ver verify_ai.py)
    evalua un representante por grupo, no cada fuente individualmente."""
    grupos = []
    for f in fuentes:
        grupo_encontrado = next(
            (g for g in grupos if any(_mismo_origen(f, otro) for otro in g)), None
        )
        if grupo_encontrado is not None:
            grupo_encontrado.append(f)
        else:
            grupos.append([f])

    grupos.sort(key=lambda g: max(m["peso"] for m in g), reverse=True)
    return grupos


def agrupar_y_verificar(items):
    """Agrupa items relevantes por (tipo, ubicacion). El score, severidad y
    confirmacion final se calculan en verify_ai.py DESPUES de la
    verificacion de plausibilidad con IA, usando solo las fuentes que la IA
    considero vigentes -- por eso aqui solo se arma la agrupacion cruda."""
    clusters = {}
    for item in items:
        clave = _clave_cluster(item)
        clusters.setdefault(clave, []).append(item)

    eventos = []
    for (tipo, ubicacion), miembros in clusters.items():
        fuentes_unicas = {}
        for m in miembros:
            nombre = m["fuente_nombre"]
            if nombre not in fuentes_unicas or m["peso"] > fuentes_unicas[nombre]["peso"]:
                fuentes_unicas[nombre] = m

        municipio = next((m.get("municipio") for m in miembros if m.get("municipio")), None)
        parroquia = next((m.get("parroquia") for m in miembros if m.get("parroquia")), None)

        eventos.append({
            "tipo": tipo,
            "ubicacion": ubicacion,
            "municipio": municipio,
            "parroquia": parroquia,
            "grupos_fuentes": _agrupar_por_independencia(list(fuentes_unicas.values())),
        })

    return eventos
