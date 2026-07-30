import difflib
import re

from dateutil import parser as dateparser

_AGENCIAS = ["efe", "afp", "reuters", "dpa", "ansa", "xinhua", "europa press", "sputnik"]
_AGENCIA_RE = re.compile(
    r"\b(?:con informaci[oó]n de|informaci[oó]n de|agencia|nota de|v[ií]a|seg[uú]n)\s+"
    r"(" + "|".join(_AGENCIAS) + r")\b"
    r"|\((" + "|".join(_AGENCIAS) + r")\)",
    re.IGNORECASE,
)

UMBRAL_SIMILITUD_TEXTO = 0.6

_MAGNITUD_RE = re.compile(r"magnitud\s+(\d+[.,]\d+)", re.IGNORECASE)


def extraer_magnitud(texto):
    """Devuelve la magnitud (float, redondeada a 1 decimal) mencionada
    explicitamente en el texto (p.ej. "magnitud 3.1"), o None si no se
    menciona ninguna. Se usa exclusivamente para tipo=sismo: separar en
    clusters.py sismos distintos que caen en la misma ubicacion, y en
    verify_ai.py/state.py para correlacionar el mismo sismo sentido en
    ubicaciones distintas."""
    m = _MAGNITUD_RE.search(texto)
    if not m:
        return None
    try:
        return round(float(m.group(1).replace(",", ".")), 1)
    except ValueError:
        return None


def _separar_sismos_por_magnitud(miembros):
    """Si un cluster de tipo=sismo en una misma ubicacion tiene items que
    mencionan al menos 2 magnitudes distintas, los separa en sub-eventos por
    magnitud -- de lo contrario (una sola magnitud mencionada, o ninguna),
    los deja en un solo grupo, igual que antes. Sin esto, dos sismos reales
    distintos en el mismo estado el mismo dia se fusionaban en una sola
    alerta combinada (ver conversacion del 2026-07-25). Los items sin
    magnitud extraible se asignan al sub-evento cuyo miembro mas reciente
    este mas cerca en el tiempo."""
    con_magnitud = [(m, extraer_magnitud(m["texto"])) for m in miembros]
    magnitudes_distintas = {mag for _, mag in con_magnitud if mag is not None}

    if len(magnitudes_distintas) < 2:
        return [miembros]

    grupos_por_magnitud = {mag: [] for mag in magnitudes_distintas}
    sin_magnitud = []
    for m, mag in con_magnitud:
        if mag is not None:
            grupos_por_magnitud[mag].append(m)
        else:
            sin_magnitud.append(m)

    def _fecha_referencia(grupo):
        return max(dateparser.isoparse(m["fecha"]) for m in grupo)

    for m in sin_magnitud:
        fecha_m = dateparser.isoparse(m["fecha"])
        mag_mas_cercana = min(
            grupos_por_magnitud,
            key=lambda mag: abs((_fecha_referencia(grupos_por_magnitud[mag]) - fecha_m).total_seconds()),
        )
        grupos_por_magnitud[mag_mas_cercana].append(m)

    return list(grupos_por_magnitud.values())


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
        sub_clusters = _separar_sismos_por_magnitud(miembros) if tipo == "sismo" else [miembros]

        for sub_miembros in sub_clusters:
            fuentes_unicas = {}
            for m in sub_miembros:
                nombre = m["fuente_nombre"]
                if nombre not in fuentes_unicas or m["peso"] > fuentes_unicas[nombre]["peso"]:
                    fuentes_unicas[nombre] = m

            # Se prioriza el municipio/parroquia del miembro mas RECIENTE (no
            # el primero en aparecer, que dependia solo del orden de
            # recoleccion) -- si varias fuentes del mismo cluster mencionan
            # ubicaciones especificas distintas (caso real: dos reportes de
            # una filial sobre el mismo evento, uno diciendo "municipio
            # Colina" y una actualizacion posterior diciendo "municipio
            # Zamora"), el encabezado de la alerta ("Ubicacion") debe
            # coincidir con la fuente mas actual, no con una versión vieja --
            # lo mismo que ya hace el resumen consolidado en verify_ai.py.
            # Bug real encontrado (30-07-2026): elegir municipio y parroquia
            # cada uno por separado ("el valor no nulo mas reciente de cada
            # campo") podia emparejar un municipio de un miembro con la
            # parroquia de OTRO miembro mas viejo que en realidad pertenece a
            # un municipio distinto -- caso real: 3 reportes de la misma
            # filial, el mas reciente dice "municipio Zamora" (sin
            # parroquia), uno viejo dice "parroquia Las Calderas, municipio
            # Colina" -- el resultado combinado terminaba en "Municipio
            # Zamora, Parroquia Las Calderas", una combinacion que no existe
            # (Las Calderas es parroquia de Colina, no de Zamora). Ahora la
            # parroquia solo se acepta de un miembro cuyo propio municipio
            # coincida con el ya elegido (o que no declare ninguno) --
            # nunca de un miembro con un municipio DISTINTO.
            miembros_por_fecha = sorted(sub_miembros, key=lambda m: m["fecha"], reverse=True)
            municipio = next((m.get("municipio") for m in miembros_por_fecha if m.get("municipio")), None)
            parroquia = next(
                (
                    m.get("parroquia") for m in miembros_por_fecha
                    if m.get("parroquia") and (not m.get("municipio") or m.get("municipio") == municipio)
                ),
                None,
            )

            eventos.append({
                "tipo": tipo,
                "ubicacion": ubicacion,
                "municipio": municipio,
                "parroquia": parroquia,
                "grupos_fuentes": _agrupar_por_independencia(list(fuentes_unicas.values())),
            })

    return eventos
