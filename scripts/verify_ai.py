import json
import os
import re
import time
import unicodedata
from datetime import datetime, timezone

import requests
from dateutil import parser as dateparser

from classify import _contiene_palabra_clave_no_negada
from config_loader import load_settings, load_estados, load_ubicaciones_detalle
from verify import extraer_magnitud

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PENDIENTES_PATH = os.path.join(BASE_DIR, "data", "pendientes_verificacion.json")

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL = "llama-3.3-70b-versatile"

# El monitoreo corre cada 10 minutos -- cuando Groq falla de forma
# transitoria (limite de tasa, respuesta invalida, error de red) para un
# evento, se retiene sin publicar hasta MAX_CICLOS_ESPERA_GROQ ciclos
# adicionales en vez de publicarlo sin verificar de inmediato. Se descubrio
# que, en la practica, la mayoria de las corridas agotan la cuota de Groq a
# mitad de camino (429 repetido), y publicar sin filtro de plausibilidad
# cada vez que eso pasa dejaba pasar la mayoria de las alertas del dia sin
# ninguna verificacion real (10 de 15 alertas de un solo dia, ver
# roadmap_evolucion.md). Solo tras agotar los reintentos se publica sin
# confirmar, como red de seguridad para no perder un evento real si Groq
# esta caido por mas tiempo del esperado.
MAX_CICLOS_ESPERA_GROQ = 2

# En corridas con muchos eventos agrupados (12+), la cuota de Groq se
# agotaba a mitad de camino y los eventos restantes se publicaban sin
# verificacion de IA (fail-open). Se espacian mas las llamadas entre si
# (ESPERA_ENTRE_LLAMADAS_GROQ) y se reintenta un 429 hasta
# MAX_REINTENTOS_GROQ veces con espera creciente (5s, 10s, 20s...), en vez
# de un solo reintento fijo de 5s.
ESPERA_ENTRE_LLAMADAS_GROQ = 3
MAX_REINTENTOS_GROQ = 3
ESPERA_BASE_REINTENTO_429 = 5

# Filtro determinista de respaldo: si el texto de una fuente contiene una
# marca temporal explícita de retrospectiva/aniversario, se descarta sin
# depender del juicio del modelo (que en la practica ha fallado en casos
# como "a un mes del terremoto en Vargas...").
_NUMEROS = r"(un|dos|tres|cuatro|cinco|seis|siete|ocho|nueve|diez|\d+)"
# Cualificador opcional entre "a"/"al cumplirse" y el numero -- caso real
# (11-08-2026, Runrun.es, una vez corregido el bug de truncamiento "[…]"
# de fetch_rss.py que ocultaba esta frase por completo): "a casi dos meses
# del doble terremoto, siguen buscando a sus familiares" no coincidia con
# el patron porque "casi" se interpone entre "a" y el numero -- el patron
# original exige que el numero siga inmediatamente a "a"/"al cumplirse".
_CUALIFICADOR_APROX = r"(?:(?:casi|cerca de|alrededor de)\s+)?"
_PATRON_RETROSPECTIVA = re.compile(
    rf"\b(a|al cumplirse)\s+{_CUALIFICADOR_APROX}{_NUMEROS}\s+"
    r"(dia|dias|semana|semanas|mes|meses|ano|anos)\s+(del|de|despues)\b"
    r"|\baniversario\b"
    rf"|\b{_NUMEROS}\s+(mes|meses|ano|anos)\s+despues\b"
    # "doble sismo"/"doblete sismico"/"doble terremoto" son los nombres
    # con que los medios venezolanos se refieren al sismo doble de La
    # Guaira/Vargas de hace un mes -- ninguna cobertura de un sismo
    # genuinamente nuevo usaria ese termino exacto. Caso real que se
    # escapo: "tras el doblete sismico, los rescatistas encontraron..."
    # (un articulo sobre labores de rescate del terremoto anterior, mal
    # clasificado como deslizamiento nuevo). Ampliado (11-08-2026) con
    # "doble terremoto"/"terremoto doble", la variante usada por Runrun.es
    # para el mismo evento ("a casi dos meses del doble terremoto").
    r"|\bdoblet?e?\s+sismic[oa]\b|\bdoble\s+sismo\b|\bsismo\s+doble\b"
    r"|\bdoble\s+terremoto\b|\bterremoto\s+doble\b"
    # Variante con la unidad de tiempo ANTES del numero ("dia 41 posterior
    # a los terremotos...", en vez de "41 dias despues de"). Caso real
    # (05-08-2026): un articulo sobre el rescate de cuerpos "en el dia 41
    # posterior a los terremotos... del pasado 24 de junio" se publico
    # como un sismo NUEVO en La Guaira -- es una labor de rescate en curso
    # de un sismo de mas de un mes de antiguedad, no un evento sismico
    # actual.
    rf"|\b(dia|dias)\s+{_NUMEROS}\s+posterior(?:es)?\s+a\b"
    # Caso real (15-08-2026, PASADO_POR_FALLA_TECNICA): "El Gran Sismo de
    # los Andes: la noche que la tierra borro pueblos enteros #15Ago -- A
    # las 10:15 de la noche del 28 de abril de 1894, un terremoto sacudio
    # Merida, Trujillo, Tachira..." -- una nota historica/efemeride sobre un
    # terremoto de 1894 (mas de un siglo de antiguedad) generaba alertas
    # nuevas de sismo/deslizamiento en Distrito Capital y Tachira, como si
    # hubiera ocurrido el dia de publicacion. Una fecha completa ("DD de MES
    # de AAAA") con un año claramente historico (anterior a 2020) es una
    # señal decisiva de que el relato es retrospectivo, sin importar cuanta
    # evidencia fuerte de sismo tenga (la evidencia describe el terremoto
    # historico, no uno nuevo). Se verifico contra las 122 fuentes de data/
    # historico_fuentes_texto.jsonl que esta combinacion (fecha completa con
    # año anterior a 2020) es exclusiva de este articulo.
    r"|\b\d{1,2}\s+de\s+(?:enero|febrero|marzo|abril|mayo|junio|julio|agosto|"
    r"septiembre|setiembre|octubre|noviembre|diciembre)\s+de\s+(?:1[0-9]\d\d|20[01]\d)\b"
    # Caso real (15-08-2026, PASADO_POR_FALLA_TECNICA): "Los terremotos de
    # Venezuela dejaron en La Guaira decenas de alumnos fallecidos... la
    # iniciativa responde a una emergencia educativa... especialmente en
    # Catia La Mar, epicentro del SEGUNDO terremoto" -- un reportaje de
    # largo aliento sobre la reconstruccion educativa semanas despues del
    # sismo doble de La Guaira/Vargas (ver "doble terremoto" arriba) usa la
    # variante "segundo terremoto"/"segundo sismo" (en vez de "doble") para
    # referirse al mismo evento ya cubierto, generando una alerta nueva de
    # sismo en Distrito Capital via una mencion de pasada al area
    # metropolitana de Caracas.
    r"|\bsegundo\s+terremoto\b|\bsegundo\s+sismo\b",
    re.IGNORECASE,
)


def _quitar_tildes(texto):
    return "".join(c for c in unicodedata.normalize("NFD", texto) if unicodedata.category(c) != "Mn")


def _normalizar(texto):
    return _quitar_tildes(texto.lower())


def _es_retrospectiva_obvia(texto):
    return _PATRON_RETROSPECTIVA.search(_normalizar(texto)) is not None


# Filtro determinista para tipo=vialidad: un choque rutinario entre 1-2
# vehiculos (o motorizados) con una victima no debe alertar como la Cruz
# Roja lo haria con un accidente masivo -- es el tipo de caso que ya lo
# atiende transito/ambulancia local. El prompt de la IA ya pedia rechazar
# estos casos, pero en la practica un choque individual con un fallecido
# se aprobo igual (calificado ademas como severidad CRITICA solo por
# mencionar un muerto, sin importar la escala del evento). Este filtro
# corre ANTES de la IA y no depende de su juicio: exige evidencia
# explicita de que el accidente es masivo/multiple, involucra transporte
# publico, o tiene varias victimas -- no solo tipo=vialidad + una palabra
# de severidad.
_NUMERO_HERIDOS_RE = re.compile(
    r"\b(tres|cuatro|cinco|seis|siete|ocho|nueve|diez|[3-9]|\d{2,})\s+"
    r"(heridos|heridas|lesionados|lesionadas)\b"
)
# Umbral mas alto para victimas fatales (5+, no 3+ como heridos): un
# fallecido o incluso unos pocos no deberian por si solos convertir un
# choque en "accidente masivo" -- el umbral de heridos es mas bajo porque
# hay mas heridos que fallecidos en accidentes de la misma magnitud.
_NUMERO_FALLECIDOS_RE = re.compile(
    r"\b(cinco|seis|siete|ocho|nueve|diez|[5-9]|\d{2,})\s+"
    r"(fallecidos|fallecidas|muertos|muertas)\b"
)
_EVIDENCIA_FUERTE_VIALIDAD_RE = re.compile(
    r"\b(colapso vial|colapso de la via|colapso de la vía|via colapsada|vía colapsada|"
    r"vias colapsadas|vías colapsadas|colision multiple|colisión múltiple|choque multiple|"
    r"choque múltiple|accidente masivo|volcamiento de autobus|volcamiento de autobús|"
    r"volcamiento de un autobus|volcamiento de un autobús|volcamiento de buseta|"
    r"volcamiento de una buseta|choque de autobus|choque de autobús|choque de un autobus|"
    r"choque de un autobús|autobus accidentado|autobús accidentado|"
    r"unidad de transporte publico|unidad de transporte público|transporte publico|"
    r"transporte público|multiples heridos|múltiples heridos|varios heridos|"
    r"numerosos heridos|varios fallecidos|multiples fallecidos|múltiples fallecidos|"
    r"varios muertos)\b",
    re.IGNORECASE,
)


def _vialidad_sin_evidencia_fuerte(texto):
    texto_norm = _normalizar(texto)
    tiene_evidencia = (
        _EVIDENCIA_FUERTE_VIALIDAD_RE.search(texto_norm) is not None
        or _NUMERO_HERIDOS_RE.search(texto_norm) is not None
        or _NUMERO_FALLECIDOS_RE.search(texto_norm) is not None
    )
    return not tiene_evidencia


# Filtro determinista para tipo=incendio: un incendio de un solo vehiculo en
# la via (una gandola, un camion) es un incidente rutinario de transito, no
# una emergencia que requiera respuesta de la Cruz Roja -- mismo patron que
# el filtro de vialidad. Solo se descarta cuando el incendio involucra un
# vehiculo; un incendio forestal, estructural o de otro tipo no pasa por
# este filtro. A diferencia de vialidad (que acepta CUALQUIERA de varias
# senales), aqui el usuario pidio explicitamente una condicion mas estricta:
# la fuente debe describir el hecho como un accidente MULTIPLE Y mencionar
# heridos o fallecidos -- ambas cosas a la vez, no una sola.
_VEHICULO_INCENDIO_RE = re.compile(
    r"\b(gandolas?|g[aá]ndolas?|camion(?:es)?|cami[oó]n(?:es)?|vehiculos?|veh[ií]culos?|"
    r"carros?|automovil(?:es)?|autom[oó]vil(?:es)?|motos?|motorizados?|autobus(?:es)?|"
    r"autob[uú]s(?:es)?|busetas?|furgones?|furg[oó]n(?:es)?|tractomulas?|cisternas?|"
    r"camionetas?|rastras?)\b",
    re.IGNORECASE,
)
_ACCIDENTE_MULTIPLE_RE = re.compile(
    r"\b(colision multiple|colisión múltiple|choque multiple|choque múltiple|"
    r"accidente masivo|accidente multiple|accidente múltiple|varios vehiculos|"
    r"varios vehículos|multiples vehiculos|múltiples vehículos|"
    r"choque entre varios vehiculos|choque entre varios vehículos)\b",
    re.IGNORECASE,
)
# Lista (no un solo regex) para poder usar _contiene_palabra_clave_no_negada()
# -- caso real (10-08-2026): un incendio de tres galpones en Petare
# ("Efecto Cocuyo") describia explicitamente "sin víctimas que lamentar" y
# "No hubo heridos, pero 5 personas resultaron afectadas por el humo" -- un
# regex simple habria contado "heridos" (dentro de "No hubo heridos") como
# evidencia de victimas pese a la negacion explicita justo antes.
_VICTIMAS_INCENDIO = [
    "herido", "herida", "heridos", "heridas", "lesionado", "lesionada",
    "lesionados", "lesionadas", "fallecido", "fallecida", "fallecidos",
    "fallecidas", "muerto", "muerta", "muertos", "muertas",
    "victima fatal", "víctima fatal", "victimas fatales", "víctimas fatales",
    "atrapado", "atrapada", "atrapados", "atrapadas",
    "evacuado", "evacuada", "evacuados", "evacuadas",
    "rescatado", "rescatada", "rescatados", "rescatadas",
    "intoxicado", "intoxicada", "intoxicados", "intoxicadas",
    "afectado por el humo", "afectada por el humo",
    "afectados por el humo", "afectadas por el humo",
]


def _tiene_victimas_incendio(texto_norm):
    return any(_contiene_palabra_clave_no_negada(texto_norm, f) for f in _VICTIMAS_INCENDIO)


def _incendio_vehiculo_sin_evidencia_fuerte(texto):
    texto_norm = _normalizar(texto)
    if not _VEHICULO_INCENDIO_RE.search(texto_norm):
        return False  # no es un incendio de vehiculo, este filtro no aplica
    tiene_accidente_multiple = _ACCIDENTE_MULTIPLE_RE.search(texto_norm) is not None
    tiene_victimas = _tiene_victimas_incendio(texto_norm)
    return not (tiene_accidente_multiple and tiene_victimas)


# Filtro determinista para tipo=incendio: un incendio de una sola vivienda,
# apartamento o galpon, ya sofocado y sin heridos/fallecidos/personas
# atrapadas o evacuadas, es un incidente rutinario que atiende el cuerpo de
# bomberos local, no algo que requiera respuesta de la Cruz Roja -- mismo
# principio que _incendio_vehiculo_sin_evidencia_fuerte() y que el criterio
# ya usado por la IA para tipo=vialidad (ver SYSTEM_PROMPT_TEMPLATE). Caso
# real (10-08-2026): "Voraz incendio se registra en tres galpones en
# Petare" -- el propio articulo, en sus 3 actualizaciones a lo largo de la
# noche, nunca menciona heridos ni fallecidos (una fuente distinta del
# mismo hecho, Efecto Cocuyo, lo confirma explicitamente: "sin víctimas
# que lamentar"). Deliberadamente NO se activa para "local comercial"/
# "centro comercial" (rango demasiado amplio, de un solo local a un
# centro comercial entero -- casos reales ya publicados de centros
# comerciales SIN victimas explicitas, como el incendio de Los Cedros en
# Nueva Esparta, se consideran significativos igual) ni para incendios
# forestales/estructurales de mayor escala.
_ESTRUCTURA_MENOR_INCENDIO_RE = re.compile(
    r"\b(vivienda|viviendas|apartamento|apartamentos|galpon|galpón|galpones)\b",
    re.IGNORECASE,
)


def _incendio_estructura_menor_sin_evidencia_fuerte(texto):
    texto_norm = _normalizar(texto)
    if not _ESTRUCTURA_MENOR_INCENDIO_RE.search(texto_norm):
        return False  # no es un incendio de vivienda/apartamento/galpon, no aplica
    return not _tiene_victimas_incendio(texto_norm)


# Filtro determinista para tipo=deslizamiento: la palabra "derrumbe" tambien
# se usa en espanol para el colapso de una pared/muro/techo por deterioro
# estructural (filtraciones, humedad acumulada, antiguedad) -- un evento que
# no tiene nada que ver con un deslizamiento de tierra causado por lluvia.
# Caso real que se escapo: "Filtraciones y humedad generan colapso parcial
# en iglesia San Fernando Rey de Ospino" (una pared de una iglesia colapso
# por filtraciones de años, sin ninguna lluvia ni movimiento de tierra
# involucrado), publicado como "Deslizamiento/Derrumbe en Municipio Ospino,
# Portuguesa". Mismo patron que el filtro de incendio vehicular: solo se
# activa cuando el texto tiene una senal de construccion/deterioro, y solo
# descarta si ademas NO hay ninguna senal de lluvia/movimiento de tierra que
# respalde que se trata de un deslizamiento real.
_ESTRUCTURA_DESLIZAMIENTO_RE = re.compile(
    r"\b(filtraciones|humedad acumulada|deterioro estructural|estructura deteriorada|"
    r"pared|paredes|muro|muros|techo|techos|campanario|iglesia|iglesias)\b",
    re.IGNORECASE,
)
_EVIDENCIA_FUERTE_DESLIZAMIENTO_RE = re.compile(
    r"\b(lluvia|lluvias|precipitacion|precipitaciones|aguacero|tormenta|onda tropical|"
    r"tierra|ladera|talud|cerro|barro|lodo|material rocoso|roca|piedras|"
    r"via|vía|carretera|autopista|quebrada|desbordamiento)\b",
    re.IGNORECASE,
)


def _deslizamiento_estructura_sin_evidencia_fuerte(texto):
    texto_norm = _normalizar(texto)
    if not _ESTRUCTURA_DESLIZAMIENTO_RE.search(texto_norm):
        return False  # no hay senal de colapso de construccion, este filtro no aplica
    return _EVIDENCIA_FUERTE_DESLIZAMIENTO_RE.search(texto_norm) is None


# Filtro determinista para tipo=sismo: la mayoria de sismos que se publican
# hoy son temblores menores sin ningun dano real, y estan empañando el
# proposito del sistema (demasiados reportes de baja relevancia). Un sismo
# solo debe alertar si (magnitud >=4 Y fue sentido por la poblacion o lo
# informa una fuente sismologica oficial) O si el texto ya describe danos
# reales (colapso, heridos, fallecidos) sin importar la magnitud.
UMBRAL_MAGNITUD_SISMO = 4.0
_SENTIDO_SISMO_RE = re.compile(
    r"\b(se sintio|se sintió|sacudio|sacudió|remezon|remezón|se percibio|se percibió)\b",
    re.IGNORECASE,
)
# Caso real (08-08-2026): "las autoridades de gestion de riesgo NO reportan
# daños estructurales ni personas lesionadas" (un sismo de magnitud 3.0 sin
# ningun dano real) se contaba como evidencia FUERTE de dano porque el
# regex original solo buscaba la frase "daños estructurales" en cualquier
# parte del texto, sin importar la negacion explicita justo antes -- se
# reemplaza la busqueda por _contiene_palabra_clave_no_negada() (ver
# classify.py), que ya descarta coincidencias precedidas de "sin"/"no"/
# "ningun" a pocas palabras de distancia.
# "colapso de" (sin objeto) se cambio por frases especificas -- caso real
# (10-08-2026): "colapso de árboles" (arboles caidos por una tormenta, sin
# relacion con ningun sismo) contaba como evidencia fuerte de dano
# sismico, en un articulo (sobre la actualizacion de magnitud de un sismo
# en Colombia) que traia pegada, sin relacion, una frase de clima ajena
# ("...el colapso de árboles a lo largo de la Carretera Panamericana...").
# Se verifico contra el corpus completo que "colapso de" solo aparecia,
# ademas de este caso, en "colapso de algunos sistemas" (drenaje, un
# articulo de inundacion) y "colapso de vivienda" (un caso real de
# colapso_estructural, no sismo) -- ningun caso legitimo de dano sismico
# en el corpus dependia de la version generica sin objeto.
_EVIDENCIA_DANO_SISMO = [
    "colapso estructural", "colapso de vivienda", "colapso de viviendas",
    "colapso de edificio", "colapso de edificios", "colapso de estructura",
    "colapso de estructuras", "derrumbe", "derrumbes",
    "heridos", "heridas", "fallecidos", "fallecidas", "muertos", "muertas",
    "danos severos", "daños severos", "danos estructurales",
    "daños estructurales", "edificacion colapsada", "edificación colapsada",
    "vivienda colapsada", "viviendas colapsadas", "grietas estructurales",
]
# Nombres de fuentes sismologicas oficiales -- hoy solo configuradas como
# canales de Telegram (FUNVISIS, INAMEH en config/sources.yaml), y la
# recoleccion de Telegram esta deshabilitada en main.py, asi que esta
# excepcion no tiene efecto real todavia. Se deja lista para cuando se
# reactive.
_FUENTES_SISMOLOGICAS_OFICIALES = ("funvisis", "inameh")


def _es_fuente_sismologica_oficial(fuente_nombre):
    nombre_norm = _normalizar(fuente_nombre)
    return any(oficial in nombre_norm for oficial in _FUENTES_SISMOLOGICAS_OFICIALES)


def _sismo_sin_evidencia_fuerte(texto, fuente_nombre):
    texto_norm = _normalizar(texto)
    if any(_contiene_palabra_clave_no_negada(texto_norm, f) for f in _EVIDENCIA_DANO_SISMO):
        return False

    magnitud = extraer_magnitud(texto)
    if magnitud is not None and magnitud >= UMBRAL_MAGNITUD_SISMO:
        if _SENTIDO_SISMO_RE.search(texto_norm) or _es_fuente_sismologica_oficial(fuente_nombre):
            return False

    return True


def _estados_mencionados_extra(texto_combinado, ubicacion_propia):
    """Devuelve la lista de estados (distintos de ubicacion_propia) que el
    texto combinado de las fuentes menciona explicitamente -- se usa
    exclusivamente para tipo=sismo, para saber si un mismo sismo fue
    reportado sintiendose en varios estados a la vez (p.ej. "se sintio en
    La Guaira, Distrito Capital y Miranda"), y asi poder correlacionar esa
    alerta con la que ya se publico bajo otra de esas ubicaciones el mismo
    dia (ver state.py)."""
    texto_norm = _normalizar(texto_combinado)
    encontrados = []
    for nombre_estado, alias in load_estados().items():
        if nombre_estado == ubicacion_propia:
            continue
        candidatos = set(alias) | {_normalizar(nombre_estado)}
        for candidato in candidatos:
            candidato_norm = _normalizar(candidato)
            if re.search(r"\b" + re.escape(candidato_norm) + r"\b", texto_norm):
                encontrados.append(nombre_estado)
                break
    return encontrados

SYSTEM_PROMPT_TEMPLATE = (
    "Eres un analista de un sistema de monitoreo de emergencias en Venezuela. "
    "Se te da la FECHA ACTUAL del sistema, un TIPO de emergencia que un "
    "clasificador automático le asignó a un grupo de reportes, y una lista "
    "numerada de fuentes periodísticas independientes sobre ese grupo. Tu "
    "tarea es clasificar CADA fuente por separado: para cada una, responde "
    "'SI' si esa fuente específica describe, como tema PRINCIPAL, un EVENTO "
    "EMERGENTE del tipo indicado que está ocurriendo AHORA o en las últimas "
    "24 horas contadas desde la fecha actual del sistema; responde 'NO' en "
    "caso contrario.\n"
    "\nUsa la fecha actual del sistema para evaluar expresiones temporales "
    "relativas de forma absoluta, no solo por el tono del texto (e.g., 'a un "
    "mes de la tragedia', 'al cumplirse 30 días', 'un mes después', 'la "
    "semana pasada').\n"
    "\nResponde 'NO' para una fuente si:\n"
    "• Es una retrospectiva, aniversario, homenaje, o cobertura semanas/meses "
    "después del evento original\n"
    "• No describe realmente un evento del tipo indicado, aunque lo mencione "
    "de pasada (e.g., tipo=sismo pero el texto es sobre un robo a víctimas de "
    "un sismo pasado, una nota policial, política o social que solo hace "
    "referencia a una emergencia anterior)\n"
    "• Si tipo=vialidad: es un accidente de tránsito individual y rutinario "
    "(un choque entre 1-2 vehículos, un motorizado herido, un volcamiento "
    "aislado) sin víctimas múltiples ni colapso de una vía completa — son "
    "casos que atiende tránsito/ambulancia local, no algo que requiera "
    "respuesta de la Cruz Roja\n"
    "• Si tipo=incendio: es un incendio de una sola vivienda, apartamento, "
    "vehículo o estructura menor, ya sofocado/controlado, sin heridos, "
    "fallecidos, personas atrapadas o evacuadas — son casos que atiende el "
    "cuerpo de bomberos local de forma rutinaria, no algo que requiera "
    "respuesta de la Cruz Roja\n"
    "• Es un reportaje/denuncia sobre un problema crónico (e.g., 'los "
    "apagones tienen en jaque a los comerciantes'), un análisis de impacto "
    "comercial o socioeconómico de una crisis pasada, o un asunto "
    "organizacional/administrativo (e.g., 'personal dejó la institución')\n"
    "• Describe un problema durable, no un evento súbito/agudo\n"
    "\nResponde 'SI' para una fuente solo si reporta, como tema principal, un "
    "evento del tipo indicado sucediendo ahora o en horas recientes, que "
    "requiere respuesta inmediata de emergencias (si tipo=vialidad, solo "
    "cuando hay colapso de una vía completa, un accidente masivo con "
    "múltiples heridos o fallecidos, o afectación significativa de "
    "infraestructura vial; si tipo=incendio, cuando hay heridos, "
    "fallecidos, personas atrapadas o evacuadas, o el incendio afecta una "
    "escala significativa — varias estructuras, un incendio forestal de "
    "gran magnitud, un centro comercial u otro inmueble de gran tamaño).\n"
    "\nFECHA ACTUAL DEL SISTEMA: {fecha_actual}\n"
    "\nDEBES RESPONDER EXCLUSIVAMENTE EN FORMATO JSON, sin explicaciones ni "
    "texto adicional. La estructura debe ser un objeto con una clave "
    "'veredictos' que contenga una lista de exactamente {n} strings ('SI' o "
    "'NO'), en el mismo orden en que se dan las fuentes.\n"
    "Ejemplo con 3 fuentes: {{\"veredictos\": [\"SI\", \"NO\", \"SI\"]}}"
)


BLOQUE_UBICACION_DETALLADA_TEMPLATE = (
    "\n\nADEMAS del array 'veredictos': el clasificador automático no pudo "
    "determinar con certeza el municipio y/o la parroquia donde ocurrió el "
    "evento dentro del estado ya indicado. Si el texto de las fuentes lo "
    "deja claro, agrega al mismo objeto JSON las claves 'municipio' y/o "
    "'parroquia', usando EXCLUSIVAMENTE un valor de estas listas (nunca "
    "inventes un nombre que no esté en ellas). Usa null si no se puede "
    "determinar con certeza.\n"
    "MUNICIPIOS VÁLIDOS: {municipios}\n"
    "PARROQUIAS VÁLIDAS: {parroquias}\n"
    "Ejemplo: {{\"veredictos\": [\"SI\"], \"municipio\": \"Sucre\", \"parroquia\": null}}"
)


def _listas_ubicacion_valida(estado):
    """Aplana la jerarquia estado->municipio->parroquias (ver classify.py)
    en dos listas simples de nombres validos, solo para este prompt de
    asistencia de IA -- no necesita la relacion municipio/parroquia
    completa, la deteccion deterministica en classify.py si la respeta."""
    detalle = load_ubicaciones_detalle().get(estado, {})
    municipios = list(detalle.get("municipios", {}).keys())
    parroquias = [
        p for info in detalle.get("municipios", {}).values()
        for p in info.get("parroquias", [])
    ]
    return municipios, parroquias


def _extraer_municipio_parroquia(respuesta_texto, municipios_validos, parroquias_validos):
    """Extrae 'municipio'/'parroquia' de la respuesta de la IA, aceptando
    unicamente un valor que coincida exactamente con la lista de opciones
    validas dadas en el prompt -- cualquier otro valor (incluido texto
    inventado o mal formado) se descarta como None, igual que la
    verificacion de plausibilidad nunca confia en texto libre sin validar."""
    try:
        datos = json.loads(respuesta_texto)
        if not isinstance(datos, dict):
            return None, None
        municipio = datos.get("municipio")
        parroquia = datos.get("parroquia")
        return (
            municipio if municipio in municipios_validos else None,
            parroquia if parroquia in parroquias_validos else None,
        )
    except (json.JSONDecodeError, TypeError, ValueError, AttributeError):
        return None, None


def _construir_prompt_fuentes(grupos_fuentes):
    bloques = []
    for i, grupo in enumerate(grupos_fuentes, start=1):
        representante = max(grupo, key=lambda m: m["peso"])
        bloques.append(
            f"--- Fuente {i} ({representante['fuente_nombre']}) ---\n"
            f"{representante['texto'][:500]}"
        )
    return "\n\n".join(bloques)[:6000]


def _parsear_veredictos_json(respuesta_texto, n):
    """Parsea la respuesta JSON de Groq, aceptando tanto un objeto con clave
    'veredictos' como una lista suelta. Normaliza tildes ('SÍ' -> 'SI') antes
    de comparar, y valida que haya exactamente n valores SI/NO -- cualquier
    otro caso devuelve None para que el llamador trate esto como fallo
    tecnico (fail-open auditado), no como una lista corrupta silenciosa."""
    try:
        datos = json.loads(respuesta_texto)
        if isinstance(datos, dict):
            valores = datos.get("veredictos", [])
        elif isinstance(datos, list):
            valores = datos
        else:
            return None

        valores_norm = [_quitar_tildes(str(v).strip()).upper() for v in valores]
        valores_validos = [v for v in valores_norm if v in ("SI", "NO")]

        if len(valores_validos) != n:
            return None
        return valores_validos
    except (json.JSONDecodeError, TypeError, ValueError, AttributeError):
        return None


BONO_FUENTE_LOCAL = 0.1


def _peso_efectivo(fuente, ubicacion_evento):
    """El peso base de una fuente (config/sources.yaml) mide su confiabilidad
    general, pero un medio regional que reporta sobre su propia zona aporta
    mas certeza que el mismo medio reportando sobre otro estado -- por eso el
    bono se aplica aqui, por evento, y no como un ajuste fijo al peso en la
    config."""
    bono = BONO_FUENTE_LOCAL if fuente.get("region") == ubicacion_evento else 0
    return fuente["peso"] + bono


def _finalizar_evento(evento, grupos_aprobados, error_sistema=False):
    """error_sistema=True marca que las fuentes no pasaron por un veredicto
    real de la IA (sin API key, respuesta no parseable, o fallo de red/rate
    limit tras agotar reintentos) y se dejaron pasar por seguridad -- queda
    registrado en 'estado_verificacion' para auditoria, y nunca se etiqueta
    como CONFIRMADO sin verificacion real, sin importar el score."""
    settings = load_settings()["verificacion"]
    umbral = settings["umbral_confirmado"]

    representantes = sorted(
        (max(g, key=lambda m: m["peso"]) for g in grupos_aprobados),
        key=lambda m: m["peso"], reverse=True,
    )
    miembros_aprobados = [m for g in grupos_aprobados for m in g]

    # evento["municipio"]/["parroquia"] los fija verify.agrupar_y_verificar()
    # ANTES de esta verificacion, a partir de TODOS los miembros del cluster
    # (el mas reciente con un valor no nulo) -- incluye fuentes que la IA
    # puede rechazar aqui mismo por no ser el mismo hecho. Sin este chequeo,
    # una fuente descartada que sí nombraba un municipio/parroquia deja esa
    # ubicacion "pegada" al evento final aunque ninguna fuente PUBLICADA la
    # respalde. Mismo criterio que ya se aplica abajo para el municipio/
    # parroquia que propone la IA (ver comentario en pedir_ubicacion) --
    # aqui aplica tambien cuando classify.py ya lo habia determinado y por
    # eso nunca se le pidio nada a la IA. Caso real (31-07-2026): un cluster
    # de "incendio en Distrito Capital" con una fuente aprobada sobre el
    # CCCT (sin mencionar ningun municipio) y otra fuente del mismo cluster,
    # sobre un hecho distinto, que si mencionaba "Parroquia La Vega,
    # Municipio Libertador" y fue rechazada -- el evento publicado terminaba
    # con esa parroquia/municipio igual.
    texto_aprobados_norm = _normalizar(" ".join(m["texto"] for m in miembros_aprobados))
    if evento.get("municipio") and _normalizar(evento["municipio"]) not in texto_aprobados_norm:
        print(
            f"[WARN] Municipio '{evento['municipio']}' del cluster no aparece "
            f"textualmente en las fuentes aprobadas; se descarta para evitar "
            f"una ubicación inventada."
        )
        evento["municipio"] = None
    if evento.get("parroquia") and _normalizar(evento["parroquia"]) not in texto_aprobados_norm:
        print(
            f"[WARN] Parroquia '{evento['parroquia']}' del cluster no aparece "
            f"textualmente en las fuentes aprobadas; se descarta para evitar "
            f"una ubicación inventada."
        )
        evento["parroquia"] = None

    score = sum(_peso_efectivo(r, evento["ubicacion"]) for r in representantes)
    severidades = [m["severidad"] for m in miembros_aprobados if m["severidad"] != "sin_clasificar"]
    orden_severidad = ["critico", "alto", "medio", "bajo"]
    severidad_final = next((s for s in orden_severidad if s in severidades), "sin_clasificar")
    fecha_mas_reciente = max(miembros_aprobados, key=lambda m: dateparser.isoparse(m["fecha"]))["fecha"]
    fecha_mas_temprana = min(miembros_aprobados, key=lambda m: dateparser.isoparse(m["fecha"]))["fecha"]

    resultado = {
        "tipo": evento["tipo"],
        "ubicacion": evento["ubicacion"],
        "municipio": evento["municipio"],
        "parroquia": evento["parroquia"],
        "severidad": severidad_final,
        "score": round(score, 2),
        "confirmado": (score >= umbral) and not error_sistema,
        "num_fuentes": len(representantes),
        "fuentes": [
            {"nombre": m["fuente_nombre"], "link": m["link"], "fecha": m["fecha"]}
            for m in miembros_aprobados
        ],
        # True si ALGUNA fuente aprobada es un reporte de filial (ver
        # attachments_filial.py) -- render.py lo usa para mostrar un
        # distintivo y el resumen consolidado en vez del formato generico,
        # ya que a diferencia de una fuente RSS el enlace de un correo de
        # Gmail no es accesible para el publico.
        "es_reporte_filial": any(m.get("es_reporte_filial") for m in miembros_aprobados),
        # Si hay varios reportes de filial para el mismo evento (p.ej. un
        # reporte inicial y una "actualizacion" posterior), se muestra
        # SOLO el resumen del mas reciente -- una actualizacion de filial
        # reemplaza las cifras anteriores, no las corrobora ni se le suman
        # (a diferencia de dos medios de prensa distintos reportando el
        # mismo hecho, que si son confirmaciones independientes).
        "resumen_consolidado": next(
            (
                m["resumen_consolidado"]
                for m in sorted(miembros_aprobados, key=lambda m: m["fecha"], reverse=True)
                if m.get("resumen_consolidado")
            ),
            None,
        ),
        "fecha_evento": fecha_mas_reciente,
        # Se usa para el dia calendario de la clave de deduplicacion en
        # state.py -- "fecha_evento" (la fuente MAS reciente) avanza cada
        # vez que aparece un articulo de seguimiento, y una cobertura
        # continua de varios dias sobre el mismo hecho (ej. una via
        # bloqueada por un deslizamiento) puede cruzar la medianoche UTC y
        # hacer que el sistema lo trate como un evento nuevo. La fuente MAS
        # TEMPRANA se mantiene estable mientras siga dentro de la ventana de
        # busqueda, y ancla la deduplicacion al dia real del hecho.
        "fecha_evento_temprana": fecha_mas_temprana,
        "fecha_deteccion": datetime.now(timezone.utc).isoformat(),
        "estado_verificacion": "PASADO_POR_FALLA_TECNICA" if error_sistema else "APROBADO_IA",
        # Clave "privada" (prefijo "_"): texto completo de cada fuente, para
        # poder generar mas adelante informes narrativos por periodo sin
        # depender de que el articulo original siga en linea meses despues.
        # historico_fuentes.py la extrae y la BORRA del evento antes de que
        # render.py/build_site.py lo conviertan en la noticia publica -- el
        # sitio publico nunca debe reproducir el texto completo de terceros.
        "_texto_fuentes_completo": [
            {"nombre": m["fuente_nombre"], "link": m["link"], "texto": m["texto"]}
            for m in miembros_aprobados
        ],
    }

    # Solo para sismos: la magnitud y las menciones a otros estados sirven
    # para correlacionar (state.py) el mismo sismo sentido en varias
    # ubicaciones, sin depender de una ventana de tiempo estrecha entre
    # publicaciones (ver conversacion del 2026-07-25).
    if evento["tipo"] == "sismo":
        texto_combinado = " ".join(m["texto"] for m in miembros_aprobados)
        resultado["magnitud"] = extraer_magnitud(texto_combinado)
        resultado["tambien_mencionado_en"] = _estados_mencionados_extra(
            texto_combinado, evento["ubicacion"]
        )

    return resultado


def _clave_pendiente(evento):
    """Clave para rastrear cuantos ciclos lleva un cluster esperando una
    verificacion real de Groq. Se ancla al dia calendario (no a una fecha
    mas precisa del evento) a proposito: es solo para acotar cuantas
    corridas seguidas se retiene el mismo cluster, no para deduplicar
    publicaciones (eso ya lo hace state.py) -- un cluster que sigue
    fallando al cruzar la medianoche UTC simplemente arranca de cero, lo
    cual es aceptable para esta ventana corta de reintentos."""
    dia = datetime.now(timezone.utc).date().isoformat()
    return f"{evento['tipo']}::{evento['ubicacion']}::{dia}"


def _cargar_pendientes():
    if not os.path.exists(PENDIENTES_PATH):
        return {}
    with open(PENDIENTES_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def _guardar_pendientes(pendientes):
    os.makedirs(os.path.dirname(PENDIENTES_PATH), exist_ok=True)
    with open(PENDIENTES_PATH, "w", encoding="utf-8") as f:
        json.dump(pendientes, f, ensure_ascii=False, indent=2)


def _limpiar_pendiente(evento):
    """Se llama cuando Groq SI responde con exito (aprobado o rechazado) --
    ya no hace falta seguir contando ciclos fallidos para este cluster."""
    clave = _clave_pendiente(evento)
    pendientes = _cargar_pendientes()
    if pendientes.pop(clave, None) is not None:
        _guardar_pendientes(pendientes)


def _manejar_falla_temporal(evento, candidatos):
    """Cuando Groq falla de forma transitoria, retiene el evento sin
    publicar hasta MAX_CICLOS_ESPERA_GROQ ciclos (ver comentario junto a esa
    constante) antes de usar el mecanismo de "fallar hacia lo seguro"
    (publicar sin confirmar). Devuelve None mientras se retiene, o el evento
    finalizado con error_sistema=True una vez agotados los reintentos.

    Retener solo tiene sentido si el mismo cluster puede reaparecer en una
    corrida futura -- cierto para RSS (el articulo sigue en la ventana de
    busqueda) pero FALSO para correos institucionales: fetch_gmail.py marca
    cada correo como leido apenas lo procesa una vez, asi que si se retiene
    aqui, ese reporte nunca vuelve a generarse y quedaria retenido para
    siempre (bug real encontrado probando el reporte de Filial Puerto
    Piritu: quedo con 1 intento fallido sin forma de llegar nunca al
    segundo). Un cluster formado EXCLUSIVAMENTE por fuentes de correo se
    publica de inmediato sin confirmar, como antes de este cambio."""
    if all(m["fuente_tipo"] == "correo" for g in candidatos for m in g):
        print(
            f"[WARN] Groq no disponible para [{evento['tipo']}/{evento['ubicacion']}] -- "
            f"proviene solo de correo institucional (no se puede retener para un "
            f"proximo ciclo, el mensaje ya se marco como leido), se publica sin verificar."
        )
        return _finalizar_evento(evento, candidatos, error_sistema=True)

    clave = _clave_pendiente(evento)
    pendientes = _cargar_pendientes()
    intentos_previos = pendientes.get(clave, {}).get("intentos", 0)

    if intentos_previos < MAX_CICLOS_ESPERA_GROQ:
        pendientes[clave] = {
            "intentos": intentos_previos + 1,
            "ultima_vez": datetime.now(timezone.utc).isoformat(),
        }
        _guardar_pendientes(pendientes)
        print(
            f"[WARN] Groq no disponible para [{evento['tipo']}/{evento['ubicacion']}] -- "
            f"se retiene sin publicar (intento {intentos_previos + 1}/{MAX_CICLOS_ESPERA_GROQ}, "
            f"se reintentará en el próximo ciclo)."
        )
        return None

    pendientes.pop(clave, None)
    _guardar_pendientes(pendientes)
    print(
        f"[WARN] Groq sigue sin disponibilidad para [{evento['tipo']}/{evento['ubicacion']}] "
        f"tras {MAX_CICLOS_ESPERA_GROQ} ciclos de espera -- se publica sin verificar, "
        f"como red de seguridad."
    )
    return _finalizar_evento(evento, candidatos, error_sistema=True)


def verificar_evento_con_ia(evento):
    """Clasifica con IA cada fuente independiente del evento por separado
    (no un veredicto agregado unico), y recalcula score/severidad/confirmado
    usando solo las fuentes que la IA considero vigentes. Devuelve el evento
    final listo para publicar, o None si ninguna fuente fue aprobada.

    Publicar (evento no-None) solo requiere que AL MENOS UNA fuente sea
    aprobada -- igual que el criterio de publicacion anterior a este cambio.
    El umbral de score (`confirmado`) sigue siendo un criterio aparte, usado
    unicamente para la etiqueta CONFIRMADO/SIN CONFIRMAR, no para decidir si
    se publica."""
    grupos_fuentes = evento["grupos_fuentes"]

    # Filtro determinista primero: descarta de una vez las fuentes cuyo texto
    # marca explicitamente una retrospectiva/aniversario (independiente del
    # juicio del modelo, que en produccion ha fallado con frases como "a un
    # mes del terremoto en Vargas..." pese a estar cubiertas en el prompt).
    #
    # Se evalua ANTES de comprobar GROQ_API_KEY (08-08-2026): estos filtros
    # son regex puros, no dependen de ninguna llamada a la IA, pero vivian
    # despues del `if not api_key: return ...` de mas abajo -- cuando la
    # clave no esta configurada (el caso real de este entorno, ver
    # roadmap_evolucion.md), TODOS los eventos se publicaban con
    # error_sistema=True sin pasar nunca por este filtro, incluyendo los
    # peores falsos positivos que existe precisamente para atrapar (un sismo
    # de magnitud 3.0 sin evidencia fuerte, una via/incendio/deslizamiento
    # sin evidencia fuerte). El camino de fallo transitorio de Groq (ver
    # _manejar_falla_temporal) ya aplicaba el filtro correctamente porque
    # recibe `candidatos` (post-filtro), no `grupos_fuentes`; ahora ambos
    # caminos son consistentes.
    obvios_rechazados = []
    candidatos = []
    for grupo in grupos_fuentes:
        representante = max(grupo, key=lambda m: m["peso"])
        if _es_retrospectiva_obvia(representante["texto"]):
            obvios_rechazados.append(representante)
        elif evento["tipo"] == "vialidad" and _vialidad_sin_evidencia_fuerte(representante["texto"]):
            obvios_rechazados.append(representante)
        elif evento["tipo"] == "incendio" and (
            _incendio_vehiculo_sin_evidencia_fuerte(representante["texto"])
            or _incendio_estructura_menor_sin_evidencia_fuerte(representante["texto"])
        ):
            obvios_rechazados.append(representante)
        elif evento["tipo"] == "deslizamiento" and _deslizamiento_estructura_sin_evidencia_fuerte(representante["texto"]):
            obvios_rechazados.append(representante)
        elif evento["tipo"] == "sismo" and _sismo_sin_evidencia_fuerte(representante["texto"], representante["fuente_nombre"]):
            obvios_rechazados.append(representante)
        else:
            candidatos.append(grupo)

    if obvios_rechazados:
        detalle_rechazados = ", ".join(
            f"{r['fuente_nombre']} ({r['link']})" for r in obvios_rechazados
        )
        print(
            f"[DEBUG] Filtro retrospectiva/vialidad [{evento['tipo']}/{evento['ubicacion']}]: "
            f"rechazadas sin IA por marca temporal explicita o falta de evidencia fuerte: {detalle_rechazados}"
        )

    if not candidatos:
        return None

    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        print("[WARN] GROQ_API_KEY no configurada, se omite verificación de plausibilidad")
        return _finalizar_evento(evento, candidatos, error_sistema=True)

    n = len(candidatos)
    fecha_actual = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    system_prompt = SYSTEM_PROMPT_TEMPLATE.format(fecha_actual=fecha_actual, n=n)

    # Si el clasificador (regex sobre municipios/parroquias conocidos, ver
    # classify.py) no pudo determinar municipio y/o parroquia, se le pide a
    # la misma llamada de IA que ya se hace para verificar plausibilidad que
    # intente inferirlo del texto completo, restringido a los valores reales
    # de ese estado -- evita una llamada aparte y nunca deja que la IA
    # invente un nombre fuera de la lista.
    pedir_ubicacion = evento.get("municipio") is None or evento.get("parroquia") is None
    municipios_validos, parroquias_validos = ([], [])
    if pedir_ubicacion:
        municipios_validos, parroquias_validos = _listas_ubicacion_valida(evento["ubicacion"])
        if municipios_validos or parroquias_validos:
            system_prompt += BLOQUE_UBICACION_DETALLADA_TEMPLATE.format(
                municipios=municipios_validos, parroquias=parroquias_validos,
            )
        else:
            pedir_ubicacion = False

    contenido_usuario = (
        f"TIPO ASIGNADO POR EL CLASIFICADOR: {evento['tipo']}\n\n"
        f"{_construir_prompt_fuentes(candidatos)}"
    )

    try:
        resp = None
        for intento in range(MAX_REINTENTOS_GROQ):
            # Pausa entre llamadas sucesivas a Groq: en un mismo ciclo se
            # llama una vez por evento agrupado, y sin espaciarlas se
            # alcanzaba el limite de tasa (429) y el evento se dejaba pasar
            # sin verificar (fail-open).
            time.sleep(ESPERA_ENTRE_LLAMADAS_GROQ)
            resp = requests.post(
                GROQ_URL,
                headers={"Authorization": f"Bearer {api_key}"},
                json={
                    "model": GROQ_MODEL,
                    "temperature": 0,
                    "response_format": {"type": "json_object"},
                    "max_tokens": max(30, n * 6 + 20) + (40 if pedir_ubicacion else 0),
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": contenido_usuario},
                    ],
                },
                timeout=20,
            )
            if resp.status_code == 429 and intento < MAX_REINTENTOS_GROQ - 1:
                espera = ESPERA_BASE_REINTENTO_429 * (2 ** intento)
                print(f"[WARN] Groq devolvió 429 (rate limit), reintentando en {espera}s... (intento {intento + 2}/{MAX_REINTENTOS_GROQ})")
                time.sleep(espera)
                continue
            break

        resp.raise_for_status()
        respuesta = resp.json()["choices"][0]["message"]["content"].strip()
        veredictos = _parsear_veredictos_json(respuesta, n)

        if veredictos is None:
            print(
                f"[WARN] Groq devolvió un JSON de veredictos inválido o de "
                f"tamaño distinto al esperado ({n} fuentes): '{respuesta[:200]}'."
            )
            return _manejar_falla_temporal(evento, candidatos)

        _limpiar_pendiente(evento)

        representantes = [max(g, key=lambda m: m["peso"]) for g in candidatos]
        detalle = ", ".join(
            f"{r['fuente_nombre']} ({r['link']})={v}" for r, v in zip(representantes, veredictos)
        )
        grupos_aprobados = [g for g, v in zip(candidatos, veredictos) if v == "SI"]
        print(
            f"[DEBUG] Groq verificación [{evento['tipo']}/{evento['ubicacion']}]: "
            f"{detalle} → {len(grupos_aprobados)}/{n} fuentes aprobadas"
        )

        if not grupos_aprobados:
            return None

        if pedir_ubicacion:
            municipio_ia, parroquia_ia = _extraer_municipio_parroquia(
                respuesta, municipios_validos, parroquias_validos
            )
            # El anclaje textual debe verificarse SOLO contra las fuentes que
            # de verdad se van a publicar (grupos_aprobados), no contra todos
            # los candidatos evaluados (candidatos incluye fuentes que la IA
            # acaba de rechazar por no ser el mismo hecho). De lo contrario,
            # un municipio/parroquia mencionado unicamente en una fuente
            # descartada "ancla" una ubicacion que ninguna fuente publicada
            # respalda -- caso real: un cluster de "colapso estructural en
            # Zulia" con una fuente aprobada (una vivienda colapsada, sin mas
            # detalle de ubicacion) y otra fuente del mismo cluster, sobre un
            # hecho distinto, que si mencionaba "Sinamaica"/"Guajira" y fue
            # rechazada por la IA -- el evento publicado terminaba con esa
            # parroquia/municipio igual, pese a que la unica fuente publicada
            # nunca los menciona.
            texto_fuentes_norm = _normalizar(
                " ".join(m["texto"] for g in grupos_aprobados for m in g)
            )
            # Un municipio/parroquia que por coincidencia se llama igual que
            # su propio estado (frecuente en capitales de estado
            # venezolanas, ej. municipio "Barinas" del estado Barinas) o que
            # el pais ("Venezuela") aparece textualmente en casi cualquier
            # articulo sobre esa zona solo por mencionar el nombre del
            # estado/pais -- no es evidencia real de esa entidad
            # administrativa especifica. classify.py ya excluye este caso en
            # su busqueda determinista (_buscar_municipio_directo/
            # _buscar_parroquia_directa); se aplica el mismo criterio aqui
            # para que la IA no "confirme" su propia alucinacion solo porque
            # el nombre del estado esta trivialmente presente en el texto.
            ubicacion_norm = _normalizar(evento["ubicacion"])
            if municipio_ia and _normalizar(municipio_ia) in (ubicacion_norm, "venezuela"):
                print(
                    f"[WARN] Groq propuso municipio '{municipio_ia}', igual al nombre del "
                    f"estado/pais; se descarta por no ser evidencia de un municipio "
                    f"especifico."
                )
                municipio_ia = None
            if parroquia_ia and _normalizar(parroquia_ia) in (ubicacion_norm, "venezuela"):
                print(
                    f"[WARN] Groq propuso parroquia '{parroquia_ia}', igual al nombre del "
                    f"estado/pais; se descarta por no ser evidencia de una parroquia "
                    f"especifica."
                )
                parroquia_ia = None
            if municipio_ia and _normalizar(municipio_ia) not in texto_fuentes_norm:
                print(
                    f"[WARN] Groq propuso municipio '{municipio_ia}' pero ese nombre no "
                    f"aparece textualmente en las fuentes; se descarta para evitar una "
                    f"ubicación inventada."
                )
                municipio_ia = None
            if parroquia_ia and _normalizar(parroquia_ia) not in texto_fuentes_norm:
                print(
                    f"[WARN] Groq propuso parroquia '{parroquia_ia}' pero ese nombre no "
                    f"aparece textualmente en las fuentes; se descarta para evitar una "
                    f"ubicación inventada."
                )
                parroquia_ia = None
            if evento.get("municipio") is None and municipio_ia:
                evento["municipio"] = municipio_ia
            if evento.get("parroquia") is None and parroquia_ia:
                evento["parroquia"] = parroquia_ia

        return _finalizar_evento(evento, grupos_aprobados)

    except Exception as e:
        print(f"[WARN] Fallo la verificación con Groq: {e}")
        return _manejar_falla_temporal(evento, candidatos)
