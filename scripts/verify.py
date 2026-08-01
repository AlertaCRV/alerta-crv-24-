import difflib
import re
from datetime import timedelta

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


# Ventana usada para separar reportes de filial del mismo tipo+ubicacion en
# sub-eventos distintos cuando llegan muy espaciados en el tiempo -- misma
# duracion que VENTANA_HORAS_MISMO_EVENTO en state.py, para no inventar un
# criterio nuevo sin motivo. A diferencia de un articulo de prensa (que
# suele decir "actualizacion" o dar continuidad explicita a un hecho
# anterior), un reporte de filial es una cifra puntual sin ninguna
# indicacion de si es una actualizacion de una situacion ya informada o
# una nueva -- confirmado por el usuario (01-08-2026): "cada correo se
# toma como independiente sin considerar si en el pasado se informo sobre
# lo mismo y sin considerar si es o no una actualizacion". Sin este
# limite, dos (o mas) reportes de la misma filial sobre el mismo
# municipio, aunque esten semanas de diferencia, se fusionaban en un solo
# evento -- caso real (29-07-2026): 3 correos sobre Zamora, Falcon
# fechados 07-07, 28-07 y 29-07 (22 dias de diferencia entre el primero y
# el ultimo) se combinaron en una sola alerta con un resumen_consolidado
# que mezclaba cifras de familias/personas que no calzaban entre si.
VENTANA_HORAS_MISMO_EVENTO_FILIAL = 36


def _separar_reportes_filial_por_ventana(miembros):
    """Si un cluster (mismo tipo+ubicacion, misma corrida) tiene reportes
    de filial cuyas fechas se apartan mas de
    VENTANA_HORAS_MISMO_EVENTO_FILIAL entre reportes consecutivos, los
    separa en sub-eventos -- de lo contrario (todos dentro de la ventana,
    o ningun miembro es reporte de filial), los deja en un solo grupo,
    igual que antes. Los miembros que NO son reporte de filial (un
    articulo de prensa sobre el mismo tipo+ubicacion, caso raro pero
    posible) se unen al sub-grupo de filiales mas reciente en vez de
    quedar en un grupo aparte."""
    filiales = sorted(
        (m for m in miembros if m.get("es_reporte_filial")),
        key=lambda m: m["fecha"],
    )
    if len(filiales) < 2:
        return [miembros]

    limite = timedelta(hours=VENTANA_HORAS_MISMO_EVENTO_FILIAL)
    grupos = [[filiales[0]]]
    for anterior, actual in zip(filiales, filiales[1:]):
        gap = dateparser.isoparse(actual["fecha"]) - dateparser.isoparse(anterior["fecha"])
        if gap <= limite:
            grupos[-1].append(actual)
        else:
            grupos.append([actual])

    no_filiales = [m for m in miembros if not m.get("es_reporte_filial")]
    if no_filiales:
        grupos[-1].extend(no_filiales)

    return grupos


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
        if tipo == "sismo":
            sub_clusters = _separar_sismos_por_magnitud(miembros)
        else:
            sub_clusters = _separar_reportes_filial_por_ventana(miembros)

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
