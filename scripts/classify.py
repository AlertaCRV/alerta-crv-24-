import re
import unicodedata
from collections import Counter

from config_loader import load_keywords, load_estados, load_ubicaciones_detalle

_HASHTAG_RE = re.compile(r"#(\w+)", re.UNICODE)
# El lookahead original solo se detenia en puntuacion o fin de texto -- una
# oracion real y muy comun ("municipio Cajigal del estado Sucre", sin coma
# antes de "del estado") capturaba "Cajigal del estado Sucre" completo en
# vez de solo "Cajigal". Caso real (14-08-2026): ese candidato invalido no
# calzaba con ningun municipio de Sucre por coincidencia exacta, pero SI
# por el fallback de sufijo de _resolver_con_posible_adjetivo (pensado para
# "municipio fronterizo Bolivar"), porque "estado Sucre" termina en
# "sucre" -- que ademas es, por coincidencia, el nombre de OTRO municipio
# real del mismo estado. Eso publicaba "municipio: Sucre" para un hecho en
# Yaguaraparo, que en realidad esta en el municipio Cajigal. Se agregan
# "del estado"/"del edo" como delimitadores adicionales del lookahead
# (ademas de la puntuacion existente).
_MUNICIPIO_RE = re.compile(
    r"municipio\s+([A-ZÁÉÍÓÚÑ][\wÀ-ÿ' ]{2,40}?)(?=[.,;:\n]|\s+del\s+estado\b|\s+del\s+edo\b|$)",
    re.IGNORECASE,
)
_PARROQUIA_RE = re.compile(
    r"parroquia\s+([A-ZÁÉÍÓÚÑ][\wÀ-ÿ' ]{2,40}?)(?=[.,;:\n]|\s+del\s+estado\b|\s+del\s+edo\b|\s+del\s+municipio\b|$)",
    re.IGNORECASE,
)

# Una oracion realista que describe el evento y luego da la jerarquia completa
# "parroquia X, municipio Y del estado Z" (a veces con nombres compuestos, p.ej.
# "parroquia J. Vidal Marcano") puede superar facilmente las 25-30 palabras.
VENTANA_PROXIMIDAD_PALABRAS = 35

LISTA_NEGRA_POR_ESTADO = {
    # "avenida bolivar" (singular) no cubria el plural "avenidas Bolivar y
    # Raul Leoni" -- caso real (30-07-2026): un incendio en un centro
    # comercial de Porlamar, estado Nueva Esparta, en la interseccion de
    # las "avenidas Bolivar y Raul Leoni", se publico como alerta del
    # estado Bolivar (duplicado del mismo incendio, ya correctamente
    # publicado como Nueva Esparta via otra fuente que si mencionaba
    # "Margarita").
    "Bolivar": ["simon bolivar", "plaza bolivar", "avenida bolivar", "avenidas bolivar",
                "aeropuerto", "moneda", "billete de", "banco central",
                "libertador simon bolivar"],
    "Sucre": ["antonio jose de sucre", "mariscal sucre", "moneda", "billete de"],
    # "tramo Miranda" es un segmento vial nombrado de la Autopista Regional
    # del Centro (ARC) -- caso real (10-08-2026): un articulo sobre el
    # sismo de magnitud 7.4 de Colombia (que en su propio texto nunca
    # nombra a Miranda como estado) traia pegada una frase de clima/
    # vialidad ajena y sin relacion ("...el colapso de arboles... en el
    # tramo Miranda de la Autopista Regional del Centro (ARC)"), que
    # bastaba para publicar una alerta de sismo en el estado Miranda. La
    # misma frase aparece tambien, de forma legitima, en un articulo real
    # sobre una tormenta en Distrito Capital/Miranda -- pero ese caso ya
    # tiene evidencia solida e independiente ("Los Teques, estado
    # Miranda", "municipio Los Salias"), asi que excluir "tramo Miranda"
    # no le quita esa ubicacion.
    # Ampliada (14-08-2026): un articulo de El Pitazo sobre un incendio real
    # en Caracas ("avenida Los Ilustres, del municipio Libertador") agrega,
    # al final, un parrafo de contexto sobre un incendio DISTINTO y ya
    # resuelto ("Un hecho similar ocurrio... el 7 de agosto... en el sector
    # El Llanito, en Petare, estado Miranda") -- ese parrafo de comparacion
    # bastaba para publicar una alerta duplicada de "incendio" en Miranda,
    # como si el incendio de hoy hubiera ocurrido alli, ademas de la alerta
    # correcta en Distrito Capital/Libertador generada por el mismo
    # articulo. Frase completa y especifica (no solo "Petare", que si es
    # evidencia legitima en articulos reales sobre hechos actuales en ese
    # municipio de Miranda).
    "Miranda": ["francisco de miranda", "generalisimo francisco de miranda", "plaza miranda",
                "tramo miranda", "el llanito, en petare, estado miranda"],
    # Caso real (02-08-2026): una golpiza durante un partido de futbol en
    # Barquisimeto (estado Lara, entre aficion del Deportivo Lara y del
    # Portuguesa FC) tambien se publicaba como alerta de Carabobo -- el
    # equipo visitante se llama "Carabobo FC", y ese nombre de equipo
    # coincide con el alias del estado. El hecho ocurrio unicamente en Lara;
    # "Carabobo FC" no es evidencia de que algo haya pasado en el estado
    # Carabobo. Sin remapeo (no hay a que estado redirigir): se descarta
    # directamente, igual que "aeropuerto"/"moneda" para Bolivar/Sucre.
    #
    # Ampliada (14-08-2026): "Avenida Carabobo" es una via muy comun en
    # ciudades venezolanas (Barquisimeto, entre otras) sin relacion con el
    # estado Carabobo -- dos articulos reales sobre protestas por cortes
    # electricos EN BARQUISIMETO (estado Lara), cuyo punto de encuentro fue
    # la "Avenida Carabobo" local, generaban una alerta duplicada en el
    # estado Carabobo sin que el articulo mencionara ese estado en absoluto
    # (mismo patron que "avenida bolivar" para Bolivar, ver abajo).
    "Carabobo": ["carabobo fc", "avenida carabobo", "avenidas carabobo",
                 "av. carabobo", "av carabobo"],
    # Caso real (31-07-2026): un incendio en el CCCT ("ubicado en el
    # municipio Chacao") se publicaba como Distrito Capital porque el
    # articulo tambien menciona "Caracas" (alias de Distrito Capital) en
    # sentido coloquial del area metropolitana. Chacao/Baruta/El Hatillo son
    # municipios reales de Miranda, nunca de Distrito Capital (cuyo unico
    # municipio es Libertador) -- si el texto los nombra explicitamente, no
    # basta con descartar el match de Distrito Capital: se redirige a
    # Miranda (ver _REMAPEO_MUNICIPIO_A_ESTADO abajo), porque agregarlos
    # como alias de Miranda en estados.yaml no funciona -- casi siempre
    # aparecen como "municipio Chacao", y _es_mencion_subestatal() ya
    # excluye por diseno cualquier mencion "municipio X"/"parroquia X" como
    # evidencia de estado (para no confundir "municipio Sucre" con el
    # estado Sucre), lo que tambien bloquearia a Chacao como evidencia
    # directa de Miranda.
    #
    # Caso real (08-08-2026): un incendio "en el Llanito, municipio Sucre,
    # Petare, Miranda" tambien se publicaba como Distrito Capital porque el
    # articulo menciona "Bombero de Caracas" (nombre del cuerpo de bomberos
    # que respondio, no la ubicacion del hecho). Sucre es el quinto
    # municipio real del area metropolitana de Caracas (junto a Chacao,
    # Baruta y El Hatillo), pero a diferencia de esos tres la frase debe ser
    # "municipio sucre" completa, no "sucre" sola -- Sucre tambien es el
    # nombre de un estado distinto (ver el otro caso ya cubierto arriba en
    # LISTA_NEGRA_POR_ESTADO["Sucre"]).
    "Distrito Capital": ["chacao", "baruta", "el hatillo", "municipio sucre"],
    # Caso real (11-08-2026): dos articulos sobre venezolanos residentes EN
    # COLOMBIA que sobrevivieron al terremoto de magnitud 7.4 que sacudio
    # ese pais ("recuerdan el desastre de La Guaira: <<Me removio todo>>")
    # generaron 2 alertas falsas de sismo en el estado La Guaira -- la
    # unica mencion de "La Guaira" en ambos articulos es una comparacion
    # retrospectiva con un sismo venezolano de hace casi dos meses (el
    # "doble terremoto" de La Guaira/Vargas ya cubierto por
    # _PATRON_RETROSPECTIVA en verify_ai.py), no evidencia de que el sismo
    # de hoy haya ocurrido en Venezuela. El propio texto confirma que el
    # hecho es 100% extranjero: "el terremoto que azoto al sur del
    # [Colombia]... deja al menos 71 muertos", "Pereira, Cali, Manizales,
    # Quibdo y Armenia concentran las situaciones mas criticas". Se
    # verifico contra las 118 fuentes de data/historico_fuentes_texto.jsonl
    # que esta frase es exclusiva de estos 2 articulos (3 instantaneas).
    # Ampliada (14-08-2026): "vargas" es alias directo de La Guaira en
    # estados.yaml (nombre historico del estado), pero tambien es una via
    # muy comun ("Av. Vargas") en ciudades sin relacion con ese estado --
    # un articulo real sobre una marcha por cortes electricos en
    # Barquisimeto (estado Lara) que menciona la sede de Corpoelec "en la
    # Av. Vargas con Carrera 24" (una calle local) generaba una alerta
    # duplicada de La Guaira/municipio Vargas sin ninguna otra mencion de
    # ese estado en el articulo.
    "La Guaira": ["desastre de la guaira", "tragedia de la guaira",
                  "desastre de vargas", "tragedia de vargas",
                  "avenida vargas", "avenidas vargas",
                  "av. vargas", "av vargas"],
    # Caso real (12-08-2026): un articulo sobre jubilados petroleros
    # protestando frente a la sede de Pdvsa La Campiña (Caracas) generaba 2
    # alertas falsas de orden_publico en Falcon y Zulia -- ambos estados solo
    # se mencionan como la PROCEDENCIA de un grupo de manifestantes presentes
    # en esa protesta ("la presencia de manifestantes de Oriente, Falcon y
    # Caracas", "jubilados petroleros de Zulia" cuyo autobus fue detenido "en
    # peaje de Tazon" en su via de regreso), no como la ubicacion de ningun
    # hecho ocurrido en esos estados. El propio articulo nunca describe una
    # protesta, corte de via ni disturbio alguno sucediendo en Falcon o
    # Zulia. Se verifico contra las 94 fuentes de
    # data/historico_fuentes_texto.jsonl que ambas frases son exclusivas de
    # este articulo.
    "Falcon": ["manifestantes de oriente, falcon y caracas"],
    "Zulia": ["jubilados petroleros de zulia en peaje de tazon"],
}

# Ver comentario en LISTA_NEGRA_POR_ESTADO["Distrito Capital"]: cuando el
# match de un estado se descarta por una de estas frases, se reintenta la
# deteccion como si el candidato fuera el estado real indicado aqui (misma
# ventana de proximidad ya encontrada para "Caracas", que ya incluye la
# evidencia de tipo cercana -- el problema nunca fue esa ventana, solo la
# etiqueta de estado resultante).
_REMAPEO_MUNICIPIO_A_ESTADO = {
    "Distrito Capital": {
        "chacao": "Miranda",
        "baruta": "Miranda",
        "el hatillo": "Miranda",
        "municipio sucre": "Miranda",
    },
}

# Lugares reales del lado colombiano de la frontera -- cuando aparecen en
# el texto, son evidencia de que el hecho pudo ocurrir en Colombia, no en
# el estado venezolano fronterizo que tambien se menciona (a menudo solo
# como el dateline del medio: "Frontera con Colombia... Tachira.- Por
# tercer dia..."). Frases especificas ("la guajira, colombia", no
# "guajira" sola) para los nombres que colisionan con lugares reales de
# Venezuela: "Guajira" es tambien un municipio de Zulia, y "Cesar"/
# "Guainia" son substrings de un municipio de Merida ("Julio Cesar Sala")
# y una parroquia de Bolivar ("Guainiamo") respectivamente -- ver
# scripts/validar_configs.py, que no detecta colisiones de substring como
# esta, se verifico a mano contra config/ubicaciones_detalle.json.
#
# Ver _es_evento_extranjero_sin_municipio(): el descarte SOLO aplica si
# el texto no nombra ademas un municipio/parroquia venezolano especifico
# de ese estado -- los grupos armados colombianos (ELN, FARC, Segunda
# Marquetalia...) combaten con frecuencia EN territorio venezolano
# fronterizo, y esos articulos mencionan departamentos/ciudades
# colombianas como contexto sin que el hecho deje de ser una emergencia
# real en Venezuela. Casos reales de control que NO deben descartarse
# (ver tests/casos_clasificacion.jsonl): combates ELN/Segunda Marquetalia
# "en los estados venezolanos Apure y Amazonas" (municipios Romulo
# Gallegos/Maroa, Infobae 07-08-2025); ataque de las FARC contra un
# puesto militar venezolano en "municipio Paez de Apure" (SwissInfo,
# 29-03-2021).
FRONTERA_EXTRANJERA_POR_ESTADO = {
    # Caso real que motivo este mecanismo (01-08-2026): un carro bomba
    # "exploto en la sede de la Policia de Norte de Santander" se
    # publicaba como "Ataque armado en Tachira" -- el texto nunca nombra
    # ningun municipio de Tachira, solo el dateline "Tachira.-" del medio.
    "Tachira": ["norte de santander", "cucuta"],
    "Zulia": ["riohacha", "valledupar", "la guajira, colombia",
              "departamento de la guajira", "cesar, colombia",
              "departamento del cesar"],
    "Apure": ["arauca, colombia", "departamento de arauca", "arauquita",
              "saravena", "puerto carreno", "puerto carreño"],
    "Amazonas": ["vichada", "inirida", "puerto carreno", "puerto carreño",
                 "guainia, colombia", "departamento de guainia"],
}


# Caso real confirmado (01-08-2026, casos de El Colombiano/Proceso.hn sobre
# ataques de las FARC en La Guajira, Colombia): "municipio" detectado no
# siempre es evidencia venezolana confiable. detectar_municipio_parroquia()
# ya usa "Guajira" como alias directo del municipio "Indigena Bolivariano
# Guajira" de Zulia (ver PR #61) -- si el texto dice "La Guajira, Colombia"
# o "departamento de la Guajira", esa MISMA palabra dispara el falso
# municipio venezolano, lo que anularia la salvaguarda de
# _es_evento_extranjero_sin_municipio() con evidencia circular (la palabra
# que prueba que el hecho es colombiano es la misma que "prueba" que es
# venezolano). Estos municipios NUNCA cuentan como salvaguarda cuando el
# estado tambien tiene evidencia de FRONTERA_EXTRANJERA_POR_ESTADO.
_MUNICIPIO_NO_CUENTA_COMO_SALVAGUARDA = {
    "Zulia": {"Indígena Bolivariano Guajira"},
}


def _es_evento_extranjero_sin_municipio(texto_norm, ubicacion, municipio):
    """True si el texto nombra un lugar colombiano de
    FRONTERA_EXTRANJERA_POR_ESTADO para este estado fronterizo Y no se
    detecto ningun municipio/parroquia venezolano especifico confiable --
    ver comentario extenso en FRONTERA_EXTRANJERA_POR_ESTADO sobre por que
    la ausencia de municipio es la condicion clave (no basta con que
    Colombia aparezca mencionada), y en
    _MUNICIPIO_NO_CUENTA_COMO_SALVAGUARDA sobre la excepcion de Guajira."""
    lugares = FRONTERA_EXTRANJERA_POR_ESTADO.get(ubicacion)
    if not lugares:
        return False
    if municipio and municipio not in _MUNICIPIO_NO_CUENTA_COMO_SALVAGUARDA.get(ubicacion, set()):
        return False
    return any(lugar in texto_norm for lugar in lugares)


# A diferencia de _es_evento_extranjero_sin_municipio() (donde la ausencia
# de municipio es la señal clave), aqui el municipio SI aparece en el
# texto -- pero como el lugar de ORIGEN/residencia previa de una victima
# migrante, no como donde ocurrio el hecho. Caso real (11-08-2026, dos
# fuentes -- Nuevo Dia de Falcon y El Periodico de Monagas -- sobre el
# mismo hecho real): "una pareja de venezolanos oriunda del municipio
# Pedro Maria Urena, en el estado Tachira, perdieron la vida en Pereira,
# Colombia" tras el colapso de su vivienda durante el terremoto de
# Colombia generaba una alerta de sismo CRITICO en Tachira, como si el
# colapso hubiera ocurrido alli -- ninguna de las 2 fuentes describe
# ningun dano/afectacion real en Tachira, solo el pueblo natal de las
# victimas. Se verifico contra las 118 fuentes de data/
# historico_fuentes_texto.jsonl que "oriundo/a de(l)" combinado con un
# verbo de fallecimiento y "Colombia" en la misma ventana es exclusivo de
# estas 2 fuentes (mismo hecho real).
# Ampliado (14-08-2026): "Los tres venezolanos procedentes de Barinas que
# permanecian atrapados bajo los escombros del edificio Vanessa en Cali
# fueron hallados sin vida... tras el terremoto de magnitud 7,4 registrado
# en Colombia el lunes 10 de agosto" generaba una alerta de sismo CRITICO
# de magnitud 7.4 en el estado Barinas -- el terremoto ocurrio en Cali,
# Colombia; Barinas es unicamente el estado de origen de las victimas. Ni
# "oriundo/a de(l)"/"natural de(l)" ni la lista de verbos de fallecimiento
# cubrian esta redaccion ("procedentes de", "hallados sin vida"). Se
# verifico contra las 122 fuentes de data/historico_fuentes_texto.jsonl
# que ambas frases nuevas son exclusivas de este articulo.
_ORIGEN_MIGRANTE_RE = re.compile(
    r"\boriund[oa]\s+de(?:l)?\b|\bnatural\s+de(?:l)?\b|\bprocedentes?\s+de(?:l)?\b"
)
_MUERTE_MIGRANTE_EXTRANJERO = [
    "perdio la vida", "perdieron la vida", "murio", "murieron",
    "fallecio", "fallecieron", "quedaron sepultados", "quedo sepultado",
    "hallado sin vida", "hallados sin vida", "hallada sin vida", "halladas sin vida",
    "encontrado sin vida", "encontrados sin vida", "encontrada sin vida", "encontradas sin vida",
]
_VENTANA_FALLECIMIENTO_MIGRANTE = 300


def _es_fallecimiento_migrante_en_extranjero(texto_norm):
    """True si el texto describe, dentro de una ventana razonable tras la
    frase "oriundo/a de(l)", tanto un verbo de fallecimiento como la
    palabra "Colombia" -- patron de un migrante venezolano fallecido en el
    extranjero, donde el unico estado venezolano mencionado es su pueblo
    natal, no el lugar del hecho."""
    match = _ORIGEN_MIGRANTE_RE.search(texto_norm)
    if not match:
        return False
    ventana = texto_norm[match.end():match.end() + _VENTANA_FALLECIMIENTO_MIGRANTE]
    tiene_muerte = any(_contiene_palabra_clave(ventana, m) for m in _MUERTE_MIGRANTE_EXTRANJERO)
    return tiene_muerte and _contiene_palabra_clave(ventana, "colombia")

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
    #
    # Ampliada (08-08-2026): la lista solo cubria el singular -- un articulo
    # real sobre DOS gatos ("Los dos gatos reciben cuidados...") usaba el
    # plural "gatos", no cubierto por "gato" (comparacion de palabra
    # completa, ver _contiene_palabra_clave), y se colaba igual.
    "deslizamiento": ["gato", "gata", "gatos", "gatas", "gatito", "gatita",
                       "gatitos", "gatitas", "gatico", "gatica", "gaticos",
                       "gaticas", "mascota", "mascotas",
                       "perro", "perra", "perros", "perras",
                       "perrito", "perrita", "perritos", "perritas",
                       "felino", "felina", "felinos", "felinas",
                       "canino", "canina", "caninos", "caninas"],
    # Caso real (29-07-2026): un articulo titulado "Hantavirus: Enfermedad
    # totalmente controlada en Venezuela" (una nota que desmiente rumores,
    # sin casos nuevos confirmados por MinSalud) disparaba tipo=salud_publica
    # con severidad critica solo por mencionar fallecidos historicos.
    # Caso real (30-07-2026): un articulo sobre voluntarios armando kits de
    # higiene para "prevenir enfermedades" en zonas ya afectadas (una nota
    # de ayuda humanitaria en curso, sin ningun caso/brote real) disparaba
    # tipo=salud_publica solo por la palabra "enfermedades" en una frase
    # preventiva -- ninguna enfermedad se esta reportando en absoluto.
    # Ampliado (14-08-2026): "una dependencia que nacio en tiempos de la
    # pandemia de Covid-19 y que hoy dia atiende a unos 70 adultos mayores"
    # (nota de una casa parroquial/comedor de Caritas Carupano, sin ningun
    # caso ni alarma sanitaria real) disparaba tipo=salud_publica solo por
    # la palabra "pandemia" usada como referencia historica al origen de
    # un programa social, no una pandemia activa.
    "salud_publica": ["totalmente controlada", "enfermedad controlada",
                       "no existen registros confirmados",
                       "sin registros confirmados", "brote descartado",
                       "descartado el brote", "bajo control total",
                       "prevenir enfermedades", "prevenir la propagacion",
                       "tiempos de la pandemia", "durante la pandemia",
                       "desde la pandemia", "epoca de la pandemia",
                       "época de la pandemia"],
    # Caso real (30-07-2026): "Venezuela entrego nota de protesta a Iran por
    # declaraciones de su canciller" -- una nota de protesta DIPLOMATICA
    # entre gobiernos, sin ninguna relacion con disturbios/orden publico en
    # Venezuela, disparaba tipo=orden_publico solo por la palabra
    # "protesta". Mismo patron que "manifestaciones artisticas" (por eso
    # esa palabra ya se excluye sola de los keywords de tipo): una palabra
    # ambigua entre el sentido de disturbio civil y otro uso idiomatico
    # totalmente distinto. (Ver tambien _es_manifestacion_pacifica_sin_evidencia_fuerte()
    # mas abajo, para el caso de una manifestacion explicitamente pacifica.)
    "orden_publico": ["nota de protesta", "notas de protesta"],
    # Caso real (02-08-2026): "Tragedia en Cumaná: colapso de un árbol...
    # un árbol colapsara y arrastrara postes del tendido eléctrico" -- una
    # muerte por la caida de un arbol (que de paso derribo postes) se
    # publicaba como Falla electrica en Sucre solo por la frase "tendido
    # electrico", sin que el articulo describa ningun corte/interrupcion
    # real del servicio para la poblacion. Se usa la palabra suelta "arbol"
    # (no una frase fija como "colapso de un arbol") porque la ventana de
    # proximidad a la ubicacion puede recortar el texto justo antes de la
    # frase completa, dejando solo el orden invertido ("un arbol colapso")
    # -- un solo token es robusto a cualquier orden/conjugacion.
    "infraestructura_electrica": ["arbol", "árbol", "arboles", "árboles"],
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
    # Si ademas de la nota de protesta diplomatica el articulo describe
    # disturbios reales (poco comun, pero posible en una cobertura mixta),
    # esta evidencia evita descartar el tipo.
    "orden_publico": ["heridos", "detenidos", "saqueo", "saqueos",
                       "disturbios", "tiroteo", "tiroteos",
                       "enfrentamiento", "enfrentamientos"],
    "salud_publica": ["brote confirmado", "casos confirmados",
                       "declaro emergencia sanitaria",
                       "declaró emergencia sanitaria", "cuarentena",
                       "hospitalizados"],
    # Si ademas del arbol caido el articulo SI describe una interrupcion
    # real del servicio electrico (no solo el accidente en si), esta
    # evidencia evita descartar el tipo. Tambien la usa
    # _es_anuncio_corpoelec_sin_falla() mas abajo (evaluada sobre el
    # ARTICULO COMPLETO, no solo la ventana -- ver esa funcion).
    #
    # Ampliada (07-08-2026): varias coberturas reales de fallas electricas
    # describen el hecho con frases que no estaban en esta lista (no usan
    # literalmente "falla electrica"/"sin luz"/etc.) -- "restablecer el
    # suministro/servicio" (personal de Corpoelec reparando una falla ya
    # ocurrida), "fallas en el servicio electrico" (con "en el servicio"
    # entre ambas palabras, no adyacentes como en "falla electrica") y "sin
    # energia electrica" (variante de "sin electricidad"). Sin agregarlas,
    # _es_anuncio_corpoelec_sin_falla() rompia 3 casos reales ya publicados
    # y correctos que si describen una falla real, solo que con estas
    # frases alternativas.
    "infraestructura_electrica": ["apagon", "apagones", "apagón",
                                   "sin luz", "sin electricidad",
                                   "sin energia electrica",
                                   "sin energía eléctrica",
                                   "sin servicio electrico",
                                   "sin servicio eléctrico",
                                   "falla electrica", "falla eléctrica",
                                   "fallas electricas", "fallas eléctricas",
                                   "fallas en el servicio electrico",
                                   "fallas en el servicio eléctrico",
                                   "falla en el servicio electrico",
                                   "falla en el servicio eléctrico",
                                   "restablecer el suministro",
                                   "restablecer el servicio",
                                   "corte de luz", "cortes de luz"],
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


# Caso real (14-08-2026, PASADO_POR_FALLA_TECNICA): "La Guaira coordina la
# reactivacion gradual del turismo playero tras los sismos de junio...
# afectaciones causadas por el evento sismico registrado el pasado 24 de
# junio" -- un articulo sobre la reactivacion turistica semanas despues de
# un sismo ya cubierto en su momento generaba una alerta de sismo nueva en
# La Guaira, como si hubiera ocurrido el dia de publicacion. Igual que la
# correccion de epicentro, "el pasado" describiendo el sismo mismo (no una
# replica nueva) es una señal decisiva de que se refiere a un evento ya
# ocurrido, sin importar cuanta evidencia fuerte de sismo (magnitud,
# funvisis, sacudio...) tenga el articulo -- esa evidencia describe el
# sismo original, no uno nuevo. No se usa como palabra suelta ("el pasado"
# aparece con frecuencia en sentidos no relacionados) sino solo cuando
# aparece cerca de una mencion de sismo/terremoto, en cualquier orden.
_SISMO_FECHA_PASADA_RE = re.compile(
    r"\b(?:sismos?|sismic[oa]|s[ií]smic[oa]|terremotos?)\b[^.]{0,60}\bel\s+pasado\b"
    r"|\bel\s+pasado\b[^.]{0,60}\b(?:sismos?|sismic[oa]|s[ií]smic[oa]|terremotos?)\b",
    re.IGNORECASE,
)


def _es_referencia_sismo_fecha_pasada(texto_norm):
    return _SISMO_FECHA_PASADA_RE.search(texto_norm) is not None


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

# Caso real (08-08-2026): "Desde el 31 de julio hasta el 07 de agosto, segun
# registros del Diario La Prensa de Lara, se contabilizan al menos... 15
# manifestaciones por la crisis electrica en el pais" -- un articulo-tally
# retrospectivo de La Prensa de Lara, reproducido casi textual por otro
# medio (Turimiquire), resumiendo protestas y fallas electricas YA
# ocurridas en 7 estados distintos durante la semana previa (cada una con
# su propia fecha explicita: "04 de agosto", "06 de agosto"...), generaba
# 6 alertas nuevas (orden_publico y infraestructura_electrica en Lara,
# Aragua, Carabobo, Anzoategui, Distrito Capital) el dia de la republicacion
# como si los hechos estuvieran ocurriendo ese mismo dia. Mismo patron que
# "meses de espera"/"asi aprendieron": un articulo que se encuadra
# explicitamente como un recuento de un RANGO de fechas ya transcurrido, no
# el reporte de un hecho puntual de hoy. Se verifico contra las 81 fuentes
# de data/historico_fuentes_texto.jsonl que esta frase, con fechas
# variables, no aparece en ningun otro caso real ya publicado.
_RANGO_FECHAS_RETROSPECTIVO_RE = re.compile(
    r"\bdesde el \d{1,2} de \w+ hasta el \d{1,2} de \w+\b", re.IGNORECASE,
)

# Caso real (10-08-2026): "Bomberos sofocan 26 incendios forestales en
# Trujillo. Las labores de combate incluyeron la atención de 9 incendios de
# gran magnitud" -- un articulo-tally que resume, en un numero acumulado, un
# operativo de varios dias YA sofocado/controlado (el mismo incendio
# forestal de Trujillo/Carache ya cubierto en dias previos con
# actualizaciones puntuales) -- no describe un incendio nuevo puntual de
# hoy, sino un cierre/resumen numerico. Mismo principio que el rango de
# fechas y "meses de espera": un articulo enmarcado como recuento numerico
# de eventos YA resueltos no es un hecho nuevo, sin importar el tipo de
# emergencia de fondo. Umbral de 5+ (igual que _NUMERO_FALLECIDOS_RE en
# verify_ai.py) para no descartar un reporte legitimo de un puñado de
# incendios simultaneos detectados el mismo dia. Se verifico contra el
# corpus completo que "N incendios" (N>=5) no aparece en ningun otro caso
# real ya publicado.
_RESUMEN_TALLY_INCENDIOS_RE = re.compile(
    r"\b(cinco|seis|siete|ocho|nueve|diez|[5-9]|\d{2,})\s+incendios\b",
    re.IGNORECASE,
)


def _es_articulo_retrospectivo_larga_duracion(texto_norm):
    if any(_contiene_palabra_clave(texto_norm, frase) for frase in _ARTICULO_RETROSPECTIVO_LARGA_DURACION):
        return True
    if _RANGO_FECHAS_RETROSPECTIVO_RE.search(texto_norm) is not None:
        return True
    return _RESUMEN_TALLY_INCENDIOS_RE.search(texto_norm) is not None


# Caso real (30-07-2026): "Aumentan los casos de enfermedades diarreicas en
# Venezuela" -- un boletin epidemiologico NACIONAL que compara la tasa de
# contagio de TODOS los estados contra la media nacional (una tabla, no el
# reporte de un evento en un estado concreto) generaba una alerta de
# salud_publica en el estado que por casualidad quedaba mas cerca de la
# palabra clave dentro de la ventana de proximidad (el "primero por debajo
# de la media" en el listado, sin relacion real con ningun hecho en ese
# estado). El propio articulo cita al Ministerio de Salud descartando
# explicitamente cualquier alarma sanitaria por el repunte, y lo califica
# de normal para la temporada de lluvias. A diferencia de
# _CONTEXTO_CONFLICTIVO_POR_TIPO (que solo mira la ventana de proximidad a
# la ubicacion), esta señal -- el articulo entero es una tabla estadistica
# sin alarma, no una emergencia localizada -- es una propiedad del articulo
# completo, no de la mencion puntual de un estado en particular.
_MARCADORES_BOLETIN_ESTADISTICO_SALUD = [
    "boletin epidemiologico", "media nacional",
    "por cada 100.000 habitantes", "por cada 100 mil habitantes",
]
_MARCADORES_SIN_ALARMA_SANITARIA = [
    "descarta alguna alarma sanitaria", "descarta cualquier alarma sanitaria",
    "descarta alarma sanitaria", "sin alarma sanitaria",
    "no representa alarma sanitaria", "no genera alarma sanitaria",
]

# Caso real (14-08-2026, PASADO_POR_FALLA_TECNICA): "la Fundacion
# Venezolana de Investigaciones Sismologicas (Funvisis), a traves del
# Servicio Sismologico y de Alerta de Tsunami Venezolano (Ssatv), reporto
# un total de 122 eventos telúricos... entre el 7 y el 13 de agosto"
# disparaba tipo=tsunami en Tachira (un estado sin costa) solo porque la
# palabra clave "alerta de tsunami" es parte del nombre oficial de la
# division de Funvisis que emite boletines sismicos rutinarios -- el
# articulo es un resumen semanal de sismicidad menor, sin ninguna ola ni
# evacuacion costera real. Igual que el boletin estadistico de salud, esta
# senal se evalua sobre el ARTICULO COMPLETO (el nombre institucional
# puede quedar lejos, en palabras, de la ubicacion detectada). Se verifico
# contra las 122 fuentes de data/historico_fuentes_texto.jsonl que la
# frase institucional es exclusiva de este articulo.
_NOMBRE_INSTITUCIONAL_SSATV = "servicio sismologico y de alerta de tsunami"
_EVIDENCIA_FUERTE_TSUNAMI_REAL = [
    "ola gigante", "maremoto", "evacuacion costera", "evacuación costera",
]


def _es_nombre_institucional_tsunami_sin_evidencia_real(texto_norm):
    if not _contiene_palabra_clave(texto_norm, _NOMBRE_INSTITUCIONAL_SSATV):
        return False
    return not any(_contiene_palabra_clave(texto_norm, f) for f in _EVIDENCIA_FUERTE_TSUNAMI_REAL)


def _es_boletin_estadistico_salud_sin_alarma(texto_norm):
    if not any(_contiene_palabra_clave(texto_norm, m) for m in _MARCADORES_BOLETIN_ESTADISTICO_SALUD):
        return False
    if not any(_contiene_palabra_clave(texto_norm, m) for m in _MARCADORES_SIN_ALARMA_SANITARIA):
        return False
    fuerte = _EVIDENCIA_FUERTE_POR_TIPO.get("salud_publica", [])
    return not any(_contiene_palabra_clave(texto_norm, f) for f in fuerte)


# Caso real (02-08-2026): "Oposición se concentró en la Av. Juncal de
# Maturín... Contamos con una gran participación de ciudadanos que acudieron
# de manera pacífica a esta concentración. Agradecemos el respaldo y el
# comportamiento cívico demostrado" -- una manifestacion politica
# explicitamente pacifica (el propio articulo lo afirma) disparaba
# tipo=orden_publico solo por la palabra "manifestantes"/"protesta". La
# aclaracion de que fue pacifica aparecio varios parrafos despues de la
# mencion del estado -- fuera de la ventana de proximidad de
# _CONTEXTO_CONFLICTIVO_POR_TIPO -- asi que, igual que el boletin
# estadistico de salud, esta señal se evalua sobre el ARTICULO COMPLETO, no
# solo la ventana cercana a la ubicacion.
_MARCADORES_MANIFESTACION_PACIFICA = [
    "de manera pacifica", "de manera pacífica", "manera pacifica",
    "manera pacífica", "pacificamente", "pacíficamente",
    "comportamiento civico", "comportamiento cívico",
]


def _es_manifestacion_pacifica_sin_evidencia_fuerte(texto_norm):
    if not any(_contiene_palabra_clave(texto_norm, m) for m in _MARCADORES_MANIFESTACION_PACIFICA):
        return False
    fuerte = _EVIDENCIA_FUERTE_POR_TIPO.get("orden_publico", [])
    return not any(_contiene_palabra_clave(texto_norm, f) for f in fuerte)


# Caso real (12-08-2026, PASADO_POR_FALLA_TECNICA): "Andres Velasquez se
# suma llamado a manifestar este viernes por apagones... El exgobernador
# del estado Bolivar... ha expresado su respaldo a la 'Gran Protesta
# Nacional' convocada en rechazo a los constantes cortes electricos que
# afectan a Venezuela" disparaba DOS alertas falsas -- infraestructura_
# electrica Y orden_publico -- en el estado Bolivar. "Bolivar" solo nombra
# el cargo POLITICO PASADO del dirigente citado, no la ubicacion del hecho
# (nunca se describe ningun corte electrico ni disturbio en Bolivar en
# particular). Y el hecho en si es la mera ADHESION de un dirigente a una
# protesta FUTURA todavia por ocurrir ("convocada", "este viernes"), no un
# apagon ni una manifestacion ya en curso -- por eso ninguna de las dos
# palabras clave que dispararon el tipo ("apagones", "protesta") describe
# un hecho real y localizado.
#
# "apagon"/"apagones" estan en _EVIDENCIA_FUERTE_POR_TIPO de infraestructura_
# electrica (son evidencia fuerte de un corte REAL en la mayoria de los
# casos), pero aqui son precisamente la palabra ambigua a descartar -- son
# la RAZON citada del llamado a protestar, no la descripcion de un corte en
# curso. Por eso este filtro usa su propia lista de evidencia fuerte, sin
# "apagon"/"apagones", en vez de reutilizar _EVIDENCIA_FUERTE_POR_TIPO
# directamente.
_MARCADORES_CONVOCATORIA_PROTESTA_FUTURA = [
    "llamado a manifestar", "gran protesta nacional",
]
_EVIDENCIA_FUERTE_SIN_CONVOCATORIA = [
    "sin luz", "sin electricidad", "sin energia electrica",
    "sin energía eléctrica", "sin servicio electrico",
    "sin servicio eléctrico", "falla electrica", "falla eléctrica",
    "fallas electricas", "fallas eléctricas", "corte de luz",
    "cortes de luz",
    "heridos", "detenidos", "saqueo", "saqueos", "disturbios",
    "tiroteo", "tiroteos", "enfrentamiento", "enfrentamientos",
]


def _es_convocatoria_protesta_futura_sin_hecho_actual(texto_norm):
    if not any(_contiene_palabra_clave(texto_norm, m) for m in _MARCADORES_CONVOCATORIA_PROTESTA_FUTURA):
        return False
    return not any(_contiene_palabra_clave(texto_norm, f) for f in _EVIDENCIA_FUERTE_SIN_CONVOCATORIA)


# Caso real (12-08-2026): "Artefacto explosivo en centro comercial de
# Baruta" -- el titular sensacionalista disparaba tipo=explosion via la
# palabra clave "artefacto explosivo", pero el propio texto aclara, varios
# parrafos mas adelante (fuera de la ventana de proximidad a la ubicacion,
# por eso no basta con _CONTEXTO_CONFLICTIVO_POR_TIPO), que el "artefacto"
# fue en realidad "la activacion de un cartucho lacrimogeno", que el
# incidente fue "totalmente controlado" y que "no se reportaron personas
# afectadas". Un cartucho lacrimogeno no es un explosivo real -- igual que
# _es_anuncio_corpoelec_sin_falla, esta señal se evalua sobre el ARTICULO
# COMPLETO.
_MARCADORES_CARTUCHO_LACRIMOGENO = ["cartucho lacrimogeno", "cartuchos lacrimogenos"]


def _es_cartucho_lacrimogeno_sin_explosivo_real(texto_norm):
    if not any(_contiene_palabra_clave(texto_norm, m) for m in _MARCADORES_CARTUCHO_LACRIMOGENO):
        return False
    fuerte = _EVIDENCIA_FUERTE_POR_TIPO.get("explosion", [])
    return not any(_contiene_palabra_clave(texto_norm, f) for f in fuerte)


# Caso real (07-08-2026): "Gobernador Luis Caldera hizo entrega de 376
# nuevos transformadores que seran distribuidos en todo el Zulia... para
# fortalecer y optimizar el sistema electrico" -- un anuncio POSITIVO de
# entrega de equipos (ninguna falla en curso) se publicaba como Falla
# electrica en Zulia solo porque el texto nombra a "Corpoelec" (la empresa
# estatal), la unica palabra clave de tipo presente. "corpoelec" es solo el
# nombre de la compañia -- aparece tanto en coberturas de fallas reales
# como en anuncios corporativos/positivos sin relacion con ningun corte.
#
# A diferencia de "arbol" (ver _CONTEXTO_CONFLICTIVO_POR_TIPO), que se
# evalua solo en la ventana de proximidad porque el accidente y su posible
# evidencia de corte suelen estar en la misma frase corta, "corpoelec" se
# evalua sobre el ARTICULO COMPLETO: es comun que se mencione a la empresa
# solo al final (voceria/atribucion) mientras la evidencia real de la
# falla (p.ej. "apagones prolongados") aparece varios parrafos antes, fuera
# de esa ventana -- igual que la manifestacion pacifica y el boletin de
# salud sin alarma.
def _es_anuncio_corpoelec_sin_falla(texto_norm):
    if not _contiene_palabra_clave(texto_norm, "corpoelec"):
        return False
    fuerte = _EVIDENCIA_FUERTE_POR_TIPO.get("infraestructura_electrica", [])
    return not any(_contiene_palabra_clave(texto_norm, f) for f in fuerte)


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

# "muerto(s)/muerta(s)" y "ahogado(s)/ahogada(s)" son ambiguos entre
# personas y animales (a diferencia de "fallecidos"/"asesinado", que en la
# prensa venezolana solo se usan para personas). Caso real (05-08-2026):
# "Pozos secos y animales muertos: Alta Guajira comienza a sufrir los
# estragos de El Nino" -- articulo integro sobre mortalidad de ganado por
# sequia, sin ninguna victima humana, se publico con severidad CRITICA
# solo por la palabra "muertos" referida a los animales.
_PALABRAS_MUERTE_AMBIGUA_ANIMAL = {
    "muerto", "muerta", "muertos", "muertas",
    "murio", "murió",
    "ahogado", "ahogada", "ahogados", "ahogadas",
}
_ANIMAL_RE = re.compile(
    r"\b(animal|animales|ganado|reses|res|semovientes|vaca|vacas|"
    r"cabras|ovejas|aves|gallinas|peces|mascotas)\b"
)
_VENTANA_CONTEXTO_ANIMAL_CHARS = 30


def _muerte_es_de_animal(texto_norm, inicio_match, fin_match):
    inicio_ventana = max(0, inicio_match - _VENTANA_CONTEXTO_ANIMAL_CHARS)
    fin_ventana = min(len(texto_norm), fin_match + _VENTANA_CONTEXTO_ANIMAL_CHARS)
    fragmento = texto_norm[inicio_ventana:fin_ventana]
    return _ANIMAL_RE.search(fragmento) is not None


def _contiene_palabra_clave_no_negada(texto_norm, palabra):
    """Como _contiene_palabra_clave, pero descarta la coincidencia si esta
    negada a pocas palabras de distancia (p.ej. 'sin afectados que lamentar',
    'no se reportan heridos') -- evita que una palabra clave de severidad
    dispare un nivel que el propio texto esta descartando. Tambien descarta,
    para las palabras de muerte ambiguas entre persona/animal, las
    coincidencias pegadas a una palabra de contexto animal (ver
    _PALABRAS_MUERTE_AMBIGUA_ANIMAL)."""
    palabra_norm = _normalizar(palabra)
    patron = r"\b" + re.escape(palabra_norm) + r"\b"
    for m in re.finditer(patron, texto_norm):
        inicio_ventana = max(0, m.start() - _VENTANA_NEGACION_CHARS)
        fragmento_previo = texto_norm[inicio_ventana:m.start()]
        if _NEGACION_RE.search(fragmento_previo):
            continue
        if palabra_norm in _PALABRAS_MUERTE_AMBIGUA_ANIMAL and _muerte_es_de_animal(
            texto_norm, m.start(), m.end()
        ):
            continue
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


# Caso real (14-08-2026): un mapa de Primero Justicia, compartido/difundido
# por varios medios ("PJ compartió un mapa de Venezuela con nueve estados
# resaltados...", "difundió una serie de mapas detallando la incidencia de
# los cortes eléctricos en los distintos estados... según el reclamo de
# Primero Justicia, los estados Anzoátegui, Apure, Lara..."), enumera 9-12
# estados a la vez bajo la misma condición genérica (un rango de horas de
# racionamiento atribuido en bloque a toda la lista), sin ningún detalle
# local específico para la mayoría de ellos -- ni una cita textual de un
# residente, ni un municipio/parroquia nombrado. Ese tipo de nota-resumen
# de un tercero (partido, ONG, organismo) generaba alertas nuevas en
# Anzoátegui, Miranda y Nueva Esparta (y una mención redundante de Bolívar,
# ya cubierto por una fuente dedicada -- Primicia) sin evidencia específica
# de ninguno de esos estados en particular -- a diferencia de, por ejemplo,
# Distrito Capital en el mismo artículo ("comunidades del municipio
# Libertador de Caracas denuncian fallas eléctricas"), que sí nombra un
# municipio real. El objetivo es preferir cobertura de prensa regional/
# local (que sí describe el hecho en el lugar) sobre notas-resumen de
# terceros que solo reparten una misma cifra/reclamo entre muchos estados.
#
# La señal se ancla por PROXIMIDAD a la mención puntual de cada estado (no
# a "el artículo contiene la frase en algún lado"): un artículo puede tener
# tanto una cita del mapa de un tercero COMO, en otro párrafo totalmente
# distinto, cobertura local real y especifica de un hecho propio (caso
# real: "Andrés Velásquez: Apagones se deben a la corrupción..." -- abre
# con una protesta real y puntual "a las afueras de la sede de la
# Corporación Eléctrica Nacional en Caracas", y solo mas adelante resume el
# mapa de PJ). Si se descartara el articulo entero por contener la frase
# del mapa en algun lado, se perderia esa cobertura real. Por eso se usa
# la misma ventana de proximidad (35 palabras) que ya usa _ventana_cerca
# para el tipo de emergencia -- si la mencion del estado esta a mas de 35
# palabras de cualquier marcador de reclamo de tercero, no se considera
# parte de esa lista generica.
_MARCADORES_RECLAMO_TERCERO_MULTIESTADO = [
    "compartió un mapa", "compartio un mapa",
    "difundió una serie de mapas", "difundio una serie de mapas",
    "segun el reclamo de", "según el reclamo de",
    "entidades mas perjudicadas", "entidades más perjudicadas",
]
_MIN_ESTADOS_RESUMEN_MULTIESTADO = 5


def _es_articulo_resumen_multiestado_de_terceros(texto_norm, estados):
    if not any(_contiene_palabra_clave(texto_norm, m) for m in _MARCADORES_RECLAMO_TERCERO_MULTIESTADO):
        return False
    encontrados = 0
    for alias in estados.values():
        candidatos = set(alias)
        if any(_contiene_palabra_clave(texto_norm, c) for c in candidatos):
            encontrados += 1
            if encontrados >= _MIN_ESTADOS_RESUMEN_MULTIESTADO:
                return True
    return False


def _posiciones_de_marcadores(tokens, marcadores):
    posiciones = []
    for marcador in marcadores:
        m_tokens = _normalizar(marcador).split()
        n = len(m_tokens)
        for i in range(len(tokens) - n + 1):
            if tokens[i:i + n] == m_tokens:
                posiciones.append(i)
    return posiciones


def _mencion_cerca_de_marcador(pos, posiciones_marcadores, radio=VENTANA_PROXIMIDAD_PALABRAS):
    return any(abs(pos - mp) <= radio for mp in posiciones_marcadores)


def _ventana_sin_evidencia_local_especifica(ventana):
    """True si la ventana (ya recortada a la proximidad de esta mencion del
    estado) no nombra ningun municipio/parroquia especifico -- la unica
    señal de que el articulo describe algo mas que la mera pertenencia a
    la lista generica del tercero (ver _es_articulo_resumen_multiestado_
    de_terceros). Los signos de puntuacion (comillas de una cita textual)
    no sirven aqui porque `ventana` se arma con tokens ya sin puntuacion
    (ver _tokens/_ventana_cerca)."""
    return not (_contiene_palabra_clave(ventana, "municipio") or _contiene_palabra_clave(ventana, "parroquia"))


def _detectar_ubicacion_texto_plano(texto, estados):
    texto_norm = _normalizar(texto)
    palabras_tipo = [p for lista in load_keywords()["tipos"].values() for p in lista]
    tokens = _tokens(texto)
    posiciones_estados = _posiciones_de_estados(tokens, estados)
    posiciones_marcadores = (
        _posiciones_de_marcadores(tokens, _MARCADORES_RECLAMO_TERCERO_MULTIESTADO)
        if _es_articulo_resumen_multiestado_de_terceros(texto_norm, estados)
        else []
    )
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
            frase_negra = next((f for f in lista_negra if f in texto_norm), None)
            if frase_negra is not None:
                estado_real = _REMAPEO_MUNICIPIO_A_ESTADO.get(nombre_estado, {}).get(frase_negra)
                if estado_real is None:
                    continue
                # frase_negra (p.ej. "municipio Baruta") ya es evidencia
                # fuerte y especifica del municipio real -- a diferencia de
                # "caracas", que es solo un alias coloquial del area
                # metropolitana. Se intenta anclar la ventana ahi primero
                # (permitir_subestatal=True: aqui "municipio Baruta" es
                # precisamente la evidencia, no una ambiguedad a filtrar),
                # porque suele estar mas cerca de los detalles reales del
                # hecho que la mencion de "Caracas" (a menudo solo el
                # nombre de los bomberos/policia que respondieron, varias
                # frases despues). Caso real: incendio en Las
                # Mercedes/Baruta (02-08-2026), "lesionados" a ~30 palabras
                # de "municipio Baruta" pero a mas de 35 de la unica
                # mencion de "Caracas" del articulo.
                ventana = _ventana_cerca(
                    tokens, frase_negra, palabras_tipo, posiciones_estados,
                    permitir_subestatal=True,
                ) or _ventana_cerca(tokens, candidato_norm, palabras_tipo, posiciones_estados)
                if not ventana:
                    # Ninguna de las dos ventanas encontro el tipo cerca --
                    # si el tipo SI aparece en algun otro punto del
                    # articulo, no hay razon para descartar el estado por
                    # completo: se usa el texto completo como ventana,
                    # igual que ya se hace cuando la ubicacion viene de un
                    # hashtag (ventana=None).
                    if not any(_contiene_palabra_clave(texto_norm, p) for p in palabras_tipo):
                        break
                resultado.append((estado_real, ventana))
                break

            ventana, pos = _ventana_cerca_con_posicion(tokens, candidato_norm, palabras_tipo, posiciones_estados)
            if ventana:
                if (posiciones_marcadores
                        and _mencion_cerca_de_marcador(pos, posiciones_marcadores)
                        and _ventana_sin_evidencia_local_especifica(ventana)):
                    # Esta mencion puntual (este alias en particular) solo
                    # tiene evidencia generica de lista -- se prueba otro
                    # alias del MISMO estado (p.ej. "Caracas" ademas de
                    # "Distrito Capital") antes de descartarlo del todo, en
                    # vez de cortar la busqueda en el primer alias probado.
                    continue
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
    homonimo es la ubicacion del evento.

    Tambien cuenta 'municipio fronterizo Bolivar'/'parroquia foranea X' --
    un unico adjetivo intercalado entre el calificador y el nombre propio,
    patron real en cobertura de zonas fronterizas (ver
    docs/roadmap_evolucion.md, auditoria 09-08-2026: 'municipio fronterizo
    Bolivar', Diario La Nacion Tachira, generaba evidencia falsa del
    estado Bolivar en un articulo que nunca menciona ese estado)."""
    if pos > 0 and tokens[pos - 1] in _CALIFICADORES_SUBESTATALES:
        return True
    return pos > 1 and tokens[pos - 2] in _CALIFICADORES_SUBESTATALES


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


def _ventana_cerca(tokens, candidato_norm, palabras_tipo, posiciones_estados=None,
                    permitir_subestatal=False):
    """Devuelve la ventana de texto alrededor de candidato_norm si contiene
    alguna palabra clave de tipo, o None si no hay ninguna cerca.

    Si se pasan posiciones_estados (posiciones de TODAS las menciones de
    estados en el texto), la ventana se recorta para no cruzar la mencion
    mas cercana de OTRO estado, evitando que un articulo que habla de varios
    estados mezcle detalles (tipo/severidad) de uno con los de otro. Las
    menciones repetidas del MISMO estado (p.ej. el nombre de un medio local
    como "Zulia Sin Censura") no cuentan como frontera -- de lo contrario
    la ventana podia cortarse antes de llegar a un dato clave (una muerte,
    heridos) que esta mas cerca de esa repeticion que de un estado distinto.

    permitir_subestatal=True omite el filtro de "municipio X"/"parroquia X"
    (ver _es_mencion_subestatal) -- solo tiene sentido cuando candidato_norm
    es precisamente un municipio real de LISTA_NEGRA_POR_ESTADO (p.ej.
    "baruta"), casi siempre mencionado como "municipio Baruta": ahi la
    mencion subestatal NO es ambigua, es la evidencia misma que motivo el
    remapeo (ver _REMAPEO_MUNICIPIO_A_ESTADO)."""
    ventana, _ = _ventana_cerca_con_posicion(
        tokens, candidato_norm, palabras_tipo, posiciones_estados, permitir_subestatal,
    )
    return ventana


def _ventana_cerca_con_posicion(tokens, candidato_norm, palabras_tipo, posiciones_estados=None,
                                 permitir_subestatal=False):
    """Como _ventana_cerca, pero tambien devuelve la posicion (indice de
    token) de la mencion puntual que genero la ventana -- (ventana,
    posicion), o (None, None) si no hay ninguna cerca. Se usa donde ademas
    de la ventana hace falta saber DONDE en el texto esta esa mencion
    especifica (ver _mencion_cerca_de_marcador)."""
    candidato_tokens = candidato_norm.split()
    n = len(candidato_tokens)
    posiciones = [
        i for i, t in enumerate(tokens)
        if tokens[i:i + n] == candidato_tokens
        and (permitir_subestatal or not _es_mencion_subestatal(tokens, i))
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
                return ventana, pos
    return None, None


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

# Mismo problema que "Venezuela", pero con el nombre de OTRO estado: varios
# municipios/parroquias son, por coincidencia, homonimos de un estado
# distinto al que pertenecen y unicos a nivel nacional (pasan el chequeo de
# ambiguedad de _conteos_globales_ubicaciones porque solo hay uno en todo
# el pais con ese nombre) -- p.ej. la parroquia "Monagas" del municipio
# Almirante Padilla, Zulia. Caso real (07-08-2026): un articulo-resumen
# nacional sobre protestas por apagones en "Aragua, Bolivar, Carabobo,
# Cojedes, Distrito Capital, La Guaira, Monagas, Zulia" (una simple lista
# de estados afectados, sin relacion alguna con la isla de Toas) genero
# una alerta en Zulia con "Municipio Almirante Padilla, Parroquia Monagas"
# solo porque la palabra "Monagas" -- ahi nombrando al estado vecino, no a
# la parroquia -- aparecia en algun punto del texto completo. Igual que con
# "Venezuela", una mencion aislada del nombre de un estado casi siempre se
# refiere al estado, nunca a la subdivision homonima de otro.
def _nombres_estados_norm():
    global _nombres_estados_norm_cache
    if _nombres_estados_norm_cache is None:
        _nombres_estados_norm_cache = {_normalizar(n) for n in load_estados()}
    return _nombres_estados_norm_cache


_nombres_estados_norm_cache = None

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
        if normalizado == _NOMBRE_PAIS_NORM or normalizado in _nombres_estados_norm():
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
            if normalizado in _nombres_estados_norm():
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
        if normalizado == _NOMBRE_PAIS_NORM or normalizado in _nombres_estados_norm():
            continue
        if _contiene_palabra_clave(texto_norm, normalizado):
            municipio_unico, parroquia_unica = ocurrencias[0]
            return parroquia_unica, municipio_unico
    return None, None


def _resolver_con_posible_adjetivo(candidato, variantes_por_nombre):
    """Resuelve `candidato` (ya normalizado, capturado por _MUNICIPIO_RE o
    _PARROQUIA_RE) contra {nombre_normalizado: original}. Prueba primero
    una coincidencia exacta y, si falla, si el nombre real conocido es el
    SUFIJO del candidato -- cubre un adjetivo intercalado entre el
    calificador y el nombre propio (p.ej. 'municipio fronterizo Bolivar'
    captura 'fronterizo bolivar', que termina en 'bolivar', el nombre
    real). Solo se acepta si exactamente una variante conocida es sufijo
    -- si mas de una calza (ambiguo), no se adivina.

    Caso real (09-08-2026): 'municipio fronterizo Bolivar' (Diario La
    Nacion Tachira, San Antonio del Tachira) no calzaba con ningun
    municipio de Tachira porque el candidato capturado ('fronterizo
    bolivar') no coincidia exacto con 'bolivar' -- el sistema caia al
    fallback de busqueda libre, que encontraba 'Rafael Urdaneta' (un
    barrio homonimo de OTRO municipio real de Tachira) como unico
    municipio mencionado, en vez del municipio Bolivar que el texto
    nombra explicitamente."""
    directo = variantes_por_nombre.get(candidato)
    if directo is not None:
        return directo
    coincidencias = {
        original for variante, original in variantes_por_nombre.items()
        if variante and candidato.endswith(" " + variante)
    }
    if len(coincidencias) == 1:
        return next(iter(coincidencias))
    return None


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
        municipio_encontrado = _resolver_con_posible_adjetivo(candidato, _municipios_por_variante(detalle))

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
            parroquia_encontrada = _resolver_con_posible_adjetivo(
                candidato, _parroquias_de(detalle, municipio_encontrado)
            )
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
    # Igual que el retrospectivo: una convocatoria a una protesta FUTURA
    # (aun no ocurrida) no es un hecho nuevo, sin importar si dispara
    # tipo=orden_publico o tipo=infraestructura_electrica (ver comentario en
    # _es_convocatoria_protesta_futura_sin_hecho_actual).
    if _es_convocatoria_protesta_futura_sin_hecho_actual(texto_completo_norm):
        return []
    tipos_encontrados = []
    for tipo, palabras in load_keywords()["tipos"].items():
        for palabra in palabras:
            if _contiene_palabra_clave(fuente_norm, palabra):
                if tipo == "sismo" and _es_correccion_epicentro_retrospectiva(texto_completo_norm):
                    break
                if tipo == "sismo" and _es_referencia_sismo_fecha_pasada(texto_completo_norm):
                    break
                if tipo == "tsunami" and _es_nombre_institucional_tsunami_sin_evidencia_real(texto_completo_norm):
                    break
                if tipo == "salud_publica" and _es_boletin_estadistico_salud_sin_alarma(texto_completo_norm):
                    break
                if tipo == "orden_publico" and _es_manifestacion_pacifica_sin_evidencia_fuerte(texto_completo_norm):
                    break
                if tipo == "infraestructura_electrica" and _es_anuncio_corpoelec_sin_falla(texto_completo_norm):
                    break
                if tipo == "explosion" and _es_cartucho_lacrimogeno_sin_explosivo_real(texto_completo_norm):
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

    texto_norm = _normalizar(item["texto"])
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
        if _es_evento_extranjero_sin_municipio(texto_norm, ubicacion, nuevo["municipio"]):
            continue
        if _es_fallecimiento_migrante_en_extranjero(texto_norm):
            continue
        resultado.append(nuevo)

    if not resultado:
        item["ubicacion"] = None
        item["tipos"] = []
        item["severidad"] = "sin_clasificar"
        item["municipio"] = None
        item["parroquia"] = None
        return [item]
    return resultado


def es_relevante(item):
    return bool(item["ubicacion"]) and bool(item["tipos"])
