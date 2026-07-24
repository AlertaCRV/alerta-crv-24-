import difflib
import re
from datetime import datetime, timezone
from dateutil import parser as dateparser

from config_loader import load_settings

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
    """Agrupa fuentes de un mismo cluster que probablemente no son
    confirmaciones independientes entre si (mismo cable de agencia, o texto
    casi identico republicado). Devuelve una fuente representativa (la de
    mayor peso) por cada grupo, ordenadas por peso descendente."""
    grupos = []
    for f in fuentes:
        grupo_encontrado = next(
            (g for g in grupos if any(_mismo_origen(f, otro) for otro in g)), None
        )
        if grupo_encontrado is not None:
            grupo_encontrado.append(f)
        else:
            grupos.append([f])

    representantes = [max(g, key=lambda m: m["peso"]) for g in grupos]
    return sorted(representantes, key=lambda m: m["peso"], reverse=True)


def agrupar_y_verificar(items):
    settings = load_settings()["verificacion"]
    umbral = settings["umbral_confirmado"]

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

        # Fuentes que probablemente comparten el mismo origen (mismo cable de
        # agencia, o texto casi identico republicado) no cuentan cada una como
        # confirmacion independiente para el score/num_fuentes.
        fuentes_independientes = _agrupar_por_independencia(list(fuentes_unicas.values()))

        score = sum(f["peso"] for f in fuentes_independientes)
        severidades = [m["severidad"] for m in miembros if m["severidad"] != "sin_clasificar"]
        orden_severidad = ["critico", "alto", "medio", "bajo"]
        severidad_final = next((s for s in orden_severidad if s in severidades), "sin_clasificar")

        fecha_mas_reciente = max(miembros, key=lambda m: dateparser.isoparse(m["fecha"]))["fecha"]

        municipio = next((m.get("municipio") for m in miembros if m.get("municipio")), None)
        parroquia = next((m.get("parroquia") for m in miembros if m.get("parroquia")), None)

        texto_muestra = fuentes_independientes[0]["texto"]
        # Se manda a Groq el texto de las fuentes independientes del cluster
        # (no las que ya se agruparon por compartir origen): si una fuente
        # esta redactada de forma ambigua pero otras del mismo cluster dejan
        # claro que es, p.ej., una retrospectiva, la IA necesita ver el
        # conjunto para no aprobar el evento por error.
        textos_fuentes = [
            {"fuente": f["fuente_nombre"], "texto": f["texto"][:400]}
            for f in fuentes_independientes
        ]

        eventos.append({
            "tipo": tipo,
            "ubicacion": ubicacion,
            "municipio": municipio,
            "parroquia": parroquia,
            "texto_muestra": texto_muestra,
            "textos_fuentes": textos_fuentes,
            "severidad": severidad_final,
            "score": round(score, 2),
            "confirmado": score >= umbral,
            "num_fuentes": len(fuentes_independientes),
            "fuentes": [
                {"nombre": f["fuente_nombre"], "link": f["link"], "fecha": f["fecha"]}
                for f in fuentes_unicas.values()
            ],
            "fecha_evento": fecha_mas_reciente,
            "fecha_deteccion": datetime.now(timezone.utc).isoformat(),
        })

    return eventos
