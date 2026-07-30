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
    # Caso real (29-07-2026): articulos sobre el rescate de una mascota
    # atrapada entre los "escombros" de un edificio que colapso en un sismo
    # de mas de un mes antes ("Rescatan al gato Noche tras sobrevivir 33
    # dias bajo los escombros") disparaban tipo=deslizamiento -- son notas
    # de interes humano sobre un colapso viejo ya cubierto, no un
    # derrumbe/deslizamiento nuevo.
    "deslizamiento": ["gato", "gata", "gatito", "gatico", "mascota",
                       "perro", "perra", "perrito", "felino", "canino"],
    # Caso real (29-07-2026): un articulo titulado "Hantavirus: Enfermedad
    # totalmente controlada en Venezuela" (una nota que desmiente rumores,
    # sin casos nuevos confirmados por MinSalud) disparaba tipo=salud_publica
    # con severidad critica solo por mencionar fallecidos historicos.
    # Caso real (30-07-2026): un articulo sobre voluntarios armando kits de
    # higiene para "prevenir enfermedades" en zonas ya afectadas (una nota
    # de ayuda humanitaria en curso, sin ningun caso/brote real) disparaba
    # tipo=salud_publica solo por la palabra "enfermedades" en una frase
    # preventiva -- ninguna enfermedad se esta reportando en absoluto.
    "salud_publica": ["totalmente controlada", "enfermedad controlada",
                       "no existen registros confirmados",
                       "sin registros confirmados", "brote descartado",
                       "descartado el brote", "bajo control total",
                       "prevenir enfermedades", "prevenir la propagacion"],
}
_EVIDENCIA_FUERTE_POR_TIPO = {
    "sismo": ["magnitud", "richter", "funvisis", "epicentro", "se sintio",
              "sacudio", "remezon"],
    "colapso_estructural": ["colapso repentino", "colapso inesperado",
                            "heridos", "fallecidos", "atrapados bajo"],
    "explosion": ["explosion accidental", "explosion no controlada",
                  "explosion prematura", "heridos", "fallecidos"],
    "deslizamiento": ["heridos", "fallecidos", "desaparecidos",
                       "viviendas colapsadas", "viviendas destruidas",
                       "evacuados", "evacuadas", "familias afectadas"],
    "salud_publica": ["brote confirmado", "casos confirmados",
                       "declaro emergencia sanitaria",
                       "declaró emergencia sanitaria", "cuarentena",
                       "hospitalizados"],
}

# Un articulo que reporta que una entidad (USGS, Funvisis...) "ajusto"/
# "corrigio" la ubicacion del epicentro de un sismo YA OCURRIDO es un
# boletin tecnico retrospectivo sobre un evento pasado, nunca un temblor
# nuevo -- a diferencia de _CONTEXTO_CONFLICTIVO_POR_TIPO, esta señal es
# decisiva y NO se anula por evidencia fuerte de sismo (magnitud/epicentro/
# sacudio), porque esas mismas palabras describen el sismo original que se
# esta corrigiendo, no uno nuevo. Caso real (29-07-2026): "USGS ajusta el
# epicentro del terremoto en Venezuela: Se ubico en La Guaira y no en
# Yaracuy... el sismo de magnitud 7.5 que sacudio el centro-norte de
# Venezuela el pasado 24 de junio" genero dos alertas nuevas (La Guaira y
# Yaracuy) de un sismo de mas de un mes de antiguedad.
_CORRECCION_EPICENTRO_RETROSPECTIVA = [
    "ajusta el epicentro", "ajusto el epicentro", "ajustar el epicentro",
    "corrige el epicentro", "corrigio el epicentro", "corrigiendo el epicentro",
    "revisa el epicentro", "reviso el epicentro", "revision del epicentro",
    "reubica el epicentro", "reubico el epicentro", "reubicando el epicentro",
    "actualiza el epicentro", "actualizo el epicentro",
]


def _es_correccion_epicentro_retrospectiva(texto_norm):
    return any(_contiene_palabra_clave(texto_norm, frase) for frase in _CORRECCION_EPICENTRO_RETROSPECTIVA)


# A diferencia del boletin de epicentro (especifico de sismo), un articulo
# de "reportaje/feature" sobre una crisis cronica YA CONOCIDA, enmarcada
# explicitamente como algo que la gente "aprendio a vivir" o esperar
# durante meses/anos, tampoco describe un hecho nuevo -- sin importar el
# tipo de emergencia de fondo. Es una señal decisiva, igual que la de
# epicentro: no se anula por evidencia fuerte, porque esa evidencia (si la
# hay) describe la crisis original que el reportaje resume, no una
# novedad de hoy. Caso real (30-07-2026): "Cinco meses de espera: asi
# aprendieron los cumaneses a vivir sin agua" -- un reportaje sobre una
# averia de 5 meses (sistema Turimiquire), sin ningun desarrollo nuevo el
# dia de publicacion, generaba una alerta de "Falla de agua" como si el
# corte hubiera empezado esa manana.
_ARTICULO_RETROSPECTIVO_LARGA_DURACION = [
    "meses de espera", "años de espera", "anos de espera",
    "asi aprendieron", "así aprendieron", "aprendieron a vivir",
]


def _es_articulo_retrospectivo_larga_duracion(texto_norm):
    return any(_contiene_palabra_clave(texto_norm, frase) for frase in _ARTICULO_RETROSPECTIVO_LARGA_DURACION)


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

# "en los ultimos N dias"/"en la ultima semana" describe una VENTANA de
# tiempo sobre la que se reporta una tendencia (ej. "en los ultimos 15 dias
# aumentaron los cortes"), no la duracion de un corte continuo -- muy
# distinto de "cortes que superan las 94 horas". Sin esta exclusion, la
# ventana de reporte se confundia con una duracion real y escalaba la
# severidad de sin_clasificar a bajo sin que el texto describiera ningun
# corte prolongado en si.
_VENTANA_RECIENTE_RE = re.compile(r"\b(ultimos?|ultimas?|pasados?|pasadas?)\s*$", re.IGNORECASE)


def _es_ventana_reciente(texto_norm, posicion):
    contexto_previo = texto_norm[max(0, posicion - 20):posicion]
    return bool(_VENTANA_RECIENTE_RE.search(contexto_previo))


def _severidad_por_duracion(texto_norm, tipos):
    for tipo in tipos:
        umbral_dias = _UMBRAL_DIAS_DURACION_BAJO_POR_TIPO.get(tipo)
        if umbral_dias is None:
            continue
        umbral_horas = umbral_dias * 24
        if any(int(m.group(1)) >= umbral_horas for m in _DURACION_HORAS_RE.finditer(texto_norm)):
            return "bajo"
        if any(
            int(m.group(1)) >= umbral_dias and not _es_ventana_reciente(texto_norm, m.start())
            for m in _DURACION_DIAS_RE.finditer(texto_norm)
        ):
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
    """Devuelve una lista de (nombre_estado, ventana_cercana) -- una entrada
    por cada estado mencionado con evidencia clara de tipo de emergencia
    cerca (o via hashtag). Un articulo-resumen que cubre varios estados
    (comun en coberturas de lluvias/tormentas a nivel nacional) puede asi
    generar un evento por cada estado con evidencia real, en vez de
    quedarse solo con el primero que aparezca en el orden de
    config/estados.yaml y perder silenciosamente los demas.

    ventana_cercana es el fragmento de texto alrededor de la mención del
    estado que confirmó la ubicación; detectar_tipo()/detectar_severidad()
    lo usan para no tomar palabras clave de otra parte del artículo que
    describe un estado distinto. Es None cuando la ubicación viene de un
    hashtag (no hay una "mención en el texto" de la cual tomar una
    ventana).
    """
    estados = load_estados()
    hashtags = [h.lower() for h in _HASHTAG_RE.findall(texto)]

    encontrados = []
    vistos = set()

    for nombre_estado, alias in estados.items():
        for tag in hashtags:
            if tag in alias or tag == nombre_estado.lower().replace(" ", ""):
                if nombre_estado not in vistos:
                    encontrados.append((nombre_estado, None))
                    vistos.add(nombre_estado)
                break

    for nombre_estado, ventana in _detectar_ubicacion_texto_plano(texto, estados):
        if nombre_estado not in vistos:
            encontrados.append((nombre_estado, ventana))
            vistos.add(nombre_estado)

    return encontrados


def _posiciones_de_estados(tokens, estados):
    """Posiciones (indice de token) donde comienza la mencion de CUALQUIER
    estado en el texto -- se usa para que la ventana de proximidad de un
    estado nunca se extienda hasta la mencion de otro estado distinto (ver
    _ventana_cerca). Sin esto, un articulo-resumen que menciona varios
    estados en un mismo parrafo corto puede terminar atribuyendole a un
    estado la severidad/tipo de un hecho que en realidad describe a otro."""
    posiciones = []
    for nombre_estado, alias in estados.items():
        for candidato in set(alias) | {_normalizar(nombre_estado)}:
            candidato_tokens = candidato.split()
            primera = candidato_tokens[0]
            n = len(candidato_tokens)
            for i, t in enumerate(tokens):
                if t == primera and tokens[i:i + n] == candidato_tokens:
                    if not _es_mencion_subestatal(tokens, i) and not _es_mencion_direccional(tokens, i, candidato_tokens):
                        posiciones.append(i)
    return sorted(set(posiciones))


def _detectar_ubicacion_texto_plano(texto, estados):
    texto_norm = _normalizar(texto)
    palabras_tipo = [p for lista in load_keywords()["tipos"].values() for p in lista]
    tokens = _tokens(texto)
    posiciones_estados = _posiciones_de_estados(tokens, estados)
    resultado = []

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

            ventana = _ventana_cerca(tokens, candidato_norm, palabras_tipo, posiciones_estados)
            if ventana:
                resultado.append((nombre_estado, ventana))
                break  # ya se confirmo este estado, seguir con el siguiente

    return resultado


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


# Varios nombres de estado (Bolivar, Miranda, Sucre...) tambien son
# apellidos comunes en Venezuela. Un vocero/lider comunitario citado por su
# nombre puede generar un falso positivo de ubicacion -- caso real: "El
# lider social de la zona, Julian Bolivar, subrayo que..." y, mas
# adelante, "...alerto Bolivar" (la misma persona, citada por su
# apellido) -- el articulo trata en realidad sobre Monagas (dicho como
# "entidad monaguense", nunca menciona "Bolivar" como estado) pero
# generaba una alerta en el estado Bolivar.
_CALIFICADORES_LUGAR_ANTES_DE_NOMBRE = {
    "ciudad", "estado", "edo", "municipio", "parroquia", "gobernacion",
    "region", "distrito", "urbanizacion", "sector", "avenida", "av",
    "calle", "plaza", "puente", "aeropuerto", "libertador", "simon",
    "mariscal", "de", "del", "en", "desde", "hacia",
}
_VERBOS_ATRIBUCION_CITA = {
    "dijo", "afirmo", "explico", "alerto", "senalo", "indico", "declaro",
    "manifesto", "comento", "subrayo", "aseguro", "denuncio", "preciso",
    "advirtio", "reitero", "sostuvo", "recalco",
}


def _es_mencion_de_persona_citada(tokens, pos):
    """True si la mencion en `pos` de un nombre de estado que tambien es un
    apellido comun esta en realidad atribuyendo una cita a una persona
    (ver comentario arriba), no nombrando el estado. Exige que la palabra
    inmediatamente anterior no sea un calificador de lugar conocido (para
    no descartar lugares reales como "Ciudad Bolivar" o "estado Bolivar")
    Y que haya un verbo de atribucion de cita justo antes o justo
    despues."""
    anterior = tokens[pos - 1] if pos > 0 else ""
    if anterior in _CALIFICADORES_LUGAR_ANTES_DE_NOMBRE:
        return False
    if anterior in _VERBOS_ATRIBUCION_CITA:
        return True
    siguiente = tokens[pos + 1] if pos + 1 < len(tokens) else ""
    return siguiente in _VERBOS_ATRIBUCION_CITA


def _ventana_cerca(tokens, candidato_norm, palabras_tipo, posiciones_estados=None):
    """Devuelve la ventana de texto alrededor de candidato_norm si contiene
    alguna palabra clave de tipo, o None si no hay ninguna cerca.

    Si se pasan posiciones_estados (posiciones de TODAS las menciones de
    estados en el texto), la ventana se recorta para no cruzar la mencion
    mas cercana de OTRO estado, evitando que un articulo que habla de varios
    estados mezcle detalles (tipo/severidad) de uno con los de otro. Las
    menciones repetidas del MISMO estado (p.ej. el nombre de un medio local
    como "Zulia Sin Censura") no cuentan como frontera -- de lo contrario
    la ventana podia cortarse antes de llegar a un dato clave (una muerte,
    heridos) que esta mas cerca de esa repeticion que de un estado distinto."""
    candidato_tokens = candidato_norm.split()
    primera_palabra = candidato_tokens[0]

    posiciones = [
        i for i, t in enumerate(tokens)
        if t == primera_palabra
        and not _es_mencion_subestatal(tokens, i)
        and not _es_mencion_direccional(tokens, i, candidato_tokens)
        and not _es_mencion_de_persona_citada(tokens, i)
    ]
    posiciones_otros_estados = None
    if posiciones_estados:
        propias = set(posiciones)
        posiciones_otros_estados = [p for p in posiciones_estados if p not in propias]
    for pos in posiciones:
        limite_izq, limite_der = 0, len(tokens)
        if posiciones_otros_estados:
            anteriores = [p for p in posiciones_otros_estados if p < pos]
            siguientes = [p for p in posiciones_otros_estados if p > pos]
            if anteriores:
                limite_izq = max(limite_izq, max(anteriores) + 1)
            if siguientes:
                limite_der = min(limite_der, min(siguientes))
        inicio = max(limite_izq, pos - VENTANA_PROXIMIDAD_PALABRAS)
        fin = min(limite_der, pos + VENTANA_PROXIMIDAD_PALABRAS)
        ventana = " ".join(tokens[inicio:fin])
        for palabra in palabras_tipo:
            if _contiene_palabra_clave(ventana, palabra):
                return ventana
    return None


_LONGITUD_MINIMA_NOMBRE_DIRECTO = 5

# "Venezuela" es, por coincidencia, el nombre oficial de una parroquia real
# (Municipio Lagunillas, Zulia). Cualquier mencion de "Venezuela" en una
# noticia practicamente siempre se refiere al pais, nunca a esa parroquia
# especifica -- mismo problema que ya se resolvio para una parroquia
# homonima a su propio municipio, pero aqui la coincidencia es con el
# nombre del pais, no con el del municipio. Caso real que se escapo: un
# articulo que solo menciona "el occidente de Venezuela" se clasifico como
# "Parroquia Venezuela, Municipio Lagunillas, Zulia" sin que el texto
# mencionara Lagunillas en absoluto.
_NOMBRE_PAIS_NORM = "venezuela"

# ubicaciones_detalle.json trae la jerarquia real (estado -> municipio ->
# sus propias parroquias), tomada del listado de codigos de division
# politico-territorial (COD-AB/PCode) del INE. Antes el archivo tenia dos
# listas planas por estado (municipios y parroquias) sin relacion entre
# si, lo que permitia combinar un municipio de una fuente con una
# parroquia de otra que en realidad pertenecia a un municipio distinto
# (caso real: "Parroquia Guajira, Municipio Cabimas, Zulia" -- Guajira es
# una parroquia del municipio "Indigena Bolivariano Guajira", no de
# Cabimas).
_conteo_global_municipios = None
_conteo_global_parroquias = None
_indice_parroquias_por_estado = {}


def _municipios_por_variante(detalle_estado):
    """{nombre_normalizado: municipio_canonico} para todas las variantes
    (nombre oficial + alias) de los municipios de un estado."""
    resultado = {}
    for municipio, info in detalle_estado.get("municipios", {}).items():
        variantes = [municipio] + ([info["alias"]] if info.get("alias") else [])
        for variante in variantes:
            resultado[_normalizar(variante)] = municipio
    return resultado


def _parroquias_de(detalle_estado, municipio):
    """{nombre_normalizado: parroquia_canonica} de un municipio especifico."""
    info = detalle_estado.get("municipios", {}).get(municipio, {})
    return {_normalizar(p): p for p in info.get("parroquias", [])}


def _indice_parroquias_estado(detalle_estado):
    """{nombre_normalizado: [(municipio, parroquia_canonica), ...]} de TODAS
    las parroquias del estado, para resolver una parroquia mencionada sin
    saber todavia a que municipio pertenece. Una misma parroquia puede
    (rara vez) repetirse en mas de un municipio del mismo estado."""
    resultado = {}
    for municipio, info in detalle_estado.get("municipios", {}).items():
        for parroquia in info.get("parroquias", []):
            resultado.setdefault(_normalizar(parroquia), []).append((municipio, parroquia))
    return resultado


def _conteos_globales_ubicaciones():
    """Cuenta en cuantos estados distintos aparece cada nombre de municipio o
    parroquia (con sets, para no inflar el conteo si un nombre se repite en
    mas de un municipio del mismo estado). Muchos son nombres de proceres o
    de estados reusados en todo el pais (Sucre, Bolivar, Miranda,
    Independencia...) -- si un nombre asi se buscara suelto en el texto sin
    saber a que municipio pertenece, generaria falsos positivos constantes.
    Solo los nombres que aparecen en un unico estado son lo bastante
    especificos para una coincidencia directa sin ese contexto."""
    global _conteo_global_municipios, _conteo_global_parroquias
    if _conteo_global_municipios is None:
        cm, cp = Counter(), Counter()
        for detalle in load_ubicaciones_detalle().values():
            for normalizado in set(_municipios_por_variante(detalle)):
                cm[normalizado] += 1
            parroquias_estado = set()
            for info in detalle.get("municipios", {}).values():
                parroquias_estado.update(_normalizar(p) for p in info.get("parroquias", []))
            for normalizado in parroquias_estado:
                cp[normalizado] += 1
        _conteo_global_municipios, _conteo_global_parroquias = cm, cp
    return _conteo_global_municipios, _conteo_global_parroquias


def _buscar_municipio_directo(texto_norm, detalle_estado, nombre_estado_norm):
    """Busca el nombre de un municipio mencionado directamente en el texto
    (sin la palabra 'municipio' delante). Descarta nombres muy cortos,
    repetidos en varios estados, o identicos al nombre del propio estado.

    Si el texto menciona mas de un municipio distinto del mismo estado (caso
    real: "afectaron principalmente a los municipios Maracaibo, San
    Francisco, Cabimas, Mara y La Cañada de Urdaneta" -- una lista de 5
    municipios igualmente afectados), no se elige arbitrariamente el primero
    que aparezca en el orden de iteracion: eso afirmaria falsamente que solo
    ese municipio fue afectado. Se devuelve None (igual que cuando no se
    encuentra ninguno), dejando la ubicacion a nivel de solo el estado.

    Devuelve (municipio_o_None, nombres_normalizados_encontrados) -- el
    segundo elemento incluye TODOS los nombres que hicieron match, incluso
    cuando el resultado es ambiguo (mas de uno), para que el llamador pueda
    excluirlos de otras busquedas (ver _buscar_parroquia_directa): un
    municipio descartado por ambiguedad no debe poder "colarse" de vuelta
    solo porque su nombre tambien coincide, por casualidad, con el de una
    parroquia de un municipio distinto."""
    conteo_municipios, _ = _conteos_globales_ubicaciones()
    encontrados = set()
    normalizados_encontrados = set()
    for normalizado, original in _municipios_por_variante(detalle_estado).items():
        if len(normalizado) < _LONGITUD_MINIMA_NOMBRE_DIRECTO:
            continue
        if conteo_municipios[normalizado] > 1:
            continue
        if normalizado == nombre_estado_norm or normalizado == _NOMBRE_PAIS_NORM:
            continue
        if _contiene_palabra_clave(texto_norm, normalizado):
            encontrados.add(original)
            normalizados_encontrados.add(normalizado)
    if len(encontrados) == 1:
        return next(iter(encontrados)), normalizados_encontrados
    return None, normalizados_encontrados


def _buscar_parroquia_directa(texto_norm, detalle_estado, municipio, nombre_estado_norm, excluir_normalizados=None):
    """Busca una parroquia mencionada directamente en el texto. Si el
    municipio ya se conoce, busca SOLO dentro de sus propias parroquias (sin
    necesidad de chequeo de ambiguedad -- ya sabemos el contenedor exacto).
    Si el municipio no se conoce, solo acepta una coincidencia si el nombre
    es unico en todo el pais (un solo estado, y dentro de ese estado un solo
    municipio) -- en cuyo caso tambien se infiere el municipio. Devuelve
    (parroquia, municipio_inferido_o_None).

    Se excluye como evidencia una parroquia cuyo nombre coincide con el
    nombre o alias del propio municipio ya determinado -- de lo contrario,
    la misma palabra que identifico el municipio (p.ej. "Guajira" como
    alias de "Indigena Bolivariano Guajira") se reutilizaria como si fuera
    evidencia de una parroquia homonima dentro de ese municipio, aunque el
    texto nunca diga "parroquia Guajira" de forma explicita.

    `excluir_normalizados` (solo aplica cuando el municipio aun no se conoce):
    nombres que _buscar_municipio_directo() ya encontro pero descarto por
    ambiguedad (mas de un municipio distinto mencionado en el mismo texto).
    Sin esto, uno de esos mismos nombres ambiguos podia "colarse" de vuelta
    como si fuera evidencia de una parroquia de un municipio TOTALMENTE
    DISTINTO -- caso real: un texto que menciona "los municipios Colina,
    Zamora y Tocopero" (ambiguo a proposito, los tres igualmente validos)
    terminaba infiriendo "Municipio Petit" solo porque "Colina" tambien es,
    por coincidencia, el nombre de una parroquia de ese otro municipio."""
    if municipio is not None:
        info_municipio = detalle_estado.get("municipios", {}).get(municipio, {})
        nombres_municipio = {_normalizar(municipio)}
        if info_municipio.get("alias"):
            nombres_municipio.add(_normalizar(info_municipio["alias"]))
        for normalizado, original in _parroquias_de(detalle_estado, municipio).items():
            if len(normalizado) < _LONGITUD_MINIMA_NOMBRE_DIRECTO:
                continue
            if normalizado in nombres_municipio or normalizado == _NOMBRE_PAIS_NORM:
                continue
            if _contiene_palabra_clave(texto_norm, normalizado):
                return original, None
        return None, None

    excluir_normalizados = excluir_normalizados or set()
    _, conteo_parroquias = _conteos_globales_ubicaciones()
    indice = _indice_parroquias_estado(detalle_estado)
    for normalizado, ocurrencias in indice.items():
        if len(normalizado) < _LONGITUD_MINIMA_NOMBRE_DIRECTO:
            continue
        if normalizado in excluir_normalizados:
            continue
        if conteo_parroquias[normalizado] > 1 or len(ocurrencias) > 1:
            continue  # ambiguo entre estados o entre municipios del mismo estado
        if normalizado == nombre_estado_norm or normalizado == _NOMBRE_PAIS_NORM:
            continue
        if _contiene_palabra_clave(texto_norm, normalizado):
            municipio_unico, parroquia_unica = ocurrencias[0]
            return parroquia_unica, municipio_unico
    return None, None


def detectar_municipio_parroquia(texto, estado):
    if not estado:
        return None, None

    detalle = load_ubicaciones_detalle().get(estado, {})
    texto_norm = _normalizar(texto)
    nombre_estado_norm = _normalizar(estado)

    municipio_encontrado = None
    parroquia_encontrada = None
    nombres_municipio_ambiguos = set()

    m = _MUNICIPIO_RE.search(texto)
    if m:
        candidato = _normalizar(m.group(1).strip())
        municipio_encontrado = _municipios_por_variante(detalle).get(candidato)

    if municipio_encontrado is None:
        municipio_encontrado, nombres_municipio_ambiguos = _buscar_municipio_directo(
            texto_norm, detalle, nombre_estado_norm
        )

    p = _PARROQUIA_RE.search(texto)
    if p:
        candidato = _normalizar(p.group(1).strip())
        if municipio_encontrado is not None:
            # Solo se acepta si la parroquia mencionada realmente pertenece
            # al municipio ya determinado -- si no, se descarta en vez de
            # asumir que el municipio esta mal (evita el caso real de
            # combinar municipio y parroquia de fuentes distintas).
            parroquia_encontrada = _parroquias_de(detalle, municipio_encontrado).get(candidato)
        else:
            ocurrencias = _indice_parroquias_estado(detalle).get(candidato, [])
            if len(ocurrencias) == 1:
                municipio_encontrado, parroquia_encontrada = ocurrencias[0]

    if parroquia_encontrada is None:
        parroquia_encontrada, municipio_inferido = _buscar_parroquia_directa(
            texto_norm, detalle, municipio_encontrado, nombre_estado_norm,
            excluir_normalizados=nombres_municipio_ambiguos,
        )
        if municipio_encontrado is None and municipio_inferido is not None:
            municipio_encontrado = municipio_inferido

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
    # La correccion de epicentro es una propiedad del ARTICULO completo, no
    # de la mencion puntual de un estado -- un articulo multi-estado (ej.
    # "...se ubico en La Guaira y no en Yaracuy...") puede mencionar el
    # texto que prueba que es retrospectivo lejos (mas de la ventana de
    # proximidad) de alguno de los estados, sin que eso lo vuelva un sismo
    # nuevo para ese estado.
    texto_completo_norm = _normalizar(texto)
    # Igual que la correccion de epicentro, pero valida para CUALQUIER tipo
    # (no es especifica de sismo): un reportaje retrospectivo de larga
    # duracion no es un hecho nuevo sin importar la categoria.
    if _es_articulo_retrospectivo_larga_duracion(texto_completo_norm):
        return []
    tipos_encontrados = []
    for tipo, palabras in load_keywords()["tipos"].items():
        for palabra in palabras:
            if _contiene_palabra_clave(fuente_norm, palabra):
                if tipo == "sismo" and _es_correccion_epicentro_retrospectiva(texto_completo_norm):
                    break
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
    """Devuelve una LISTA de items clasificados: normalmente uno solo, pero
    un articulo que menciona varios estados con evidencia de tipo cerca de
    cada uno (ver detectar_ubicacion) genera un item por estado, cada uno
    con su propio tipo/severidad/municipio -- en vez de un solo evento
    arbitrario (el primer estado en el orden de estados.yaml) que ademas
    mezclaba severidad de todo el articulo, sin importar a que estado
    correspondia realmente cada detalle."""
    pre = item.pop("_preclasificado", None)
    if pre:
        item["ubicacion"] = pre["ubicacion"]
        item["tipos"] = pre["tipos"]
        item["severidad"] = pre["severidad"]
        item["municipio"] = None
        item["parroquia"] = None
        return [item]

    ubicaciones = detectar_ubicacion(item["texto"])
    if not ubicaciones:
        item["ubicacion"] = None
        item["tipos"] = []
        item["severidad"] = "sin_clasificar"
        item["municipio"] = None
        item["parroquia"] = None
        return [item]

    resultado = []
    for ubicacion, ventana in ubicaciones:
        nuevo = dict(item)
        nuevo["ubicacion"] = ubicacion
        nuevo["tipos"] = detectar_tipo(item["texto"], ventana)
        # La severidad tambien se restringe a la ventana cuando existe (un
        # articulo multi-estado no debe atribuirle a un estado la severidad
        # de un hecho que en realidad ocurrio en otro estado mencionado en
        # otra parte del mismo texto).
        texto_severidad = ventana if ventana is not None else item["texto"]
        nuevo["severidad"] = detectar_severidad(texto_severidad, nuevo["tipos"])
        nuevo["municipio"], nuevo["parroquia"] = detectar_municipio_parroquia(item["texto"], ubicacion)
        resultado.append(nuevo)
    return resultado


def es_relevante(item):
    return bool(item["ubicacion"]) and bool(item["tipos"])
