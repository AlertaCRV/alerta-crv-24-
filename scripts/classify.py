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
    "Distrito Capital": [
        "chacao", "baruta", "el hatillo", "municipio sucre",
        # Caso real (18-08-2026, PASADO_POR_FALLA_TECNICA): un explicativo
        # nacional sobre el deficit de generacion electrica traia como unica
        # mencion de Distrito Capital el dateline "Caracas.-" seguido de una
        # frase sobre la crisis a nivel PAIS ("Una ola de racionamientos
        # electricos indiscriminados afecta a los venezolanos..."), sin
        # ningun detalle especifico de una falla en Caracas. Se verifico
        # contra las 168 fuentes de data/historico_fuentes_texto.jsonl que
        # la frase es exclusiva de este articulo.
        "una ola de racionamientos electricos indiscriminados",
    ],
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
                  "av. vargas", "av vargas",
                  # Caso real (18-08-2026, PASADO_POR_FALLA_TECNICA): un
                  # articulo sobre inundaciones/deslizamientos reales en
                  # Caracas (Distrito Capital) -- muertes en La Vega,
                  # desalojos en La Pastora, desbordamiento del Guaire en
                  # Las Mercedes -- generaba una alerta separada y falsa de
                  # deslizamiento en La Guaira solo porque la Gobernacion de
                  # ese estado envio equipos de apoyo a Caracas ("equipos...
                  # de la Gobernacion de La Guaira"). Sin remapeo: el hecho
                  # ya queda cubierto bajo Distrito Capital via la mencion
                  # de "Caracas"/parroquias especificas, asi que basta con
                  # descartar el candidato de La Guaira.
                  "de la gobernacion de la guaira"],
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
    "Zulia": [
        "jubilados petroleros de zulia en peaje de tazon",
        # Caso real (18-08-2026, PASADO_POR_FALLA_TECNICA): un explicativo
        # nacional sobre el deficit de generacion electrica ("¿Cuando
        # terminaran los apagones en Venezuela?") menciona Zulia solo como
        # unidad de comparacion numerica ("el deficit... es similar al
        # consumo que exige todo el estado Zulia"), sin describir ninguna
        # falla electrica puntual en ese estado. Se verifico contra las 168
        # fuentes de data/historico_fuentes_texto.jsonl que la frase es
        # exclusiva de este articulo.
        "es similar al consumo que exige todo el estado zulia",
        # Caso real (18-08-2026, PASADO_POR_FALLA_TECNICA): un explicativo
        # sobre el calor de agosto en Venezuela (fenomeno El Niño) menciona
        # Zulia unicamente por TEMPERATURA ("En estados como Zulia y Falcon
        # los registros han llegado hasta los 39 °C, segun Inameh"), no por
        # escasez de agua -- pese a que el articulo SI describe fallas de
        # agua reales, estas se ubican en Portuguesa/Acarigua, no en Zulia.
        "en estados como zulia y falcon los registros",
    ],
    # Caso real (15-08-2026, PASADO_POR_FALLA_TECNICA): un articulo de EFE
    # sobre un terremoto de magnitud 7.7 en Indonesia (republicado por un
    # medio de Monagas) nunca menciona ese estado en el cuerpo de la
    # noticia -- la unica mencion es la firma final "Vía// EFE Periodista
    # del estado Monagas.", boilerplate que acredita al periodista local
    # que redistribuyo el cable, no la ubicacion del hecho. Sin remapeo (el
    # hecho real ocurrio en el extranjero): se descarta directamente. Se
    # verifico contra las 122 fuentes de data/historico_fuentes_texto.jsonl
    # que esta firma es exclusiva de este articulo.
    # Ampliado (02-09-2026, PASADO_POR_FALLA_TECNICA): "son pocas las
    # ocasiones en las que pueden trasladarse a Barrancas, en el estado
    # Monagas, para adquirir comida" -- un articulo sobre una inundacion
    # real del rio Orinoco en comunidades de Delta Amacuro (Santa Rosa de
    # Araguao, municipio Antonio Diaz) mencionaba Monagas solo como el
    # destino de viaje al que los damnificados van a comprar alimentos, sin
    # ninguna inundacion propia en ese estado. Sin remapeo: el estado real
    # (Delta Amacuro) no tiene evidencia de tipo dentro de la ventana de
    # proximidad de sus propias menciones en este articulo (quedan a mas de
    # 35 palabras de "crecida"/"inundaciones"), asi que el candidato de
    # Monagas simplemente se descarta, igual que "periodista del estado
    # monagas" arriba. Se verifico contra las 436 fuentes de data/
    # historico_fuentes_texto.jsonl que esta frase es exclusiva de este
    # articulo.
    "Monagas": ["periodista del estado monagas",
                "trasladarse a barrancas, en el estado monagas"],
    # Caso real (15-08-2026, PASADO_POR_FALLA_TECNICA): un articulo sobre
    # sequia/incendios forestales en el estado Trujillo menciona, de
    # pasada, "el colapso de las vias de acceso hacia el estado Portuguesa,
    # lo que obliga a desviar el transito pesado hacia Lara" -- Portuguesa
    # es solo el destino de una via cerrada, no la ubicacion de ningun
    # incendio. Se verifico contra las 122 fuentes de data/
    # historico_fuentes_texto.jsonl que esta frase es exclusiva de este
    # articulo.
    "Portuguesa": ["hacia el estado portuguesa"],
    # Caso real (18-08-2026, PASADO_POR_FALLA_TECNICA): "Rescatan en Choroni
    # a tres pescadores margaritenos... Los rescatistas trasladaron de
    # emergencia a los tres marineros hacia la localidad costera de Choroni,
    # en el estado Aragua" -- "Margarita" (alias de Nueva Esparta) solo
    # identifica el origen/gentilicio de las victimas, no el lugar del
    # naufragio ni del rescate, que el propio texto ubica explicitamente en
    # Aragua. Se remapea (ver _REMAPEO_MUNICIPIO_A_ESTADO) en vez de
    # descartarse sin mas, porque el hecho SI es real -- solo que en otro
    # estado.
    "Nueva Esparta": ["hacia la localidad costera de choroni"],
    # Caso real (18-08-2026, PASADO_POR_FALLA_TECNICA): "Las movilizaciones
    # se registraron... en al menos ocho estados... El Distrito Capital y
    # Amazonas serian los UNICOS territorios SIN racionamiento" -- el propio
    # articulo excluye explicitamente a Amazonas de la lista de estados con
    # protestas/racionamiento, pero la mera mencion del nombre cerca de
    # "racionamiento" bastaba para generar una alerta. Se verifico contra
    # las 168 fuentes de data/historico_fuentes_texto.jsonl que la frase es
    # exclusiva de este articulo.
    "Amazonas": ["unicos territorios sin racionamiento"],
    # Caso real (18-08-2026, PASADO_POR_FALLA_TECNICA): "Plan Vamos con
    # Sorgo... productores ya contabilizan mas de 2.300 hectareas... en el
    # estado Guarico, con la proyeccion inmediata de alcanzar las 2.500
    # hectareas al CONSOLIDAR LA SIEMBRA en los estados Portuguesa y
    # Anzoategui" -- Anzoategui es solo una META FUTURA de expansion del
    # plan agricola, no una siembra ya consolidada ni una sequia puntual
    # actual en ese estado. Se verifico contra las 168 fuentes de data/
    # historico_fuentes_texto.jsonl que la frase es exclusiva de este
    # articulo.
    "Anzoategui": ["consolidar la siembra en los estados portuguesa y anzoategui"],
    # Caso real (19-08-2026, PASADO_POR_FALLA_TECNICA): "Los habitantes de
    # Aragua de Barcelona en el estado Anzoategui se quedaron otra vez sin
    # agua... Los vecinos de municipio Aragua... ubicado en la zona centro
    # del estado Anzoategui" -- "Aragua de Barcelona" es la capital del
    # municipio Aragua, estado Anzoategui (ver config/ubicaciones_detalle.json),
    # sin ninguna relacion con el estado Aragua. El propio articulo ya se
    # publica correctamente bajo Anzoategui (municipio Aragua detectado);
    # sin remapeo (el estado real ya esta cubierto), se descarta directamente
    # el candidato de Aragua, igual que "Carabobo FC" para Carabobo.
    "Aragua": ["aragua de barcelona"],
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
    "Nueva Esparta": {
        "hacia la localidad costera de choroni": "Aragua",
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


# Caso real (20-08-2026, PASADO_POR_FALLA_TECNICA): "...los agricultores...
# del estado Portuguesa encendieron las alarmas ante la falta de una
# definicion justa en el precio de compra del grano, situacion que se suma
# a la severa sequia que afecta a regiones como el estado Guarico, donde
# mas de 80 mil hectareas del rubro se encuentran en jaque" -- un articulo
# sobre productores de maiz de Portuguesa preocupados por el PRECIO de
# compra (no por sequia alguna en su estado) tambien generaba tipo=sequia
# en Portuguesa, porque la ventana de proximidad a la mencion de
# "Portuguesa" (el dateline del articulo) alcanza a cubrir la clausula de
# sequia que el propio texto atribuye explicitamente a OTRO estado
# (Guarico). A diferencia de Guarico (bien ubicado: el texto lo nombra como
# el afectado), Portuguesa no tiene evidencia propia de sequia. Se verifico
# contra las 168 fuentes de data/historico_fuentes_texto.jsonl que esta
# frase, con el estado capturado como grupo, es exclusiva de este articulo
# (aparece 2 veces: una vez para cada estado mencionado en el mismo
# parrafo).
_SEQUIA_ESTADO_NOMBRADO_RE = re.compile(
    r"\bsequia que afecta a (?:regiones como )?el estado ([a-z][a-z ]*?)(?:,| donde| que|\.|$)"
)


def _es_sequia_atribuida_a_otro_estado(texto_norm, ubicacion):
    """True si el texto nombra explicitamente, en la misma clausula de
    sequia, un estado distinto al que se esta clasificando -- ver caso real
    arriba."""
    match = _SEQUIA_ESTADO_NOMBRADO_RE.search(texto_norm)
    if not match:
        return False
    estado_nombrado = match.group(1).strip()
    return estado_nombrado != _normalizar(ubicacion).strip()


# Mismo patron que _es_sequia_atribuida_a_otro_estado, para deslizamiento.
# Caso real (02-09-2026, PASADO_POR_FALLA_TECNICA): "Mientras las
# comunidades agricolas de Tachira y Yaracuy reportaron derrumbes, en
# Caracas y La Guaira los refugiados de los terremotos de junio denuncian
# inundaciones en sus carpas" -- el subtitulo de un articulo-resumen de
# inundaciones (6 estados) nombra explicitamente a Tachira y Yaracuy como
# los estados con derrumbes, en la misma oracion (separada solo por una
# coma) donde luego menciona a Caracas/La Guaira para un hecho DISTINTO
# (inundacion de refugios) -- pero la ventana de proximidad de "Caracas"
# alcanzaba a cubrir "derrumbes" (sin ningun estado interpuesto entre ambas
# palabras), generando tipo=deslizamiento en Distrito Capital sin ninguna
# evidencia propia. Se verifico contra las 436 fuentes de data/
# historico_fuentes_texto.jsonl que la frase, con los 2 estados capturados
# como grupos, es exclusiva de este articulo.
_DERRUMBE_ESTADOS_NOMBRADOS_RE = re.compile(
    r"\bde ([a-z][a-z ]*?) y ([a-z][a-z ]*?) reportaron derrumbes?\b"
)


def _es_derrumbe_atribuido_a_otro_estado(texto_norm, ubicacion):
    """True si el texto nombra explicitamente, en la misma clausula de
    derrumbes, un estado distinto al que se esta clasificando -- ver caso
    real arriba."""
    match = _DERRUMBE_ESTADOS_NOMBRADOS_RE.search(texto_norm)
    if not match:
        return False
    estados_nombrados = {match.group(1).strip(), match.group(2).strip()}
    return _normalizar(ubicacion).strip() not in estados_nombrados


# A diferencia de FRONTERA_EXTRANJERA_POR_ESTADO (que solo aplica a estados
# fronterizos con Colombia, donde un toponimo colombiano puede confundirse
# con uno venezolano homonimo), este marcador es DECISIVO para CUALQUIER
# estado: "San Jose del Palmar" es el nombre inequivoco del epicentro del
# terremoto de magnitud 7.4 en el departamento del Choco, Colombia
# (10-08-2026) -- ningun sismo venezolano real tendria ese epicentro. Caso
# real (16-08-2026, PASADO_POR_FALLA_TECNICA): seis dias despues del sismo,
# seguia generando alertas falsas de sismo NUEVO en estados sin ninguna
# relacion geografica con la frontera colombiana -- en Barinas la unica
# mencion del estado era una lista de titulares no relacionados en la barra
# lateral del medio (ver tambien classify.py, "articulos relacionados"); en
# Sucre el articulo describia a familias sucrenses buscando noticias de
# parientes DESAPARECIDOS EN COLOMBIA, sin ningun sismo local. Se verifico
# contra las 168 fuentes de data/historico_fuentes_texto.jsonl que "san jose
# del palmar" aparece en 4 fuentes de este mismo terremoto -- una de ellas
# (Zulia, 10-08-2026, "Terremoto de 7.4 en Colombia sacude el Zulia") SI
# describe evidencia local real (municipio Maracaibo detectado, "sacude el
# Zulia") y no se ve afectada por este filtro porque exige la AUSENCIA de
# municipio detectado, igual que _es_evento_extranjero_sin_municipio.
#
# Ampliado (20-08-2026, PASADO_POR_FALLA_TECNICA): un terremoto de magnitud
# 7.2 con epicentro en Coracora, Ayacucho, Peru, generaba tipo=sismo en
# Tachira via un titular no relacionado de la seccion "Destacados" del
# medio ("Tachira aporta tres atletas a la seleccion nacional de
# baloncesto U15") incluido al final del texto scrapeado -- mismo patron
# de "titulares no relacionados en la barra lateral" ya documentado arriba
# para Barinas. A diferencia de "San Jose del Palmar", NO se agrega
# "Ayacucho" solo (es tambien un municipio real de Tachira, ver
# config/ubicaciones_detalle.json, confirmado por un caso de control real
# en el mismo corpus: "en los municipios Ayacucho... del estado Tachira"),
# asi que se usa "Coracora" (localidad peruana sin colision con ningun
# topónimo venezolano) como marcador decisivo.
_EPICENTROS_SISMO_EXTRANJERO_DECISIVOS = ["san jose del palmar", "coracora"]


def _es_sismo_extranjero_con_epicentro_conocido_sin_municipio(texto_norm, municipio):
    if municipio:
        return False
    return any(e in texto_norm for e in _EPICENTROS_SISMO_EXTRANJERO_DECISIVOS)


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
    # Ampliado (02-09-2026, PASADO_POR_FALLA_TECNICA): dos casos reales
    # distintos de referencia retrospectiva al terremoto del 24 de junio,
    # sin ningun sismo nuevo:
    # 1) "quien anuncio que durante las fiestas se mantendra un
    #    acompanamiento espiritual especial para los afectados por los
    #    sismos registrados el 24 de junio" -- una cobertura de la Bajada de
    #    la Virgen del Valle (fiesta religiosa en Nueva Esparta) disparaba
    #    tipo=sismo solo por esa mencion pastoral, sin relacion con un
    #    temblor nuevo.
    # 2) "Mientras las comunidades agricolas de Tachira y Yaracuy reportaron
    #    derrumbes, en Caracas y La Guaira los refugiados de los terremotos
    #    de junio denuncian inundaciones en sus carpas" -- el subtitulo de un
    #    articulo-resumen de inundaciones por lluvia (6 estados) disparaba
    #    tipo=sismo en Carabobo y La Guaira solo por esa mencion de los
    #    refugios de terremotos ya ocurridos, sin ningun temblor nuevo (el
    #    hecho real de esos estados es la inundacion, ya cubierta aparte).
    # No se usa "el pasado"/"del pasado" (como _SISMO_FECHA_PASADA_RE) porque
    # ninguno de los dos casos usa esa palabra. Se verifico contra las 436
    # fuentes de data/historico_fuentes_texto.jsonl (via classify.detectar_ubicacion/
    # detectar_tipo reales, no solo grep) que estas frases, evaluadas sobre la
    # VENTANA (no el articulo completo -- a diferencia de
    # _es_referencia_sismo_fecha_pasada), no afectan un caso de control real
    # y vigente en el mismo corpus (Runrun.es, 18-08-2026, "colapso de
    # vivienda en Carapita"): un sismo real del 18 de agosto que TAMBIEN
    # menciona, mucho mas lejos en el mismo articulo, "los terremotos del
    # pasado 24 de junio" -- esa mencion queda fuera de la ventana de
    # proximidad de Distrito Capital en ese caso, a diferencia de los 2
    # casos reales de arriba donde la mencion retrospectiva SI cae dentro de
    # la ventana que genero el tipo=sismo.
    "sismo": ["cerco epidemiologico", "epidemiologico", "brote de enfermedad",
              "atenciones medicas", "salud integral comunitaria",
              "24 de junio", "terremoto de junio", "terremotos de junio",
              "sismo de junio", "sismos de junio"],
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
    # Ampliado (18-08-2026, PASADO_POR_FALLA_TECNICA): "Proteccion Civil y
    # Salud Ambiental desplegaron una jornada de ABORDAJE PREVENTIVO...
    # distribuyeron rodenticidas y antiparasitarios... abatizacion,
    # enfocados en neutralizar y eliminar los criaderos del mosquito Aedes
    # aegypti... para prevenir brotes epidemicos" -- una jornada RUTINARIA
    # de fumigacion/abatizacion contra el dengue, sin ningun caso ni brote
    # activo mencionado, disparaba tipo=salud_publica solo por las palabras
    # "dengue"/"enfermedades". Mismo patron que "prevenir enfermedades" (ya
    # cubierto arriba), con la frase especifica que usa este tipo de
    # jornada de control de vectores.
    # Ampliado (19-08-2026, PASADO_POR_FALLA_TECNICA): "se instalo en el
    # estado Apure el Estado Mayor para la Caracterizacion del Rebano
    # Bovino... para avanzar hacia la certificacion internacional de
    # Venezuela como territorio libre de FIEBRE AFTOSA" -- un censo de
    # ganado bovino/bufalino disparaba tipo=salud_publica via la palabra
    # "enfermedad" ("erradicar la enfermedad"), pero la fiebre aftosa es
    # una enfermedad EXCLUSIVAMENTE ANIMAL (no afecta salud publica
    # humana) -- ademas, el error se agravaba porque el vocero citado,
    # "Julio Cesar Vargas", generaba una ubicacion falsa en La Guaira via
    # el alias "Vargas" (ver _es_mencion_de_persona_citada).
    #
    # Ampliado (19-08-2026, mismo dia): "El Sistema de Orquestas... notifico
    # el deceso de la niña Romina Rivera Cruz, de 10 años... murio como
    # consecuencia de una ENFERMEDAD CONGENITA" -- un obituario/homenaje a
    # una niña fallecida por una enfermedad congenita preexistente (no un
    # brote, no una alarma sanitaria) disparaba tipo=salud_publica con
    # severidad CRITICA solo por la palabra "enfermedad", pese a no haber
    # nada que la Cruz Roja deba atender como emergencia de salud publica.
    "salud_publica": ["totalmente controlada", "enfermedad controlada",
                       "no existen registros confirmados",
                       "sin registros confirmados", "brote descartado",
                       "descartado el brote", "bajo control total",
                       "prevenir enfermedades", "prevenir la propagacion",
                       "tiempos de la pandemia", "durante la pandemia",
                       "desde la pandemia", "epoca de la pandemia",
                       "época de la pandemia",
                       "abordaje preventivo", "jornada preventiva",
                       "fiebre aftosa", "enfermedad congenita",
                       "enfermedad congénita"],
    # Caso real (30-07-2026): "Venezuela entrego nota de protesta a Iran por
    # declaraciones de su canciller" -- una nota de protesta DIPLOMATICA
    # entre gobiernos, sin ninguna relacion con disturbios/orden publico en
    # Venezuela, disparaba tipo=orden_publico solo por la palabra
    # "protesta". Mismo patron que "manifestaciones artisticas" (por eso
    # esa palabra ya se excluye sola de los keywords de tipo): una palabra
    # ambigua entre el sentido de disturbio civil y otro uso idiomatico
    # totalmente distinto. (Ver tambien _es_manifestacion_pacifica_sin_evidencia_fuerte()
    # mas abajo, para el caso de una manifestacion explicitamente pacifica.)
    # Ampliado (18-08-2026, PASADO_POR_FALLA_TECNICA): "La Camara de
    # Comercio de Cumana EXPRESO SU PROTESTA ante el nuevo racionamiento...
    # El gremio presento una propuesta tecnica..." -- un comunicado
    # institucional/gremial usando la palabra "protesta" en su sentido de
    # queja formal (con una propuesta tecnica de tres ejes, sin ninguna
    # manifestacion fisica descrita), mismo patron que la nota de protesta
    # diplomatica.
    # Ampliado (02-09-2026, PASADO_POR_FALLA_TECNICA): "Estos hechos
    # ocurrieron durante la represion postelectoral de 2013 y las protestas
    # civiles de 2014, ejecutados por el Destacamento 47..." -- un articulo
    # sobre una ONG y victimas exigiendo al fiscal general abrir una
    # investigacion contra un militar deportado por torturas cometidas
    # durante la represion postelectoral de 2013, disparaba tipo=orden_publico
    # via "protestas civiles de 2014" -- una referencia historica de mas de
    # una decada, usada para fechar las denuncias de tortura, no un disturbio
    # ocurriendo hoy. Se verifico contra las 436 fuentes de data/
    # historico_fuentes_texto.jsonl que la frase es exclusiva de este
    # articulo.
    "orden_publico": ["nota de protesta", "notas de protesta",
                       "expreso su protesta ante", "expresó su protesta ante",
                       "protestas civiles de 2014"],
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
    # Usada por _es_anuncio_institucional_bomberos_sin_incendio_real(): si
    # ademas del anuncio institucional el articulo describe un incendio
    # real en curso, esta evidencia evita descartar el tipo.
    "incendio": ["llamas", "sofocar", "sofocado", "sofocaron",
                 "controlar el incendio", "controlaron el incendio",
                 "heridos", "lesionados", "fallecidos", "quemaduras",
                 "evacuados", "evacuadas", "consumio", "consumió"],
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
    # Usada por _es_captura_fugitivo_sin_ataque_en_curso(): si ademas de la
    # notificacion azul/orden de captura el articulo describe un ataque
    # real en curso (poco comun, pero posible en una cobertura mixta), esta
    # evidencia evita descartar el tipo.
    "ataque_armado": ["tiroteo", "tiroteos", "enfrentamiento",
                       "enfrentamientos", "heridos", "fallecidos",
                       "muertos", "muertas", "emboscada"],
    # Usada por _es_boletin_pronostico_inameh_sin_inundacion_real(): si el
    # articulo describe una inundacion YA ocurrida (no solo pronosticada),
    # esta evidencia evita descartar el tipo.
    "inundacion": ["anegado", "anegada", "anegados", "anegadas",
                    "anegacion", "anegaciones", "vivienda anegada",
                    "viviendas anegadas", "familias afectadas",
                    "evacuados", "evacuadas", "arrastro", "arrastró",
                    "desbordo", "desbordó", "damnificados", "damnificadas"],
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

# Caso real (20-08-2026, PASADO_POR_FALLA_TECNICA): "Familia en La
# Milagrosa lleva 3 años esperando respuesta tras crecida del Rio Milla...
# Hace tres años, la crecida del rio Milla derrumbo el patio y destruyo las
# paredes de la vivienda... al borde del colapso total" -- un reportaje
# sobre una familia que vive desde hace 3 anos en una casa danada por una
# inundacion YA OCURRIDA, sin ningun desarrollo nuevo el dia de
# publicacion, generaba una alerta de inundacion CRITICA (via "colapso
# total", que describe el riesgo temido a futuro, no un hecho consumado)
# como si la crecida hubiera ocurrido esa madrugada. A diferencia de "anos
# de espera" (que exige esa frase exacta), aqui el articulo data el propio
# hecho ("la crecida") con "hace N anos" en vez de enmarcar la espera --
# por eso no bastaba el marcador existente. No se uso "hace N anos" a secas
# como marcador (demasiado amplio: dispara con frecuencia en citas de
# contexto de coberturas de protestas/reclamos REALES y vigentes, ej. "el
# alcalde afirmo que hace un ano fue informado por Corpoelec", sin volver
# retrospectivo el resto del articulo) -- se exige que el propio suceso
# hidrologico (crecida/inundacion/desbordamiento) este fechado por la frase
# "hace N anos", nunca solo una mencion de contexto. Se verifico contra las
# 168 fuentes de data/historico_fuentes_texto.jsonl que "hace N anos" a
# secas aparece en otros 3 casos reales y vigentes (paro civico en El
# Callao, protesta de familiares de militares detenidos, protesta por
# racionamiento en Acarigua) que NO deben descartarse, y que este patron
# mas especifico es exclusivo del caso de La Milagrosa.
_RETROSPECTIVO_HECHO_HIDROLOGICO_ANOS_RE = re.compile(
    r"\bhace (un|dos|tres|cuatro|cinco|seis|siete|ocho|nueve|diez|\d+) a[nñ]os,?"
    r" la (crecida|inundacion|inundación|desbordamiento)\b",
    re.IGNORECASE,
)


def _es_articulo_retrospectivo_larga_duracion(texto_norm):
    if any(_contiene_palabra_clave(texto_norm, frase) for frase in _ARTICULO_RETROSPECTIVO_LARGA_DURACION):
        return True
    if _RANGO_FECHAS_RETROSPECTIVO_RE.search(texto_norm) is not None:
        return True
    if _RESUMEN_TALLY_INCENDIOS_RE.search(texto_norm) is not None:
        return True
    return _RETROSPECTIVO_HECHO_HIDROLOGICO_ANOS_RE.search(texto_norm) is not None


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


# Caso real (20-08-2026, PASADO_POR_FALLA_TECNICA): "El sismo alcanzo una
# intensidad de III-IV en Coracora... Las autoridades descartan, por ahora,
# posibilidad de tsunami" (terremoto de magnitud 7.2 en Ayacucho, Peru)
# disparaba tipo=tsunami en La Guaira via la palabra "tsunami" -- la MISMA
# frase que la niega explicitamente. La ubicacion "La Guaira" tampoco tenia
# relacion real con el hecho: era el titular de un articulo relacionado
# incluido de pasada en el texto scrapeado ("mujer localiza a su familia
# atrapada en edificio de La Guaira"), mismo patron de "titulares no
# relacionados" ya documentado para el epicentro extranjero de sismo. Igual
# que el boletin institucional de tsunami, esta señal es decisiva (un
# tsunami explicitamente descartado por las autoridades no es evidencia de
# uno real) y se evalua sobre el ARTICULO COMPLETO.
_MARCADORES_TSUNAMI_DESCARTADO = [
    "descartan, por ahora, posibilidad de tsunami",
    "descartan la posibilidad de tsunami",
    "descartan posibilidad de tsunami",
    "descarta la posibilidad de tsunami",
    "descarta posibilidad de tsunami",
    "descartaron la posibilidad de tsunami",
    "descarto la posibilidad de tsunami",
    "sin riesgo de tsunami", "no representa riesgo de tsunami",
    "no genera riesgo de tsunami", "no hay riesgo de tsunami",
]


def _es_tsunami_descartado_explicitamente(texto_norm):
    if not any(_contiene_palabra_clave(texto_norm, m) for m in _MARCADORES_TSUNAMI_DESCARTADO):
        return False
    return not any(_contiene_palabra_clave(texto_norm, f) for f in _EVIDENCIA_FUERTE_TSUNAMI_REAL)


# Caso real (15-08-2026, PASADO_POR_FALLA_TECNICA): "Corposalud y OPS
# unifican esfuerzos en capacitacion de salud mental... para fortalecer el
# acompañamiento psicologico y social de la poblacion civil afectada por la
# contingencia sismica... dirigido al personal que atiende directamente a
# pacientes en los refugios temporales" -- un taller de capacitacion en
# salud mental para personal que atiende a damnificados de un sismo YA
# ocurrido disparaba tipo=sismo en Aragua via la palabra "terremoto"
# (mencionada mucho mas adelante, en una cita sobre el impacto emocional de
# los sobrevivientes, fuera de la ventana de proximidad a "Aragua" -- por
# eso no basta con _CONTEXTO_CONFLICTIVO_POR_TIPO). Mismo patron que el
# boletin institucional de tsunami: se evalua sobre el ARTICULO COMPLETO.
_MARCADORES_TALLER_SALUD_MENTAL_POST_SISMO = [
    "salud mental", "contingencia sismica", "contingencia sísmica",
    "refugios temporales", "campamentos transitorios",
]


def _es_taller_salud_mental_post_sismo_sin_evidencia_real(texto_norm):
    if not any(_contiene_palabra_clave(texto_norm, m) for m in _MARCADORES_TALLER_SALUD_MENTAL_POST_SISMO):
        return False
    fuerte = _EVIDENCIA_FUERTE_POR_TIPO.get("sismo", [])
    return not any(_contiene_palabra_clave(texto_norm, f) for f in fuerte)


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


# Caso real (14-08-2026, PASADO_POR_FALLA_TECNICA): "Madres y activistas
# presentaron un libro que documenta la represión poselectoral del 28 de
# julio de 2024 en Venezuela" -- una nota sobre la PRESENTACION de un
# libro que preserva la memoria de una represion politica ya ocurrida
# (2024) mencionaba de pasada, como contexto, una protesta de familiares
# de presos politicos ocurrida un dia ANTES de la presentacion del libro
# ("la presentacion del libro ocurrio un dia despues de que familiares...
# protestaran"), disparando tipo=orden_publico en Distrito Capital via la
# palabra "manifestantes" -- usada para referirse a esos MISMOS
# manifestantes de dias atras, no a un disturbio en curso. El tema del
# articulo es la presentacion de un libro/acto de memoria, no un hecho de
# orden publico actual. Igual que la manifestacion pacifica, se evalua
# sobre el ARTICULO COMPLETO (la mencion del libro puede quedar lejos, en
# palabras, de "manifestantes").
_MARCADORES_PRESENTACION_LIBRO_MEMORIA = [
    "presentaron un libro", "presento un libro", "presentó un libro",
    "presentacion del libro", "presentación del libro",
]
# "detenidos" NO se incluye aqui, a diferencia de _EVIDENCIA_FUERTE_POR_TIPO
# ["orden_publico"] -- en el contexto de un libro/acto de memoria sobre
# presos politicos, "detenidos" describe personas YA privadas de libertad
# (un estado historico/cronico: "jovenes detenidos por razones politicas",
# "detenidos por motivos politicos"), no arrestos frescos durante un
# disturbio en curso, que es lo que esa palabra normalmente evidencia.
_EVIDENCIA_FUERTE_SIN_PRESOS_POLITICOS = [
    "heridos", "saqueo", "saqueos", "disturbios",
    "tiroteo", "tiroteos", "enfrentamiento", "enfrentamientos",
]


def _es_presentacion_libro_memoria_sin_disturbio_actual(texto_norm):
    if not any(_contiene_palabra_clave(texto_norm, m) for m in _MARCADORES_PRESENTACION_LIBRO_MEMORIA):
        return False
    return not any(_contiene_palabra_clave(texto_norm, f) for f in _EVIDENCIA_FUERTE_SIN_PRESOS_POLITICOS)


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


# Caso real (19-08-2026, a pedido del usuario): "Todos los dias por 5 o 6
# horas se va la luz", citado por una vendedora de cachapas en un articulo
# sobre gastronomia en Monagas (sin ninguna relacion con una falla nueva),
# generaba una alerta de infraestructura_electrica -- mismo patron de
# fondo que la casa hogar de Tachira que pide donaciones (14-08-2026,
# identificado como pendiente en la auditoria del 18-08-2026): una queja
# CRONICA sobre apagones diarios, citada como contexto de un articulo cuyo
# TEMA real es otro (comida, donaciones), sin ningun hecho electrico nuevo,
# colectivo o institucional que la respalde como una alerta puntual.
#
# El desafio (tambien documentado en esa auditoria) es que el mismo
# lenguaje ("todos los dias", "cortes constantes") tambien aparece en
# coberturas REALES: protestas activas (con cacerolazos/manifestantes/
# concentraciones), denuncias de una figura politica con datos concretos
# (ej. un concejal alertando que los cortes ponen en riesgo a pacientes de
# hemodialisis), o un incidente puntual nuevo (un transformador, una
# parroquia con paralizacion total del servicio desde una fecha concreta).
# Por eso el descarte exige la AUSENCIA de ambas: si el articulo tiene
# evidencia de accion colectiva en curso o de un incidente nuevo y
# especifico, no se descarta. Se descarto a proposito una tercera
# categoria de escape ("figura politica citada") probada durante el
# diseño de este filtro: un "gobernador"/"concejal" mencionado en
# CUALQUIER parte del articulo -- no necesariamente relacionado con la
# queja electrica -- evitaba el descarte por coincidencia. Caso real: la
# casa hogar de Tachira (ver arriba) menciona al gobernador del estado en
# el contexto de una ambulancia prometida, sin relacion alguna con los
# apagones, y ese solo hecho bastaba para no descartarla. Se verifico
# contra las 4 fuentes vigentes de infraestructura_electrica en data/
# historico_fuentes_texto.jsonl que usan "todos los dias"/"a diario"
# (protesta en 8 estados, PJ y su mapa, Andres Velasquez, y una alerta de
# un concejal sobre pacientes renales en Zulia -- esta ultima sigue
# publicandose con normalidad porque el mismo articulo tambien reporta
# "la paralizacion total de la red energetica" en La Guajira, un incidente
# especifico) que ninguna se ve afectada por el descarte final.
_MARCADORES_QUEJA_CRONICA_ELECTRICA = [
    "todos los dias", "todos los días", "a diario", "cada dia", "cada día",
]
_MARCADORES_ESCAPE_QUEJA_CRONICA_ELECTRICA = [
    # Accion colectiva en curso.
    "protesta", "protestas", "protestaron", "manifestantes",
    "manifestacion", "manifestación", "cacerolazo", "cacerolazos",
    "concentraron", "se concentraron", "marcha de protesta",
    # Incidente nuevo y especifico.
    "transformador", "explosion", "explosión",
    "restablecer el suministro", "restablecer el servicio",
    "cortocircuito", "corto circuito",
    "poste caido", "poste caído", "poste derribado",
    "cable caido", "cable caído",
    "paralizacion total", "paralización total",
    "paralisis total", "parálisis total",
]


def _es_queja_cronica_electrica_sin_hecho_verificable(texto_norm):
    if not any(m in texto_norm for m in _MARCADORES_QUEJA_CRONICA_ELECTRICA):
        return False
    if any(m in texto_norm for m in _MARCADORES_ESCAPE_QUEJA_CRONICA_ELECTRICA):
        return False
    # Un articulo-resumen de un tercero (mapa de PJ, informe de un
    # observatorio...) que reparte cifras entre muchos estados YA tiene su
    # propio mecanismo de precision por estado (ver
    # _MARCADORES_RECLAMO_TERCERO_MULTIESTADO/_ventana_sin_evidencia_local_
    # especifica, que SI distingue, estado por estado, cual mencion tiene
    # evidencia local real -- ej. "municipio Libertador de Caracas denuncian
    # fallas electricas" -- de cual es solo una cifra generica repartida).
    # Este filtro, al evaluar el ARTICULO COMPLETO, no debe pisar ese
    # mecanismo mas fino: si el articulo ya es de ese tipo, se cede el paso.
    if any(_contiene_palabra_clave(texto_norm, m) for m in _MARCADORES_RECLAMO_TERCERO_MULTIESTADO):
        return False
    return True


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


# Caso real (15-08-2026, PASADO_POR_FALLA_TECNICA): "Falsa alarma en
# Carabobo: Despliegue policial por supuesta granada termina tras hallazgo
# de un envase de perfume... se descarto de manera categorica que se
# tratara de una amenaza real" -- el propio articulo, ya desde el titular,
# aclara que la "granada" reportada nunca fue un explosivo. Mismo patron
# que el cartucho lacrimogeno: se evalua sobre el ARTICULO COMPLETO.
_MARCADORES_FALSA_ALARMA_EXPLOSIVO = ["falsa alarma"]


def _es_falsa_alarma_sin_explosivo_real(texto_norm):
    if not any(_contiene_palabra_clave(texto_norm, m) for m in _MARCADORES_FALSA_ALARMA_EXPLOSIVO):
        return False
    fuerte = _EVIDENCIA_FUERTE_POR_TIPO.get("explosion", [])
    return not any(_contiene_palabra_clave(texto_norm, f) for f in fuerte)


# Caso real (15-08-2026, PASADO_POR_FALLA_TECNICA): "Capturada en Tachira
# mujer solicitada por terrorismo y trafico de armas... presentaba una
# Notificacion Azul en su contra por la presunta comision de los delitos
# de trafico de armas y municiones... y terrorismo" disparaba tipo=
# ataque_armado en Tachira via las palabras "terrorismo"/"trafico de
# armas" -- el hecho real es la CAPTURA de una fugitiva con una notificacion
# de Interpol en su contra, no un ataque armado en curso. Se evalua sobre
# el ARTICULO COMPLETO (igual que el cartucho lacrimogeno): "notificacion
# azul" es un termino tecnico especifico de Interpol para personas
# buscadas, exclusivo de este tipo de nota de captura/detencion.
#
# Ampliado (15-08-2026, mismo dia): "Dos hermanos de Araya fueron
# excarcelados tras permanecer detenidos por financiamiento al terrorismo...
# tras estar recluidos por mas de un año" disparaba el mismo tipo=
# ataque_armado en Sucre via "terrorismo" -- el hecho real es la
# EXCARCELACION (liberacion) de dos personas ya detenidas desde hace un año,
# el extremo opuesto de una captura, pero el mismo patron de fondo: un
# proceso judicial relacionado con cargos de terrorismo, sin ningun ataque
# armado ocurriendo. "Excarcelados"/"excarcelacion" es un termino juridico
# especifico (liberacion de un recluso), exclusivo de este tipo de nota.
#
# Ampliado (18-08-2026, PASADO_POR_FALLA_TECNICA): "Omar Mora Tosta denuncia
# 'limbo' judicial en casos de Dignora Hernandez y Henry Alviarez... El caso
# pertenecia al Tribunal Primero de Juicio con competencia en TERRORISMO"
# disparaba tipo=ataque_armado via la palabra "Terrorismo" (nombre de la
# jurisdiccion del tribunal, no un ataque) -- el hecho real es un abogado
# denunciando trabas administrativas (un expediente extraviado, la
# imposibilidad de presentarse ante el tribunal) en el proceso judicial de
# dos dirigentes opositores, ni una captura ni una excarcelacion, pero el
# mismo patron de fondo: un proceso judicial relacionado con cargos de
# terrorismo, sin ningun ataque armado ocurriendo. "Limbo" (entre comillas
# en el titular, refiriendose al estado procesal del caso) es un termino
# exclusivo de este tipo de nota. Se verifico contra las 168 fuentes de
# data/historico_fuentes_texto.jsonl que la palabra es exclusiva de este
# articulo.
#
# Ampliado (20-08-2026, PASADO_POR_FALLA_TECNICA): "Transparencia Venezuela
# alerta sobre irregularidades en sobreseimientos del clan Convit y
# detencion de jueces... la Sala Especial de la Corte de Apelaciones de
# Caracas, con competencia en delitos de TERRORISMO, corrupcion y
# delincuencia organizada, decreto el sobreseimiento de la causa..." --
# mismo patron: "terrorismo" nombra la jurisdiccion de un tribunal, y el
# hecho real es un SOBRESEIMIENTO (cierre/archivo de una causa penal), el
# opuesto de una captura o un ataque, denunciado por una ONG de
# transparencia. "Sobreseimiento"/"sobreseimientos" es un termino juridico
# especifico (cierre de una causa sin condena), exclusivo de este tipo de
# nota. Se verifico contra las 168 fuentes de data/historico_fuentes_texto.jsonl
# que la palabra es exclusiva de este articulo.
_MARCADORES_CAPTURA_FUGITIVO = [
    "notificacion azul", "notificación azul",
    "orden de captura internacional",
    "excarcelados", "excarcelado", "excarcelada", "excarceladas",
    "excarcelacion", "excarcelación",
    "limbo",
    "sobreseimiento", "sobreseimientos",
    # Ampliado (20-08-2026, PASADO_POR_FALLA_TECNICA): "en marzo de 2025...
    # 238 venezolanos [fueron enviados] a El Salvador, donde fueron
    # recluidos en el Centro de Confinamiento del Terrorismo (Cecot)"
    # disparaba tipo=ataque_armado en un articulo sobre deportaciones de
    # venezolanos a Liberia -- "Centro de Confinamiento del Terrorismo" es
    # el nombre propio de la megaprision salvadorena (Cecot), mencionada
    # como contexto historico de un episodio de deportacion previo, no un
    # ataque armado ocurriendo. Termino exclusivo de este tipo de nota
    # (migracion/deportaciones), frecuente en coberturas sobre venezolanos.
    "centro de confinamiento del terrorismo", "cecot",
]


def _es_captura_fugitivo_sin_ataque_en_curso(texto_norm):
    if not any(_contiene_palabra_clave(texto_norm, m) for m in _MARCADORES_CAPTURA_FUGITIVO):
        return False
    fuerte = _EVIDENCIA_FUERTE_POR_TIPO.get("ataque_armado", [])
    return not any(_contiene_palabra_clave(texto_norm, f) for f in fuerte)


# Caso real (15-08-2026, PASADO_POR_FALLA_TECNICA): "Inameh pronostico
# fuertes chubascos con la llegada de la Onda Tropical 37 a Venezuela...
# en areas de nuestra Guayana Esequiba, Bolivar, Amazonas... Lara..." --
# un boletin meteorologico RUTINARIO de pronostico (no de un hecho ya
# ocurrido) disparaba tipo=inundacion en Lara via la palabra "vaguada"
# (termino meteorologico generico, parte del vocabulario tecnico de
# cualquier pronostico del Inameh, no evidencia de una inundacion real). Se
# verifico contra las 122 fuentes de data/historico_fuentes_texto.jsonl que
# ninguna cobertura real de daños/inundaciones por una onda tropical (p.ej.
# la Onda Tropical 30, que si causo anegaciones/derrumbes/lesionados reales)
# menciona al Inameh como fuente -- la combinacion de ambas palabras es
# exclusiva de boletines de pronostico puro. Se evalua sobre el ARTICULO
# COMPLETO, no la ventana (el pronostico lista muchos estados a la vez, sin
# concentrar "inameh"/"onda tropical" cerca de cada uno en particular).
def _es_boletin_pronostico_inameh_sin_inundacion_real(texto_norm):
    if not _contiene_palabra_clave(texto_norm, "inameh"):
        return False
    if not _contiene_palabra_clave(texto_norm, "onda tropical"):
        return False
    fuerte = _EVIDENCIA_FUERTE_POR_TIPO.get("inundacion", [])
    return not any(_contiene_palabra_clave(texto_norm, f) for f in fuerte)


# "Derrumbe" (palabra clave de deslizamiento) es ambiguo en español entre un
# movimiento de tierra/ladera y el desplome de una estructura por deterioro.
# Caso real (18-08-2026, PASADO_POR_FALLA_TECNICA): "Se derrumba techo de
# casa colonial... el derrumbe parcial del techo de una vivienda... se
# presume que las continuas precipitaciones... debilitaron los materiales de
# construccion tradicional, como la madera y las tejas de arcilla" -- un
# techo que colapsa por deterioro estructural agravado por la lluvia se
# publicaba como deslizamiento en Guarico, cuando el hecho real es un
# colapso_estructural (mismo patron que el desplome de una vivienda en
# Carapita, ya cubierto bajo ese tipo). A diferencia de
# _CONTEXTO_CONFLICTIVO_POR_TIPO (que solo descarta el tipo detectado sin
# reemplazarlo, perdiendo el evento por completo si no hay otra palabra
# clave), aqui el hecho SI es una emergencia real que merece seguir
# publicandose -- solo que bajo el tipo correcto. Se exige la AUSENCIA de
# palabras de terreno natural (ladera/talud/cerro/montaña/tierra) y de
# evidencia fuerte de deslizamiento (heridos/fallecidos/desaparecidos/
# viviendas colapsadas/evacuados/familias afectadas) para no reclasificar un
# deslizamiento real que ademas dañe un techo de pasada.
_MARCADORES_DERRUMBE_ESTRUCTURAL = ["techo", "tejas", "tejado"]
_MARCADORES_DESLIZAMIENTO_TERRENO = ["ladera", "talud", "cerro", "montana", "montaña", "tierra"]


def _es_derrumbe_de_techo_no_deslizamiento(texto_norm):
    if not (_contiene_palabra_clave(texto_norm, "derrumbe") or _contiene_palabra_clave(texto_norm, "derrumbes")):
        return False
    if not any(_contiene_palabra_clave(texto_norm, m) for m in _MARCADORES_DERRUMBE_ESTRUCTURAL):
        return False
    if any(_contiene_palabra_clave(texto_norm, m) for m in _MARCADORES_DESLIZAMIENTO_TERRENO):
        return False
    fuerte = _EVIDENCIA_FUERTE_POR_TIPO.get("deslizamiento", [])
    return not any(_contiene_palabra_clave(texto_norm, f) for f in fuerte)


# "Escombros" (palabra clave de deslizamiento) es ambiguo entre el material
# suelto de un deslizamiento de tierra y los restos de construccion tras un
# terremoto. Caso real (20-08-2026, PASADO_POR_FALLA_TECNICA): "Maquinaria
# pesada de EEUU llego a Venezuela para retirar toneladas de escombros por
# terremotos... para apoyar las labores de remocion de los escombros
# dejados por los devastadores terremotos que sacudieron Venezuela el
# pasado 24 de junio" y "Mas de 600 mil toneladas de escombros se han
# recolectado en La Guaira... tras los terremotos que azotaron... el
# pasado 24 de junio" -- dos coberturas de labores de LIMPIEZA de escombros
# de un terremoto de hace casi 2 meses disparaban tipo=deslizamiento en
# Distrito Capital y La Guaira como si un deslizamiento estuviera
# ocurriendo hoy. Igual que el boletin institucional de tsunami, se evalua
# sobre el ARTICULO COMPLETO: si el texto combina "escombros" con un verbo
# de limpieza/recoleccion Y una mencion sismica, y no hay evidencia fuerte
# propia de deslizamiento (heridos/fallecidos/desaparecidos/viviendas
# colapsadas o destruidas/evacuados/familias afectadas), se descarta el
# tipo -- el hecho es real (la limpieza) pero no es un deslizamiento nuevo.
_VERBOS_LIMPIEZA_ESCOMBROS = [
    "retirar", "retiro", "retiró", "remocion", "remoción",
    "recolectado", "recolectar", "recoleccion", "recolección",
    "remover", "removieron",
]
_MENCIONES_SISMICAS_ESCOMBROS = [
    "terremoto", "terremotos", "sismo", "sismos", "temblor", "temblores",
]


def _es_limpieza_escombros_terremoto_sin_deslizamiento_real(texto_norm):
    if not (_contiene_palabra_clave(texto_norm, "escombro") or _contiene_palabra_clave(texto_norm, "escombros")):
        return False
    if not any(_contiene_palabra_clave(texto_norm, v) for v in _VERBOS_LIMPIEZA_ESCOMBROS):
        return False
    if not any(_contiene_palabra_clave(texto_norm, s) for s in _MENCIONES_SISMICAS_ESCOMBROS):
        return False
    fuerte = _EVIDENCIA_FUERTE_POR_TIPO.get("deslizamiento", [])
    return not any(_contiene_palabra_clave(texto_norm, f) for f in fuerte)


# Caso real (19-08-2026, PASADO_POR_FALLA_TECNICA): "Un grupo de ciudadanos
# protesto... Las movilizaciones se registraron de forma simultanea en al
# menos ocho estados del pais, incluyendo... Cojedes, donde ciudadanos SE
# CONCENTRARON FRENTE A LAS SEDES REGIONALES DE CORPOELEC para rechazar los
# prolongados cortes de electricidad" -- Cojedes SI tiene una protesta real
# y puntual (a diferencia de Amazonas en el mismo articulo, ya cubierto por
# LISTA_NEGRA_POR_ESTADO -- ahi el propio texto NIEGA que haya
# racionamiento), pero se publicaba como infraestructura_electrica en vez
# de orden_publico: la palabra clave mas cercana a "Cojedes" es "corpoelec"
# (keyword de infraestructura_electrica), no "protesta"/"manifestantes"
# (keywords de orden_publico, que aparecen varias frases antes, fuera de la
# ventana de proximidad). Igual que _es_derrumbe_de_techo_no_deslizamiento,
# el hecho SI es real -- solo que del tipo equivocado -- asi que se
# reclasifica en vez de perderse. Se verifico contra las 168 fuentes de
# data/historico_fuentes_texto.jsonl que la frase completa es exclusiva de
# este articulo.
_MARCADORES_PROTESTA_ELECTRICA_TIPO_INCORRECTO = [
    "se concentraron frente a las sedes regionales de corpoelec",
]


def _es_protesta_electrica_con_tipo_incorrecto(texto_norm):
    return any(m in texto_norm for m in _MARCADORES_PROTESTA_ELECTRICA_TIPO_INCORRECTO)


# Caso real (02-09-2026, PASADO_POR_FALLA_TECNICA): "A 200 bolivares el
# pasaje urbano a partir del 1 de septiembre de 2026... Otros medios de
# transporte como el Metro de Caracas, Metrobus y el ferrocarril
# Caracas-Cua..., continuaran cobrando sus tarifas habituales" -- un
# articulo sobre el ajuste del pasaje urbano (transporte terrestre)
# disparaba tipo=emergencia_metro solo por la frase "Metro de Caracas",
# mencionado de pasada para aclarar que su tarifa NO cambia -- sin ninguna
# falla/varados/incendio/descarrilamiento real. Se verifico contra las 436
# fuentes de data/historico_fuentes_texto.jsonl que la frase es exclusiva de
# este articulo.
_MARCADORES_ANUNCIO_TARIFARIO_METRO = [
    "continuaran cobrando sus tarifas habituales",
    "continuarán cobrando sus tarifas habituales",
]
_EVIDENCIA_FUERTE_EMERGENCIA_METRO = [
    "varados", "atrapados", "incendio", "descarrilamiento", "colapsado",
    "colapso del servicio", "falla en el metro", "falla del metro",
]


def _es_anuncio_tarifario_metro_sin_falla_real(texto_norm):
    if not any(m in texto_norm for m in _MARCADORES_ANUNCIO_TARIFARIO_METRO):
        return False
    return not any(_contiene_palabra_clave(texto_norm, f) for f in _EVIDENCIA_FUERTE_EMERGENCIA_METRO)


# Caso real (02-09-2026, PASADO_POR_FALLA_TECNICA): un tuit citado dentro de
# una nota sobre fallas electricas en Baruta/El Hatillo decia "Luego de mes
# y pico sin agua en Los Naranjos en el Hatillo, Caracas, hoy llego asi que
# la gente se dispone a lavar pero oops, no hay luz" -- el corte de AGUA ya
# habia terminado ("hoy llego") el mismo dia de publicacion; la unica falla
# vigente ese dia era la electrica (tema real del articulo). "sin agua"
# disparaba tipo=infraestructura_agua como si el corte siguiera activo. Se
# verifico contra las 436 fuentes de data/historico_fuentes_texto.jsonl que
# "hoy llego"/"ya llego" junto a "sin agua" es exclusivo de este articulo.
_MARCADORES_AGUA_RESTABLECIDA = ["hoy llego", "hoy llegó", "ya llego", "ya llegó"]


def _es_agua_restablecida_sin_falla_actual(texto_norm):
    if not (_contiene_palabra_clave(texto_norm, "sin agua")
            or _contiene_palabra_clave(texto_norm, "sin recibir agua")):
        return False
    return any(m in texto_norm for m in _MARCADORES_AGUA_RESTABLECIDA)


# Caso real (02-09-2026, PASADO_POR_FALLA_TECNICA): un decreto de la
# Gobernacion de Nueva Esparta declarando el 8 de septiembre dia no laborable
# por la festividad de la Virgen del Valle mencionaba, como dato historico,
# "el registro de su primer milagro documentado en 1608, cuando una
# procesion con la imagen sagrada puso fin a una severa sequia que azotaba a
# la region" -- una sequia de 1608 (418 anos antes de la publicacion)
# disparaba tipo=sequia como si fuera un evento actual. Se verifico contra
# las 436 fuentes de data/historico_fuentes_texto.jsonl que "milagro
# documentado" es exclusivo de este articulo.
_MARCADORES_SEQUIA_HISTORICA_RELIGIOSA = ["milagro documentado"]
_ANO_HISTORICO_RE = re.compile(r"\ben (1[0-9]{3})\b")


def _es_sequia_historica_religiosa(texto_norm):
    if not (_contiene_palabra_clave(texto_norm, "sequia") or _contiene_palabra_clave(texto_norm, "sequias")):
        return False
    if not any(m in texto_norm for m in _MARCADORES_SEQUIA_HISTORICA_RELIGIOSA):
        return False
    return _ANO_HISTORICO_RE.search(texto_norm) is not None


# Caso real (19-08-2026, PASADO_POR_FALLA_TECNICA): "71 Nuevos Bomberos Se
# Incorporan Al Cuerpo De Bomberos Del Estado Apure... egresados de la
# UNES... recibieron una preparacion integral que les permite responder
# eficazmente ante emergencias, INCENDIOS y situaciones de riesgo" -- una
# ceremonia de graduacion/incorporacion de nuevo personal (noticia
# institucional POSITIVA, sin ningun fuego real) disparaba tipo=incendio
# solo por la palabra "incendios" en la descripcion generica de las
# funciones del cuerpo de bomberos. Se evalua sobre el ARTICULO COMPLETO
# (no la ventana de proximidad): el marcador institucional suele estar en
# el titular/inicio, lejos de donde aparece la palabra "incendios" en la
# descripcion de funciones -- mismo motivo por el que
# _es_anuncio_corpoelec_sin_falla tambien se evalua sobre el articulo
# completo.
_MARCADORES_ANUNCIO_INSTITUCIONAL_BOMBEROS = [
    "nuevos bomberos", "nueva promocion de bomberos",
    "nueva promoción de bomberos", "egresados de la unes",
    "se incorporan al cuerpo de bomberos",
    # Ampliado (20-08-2026, PASADO_POR_FALLA_TECNICA): "Con misa y
    # reconocimientos conmemoran Dia del Bombero en Monagas... para honrar
    # a los 'heroes de azul y rojo'" -- un sub-patron distinto de anuncio
    # institucional positivo: no una graduacion de nuevos reclutas, sino la
    # conmemoracion anual del Dia Nacional del Bombero (misa, entrega de
    # reconocimientos), sin ningun incendio real en curso. El MISMO articulo
    # tambien disparaba tipo=sismo en La Guaira ("reconocio el esfuerzo...
    # por su apoyo a los afectados por los terremotos en La Guaira" -- apoyo
    # institucional a damnificados del terremoto de hace casi 2 meses, no un
    # sismo nuevo), de ahi que _es_anuncio_institucional_bomberos_sin_incendio_real
    # ahora acepte el tipo a verificar (ver esa funcion).
    "dia del bombero", "día del bombero", "dia nacional del bombero",
    "día nacional del bombero",
]


def _es_anuncio_institucional_bomberos_sin_incendio_real(texto_norm, tipo="incendio"):
    """`tipo` decide contra que lista de evidencia fuerte se compara (ver
    ampliacion 20-08-2026: el mismo anuncio institucional de bomberos puede
    colar tambien un tipo=sismo retrospectivo, via una mencion de
    "terremotos" en el contexto del apoyo institucional a damnificados, no
    solo tipo=incendio)."""
    if not any(m in texto_norm for m in _MARCADORES_ANUNCIO_INSTITUCIONAL_BOMBEROS):
        return False
    fuerte = _EVIDENCIA_FUERTE_POR_TIPO.get(tipo, [])
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


# Caso real (20-08-2026, PASADO_POR_FALLA_TECNICA): "El Mananero del 19 de
# agosto" (un digest matutino de RunRun.es, una lista de docenas de
# titulares no relacionados) incluye, entre otras notas, "Defensoria del
# Pueblo conforma mesa de seguimiento de apagones en el Zulia" -- la
# FORMACION de un comite de seguimiento es una accion administrativa/
# institucional, no la descripcion de un corte electrico nuevo en curso.
# A diferencia de _es_anuncio_corpoelec_sin_falla, no se puede usar
# _EVIDENCIA_FUERTE_POR_TIPO["infraestructura_electrica"] como lista de
# excepcion aqui: esa lista incluye "apagones" (para anular el filtro de
# "arbol" cuando SI hay evidencia real de corte cerca), pero "apagones" es
# precisamente la palabra dentro de la frase conflictiva misma ("mesa de
# seguimiento DE APAGONES"), lo que la volveria inutil. Se usa en su lugar
# una lista de evidencia fuerte propia, sin "apagon"/"apagones".
_MARCADORES_COMITE_SEGUIMIENTO_APAGONES = [
    "conforma mesa de seguimiento de apagones",
    "conformo mesa de seguimiento de apagones",
    "conformó mesa de seguimiento de apagones",
]
_EVIDENCIA_FUERTE_APAGON_SIN_APAGONES = [
    "sin luz", "sin electricidad", "sin energia electrica",
    "sin energía eléctrica", "sin servicio electrico",
    "sin servicio eléctrico", "falla electrica", "falla eléctrica",
    "fallas electricas", "fallas eléctricas", "restablecer el suministro",
    "restablecer el servicio", "corte de luz", "cortes de luz",
]


def _es_formacion_comite_seguimiento_apagones_sin_falla_real(texto_norm):
    if not any(_contiene_palabra_clave(texto_norm, m) for m in _MARCADORES_COMITE_SEGUIMIENTO_APAGONES):
        return False
    return not any(_contiene_palabra_clave(texto_norm, f) for f in _EVIDENCIA_FUERTE_APAGON_SIN_APAGONES)


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
    # Ampliado (15-08-2026, PASADO_POR_FALLA_TECNICA): "Las protestas en
    # Venezuela se dispararon 181%... Según el más reciente informe del
    # Observatorio Venezolano de Conflictividad Social (OVCS)... Distrito
    # Capital concentro el mayor numero de protestas (462), seguido por
    # Miranda (414), Sucre (274), Bolivar (265) y Lara (263)" -- un informe
    # estadistico nacional que reparte cifras agregadas de un SEMESTRE
    # entero entre 5+ estados generaba alertas nuevas de orden_publico en
    # Lara, Miranda y Sucre, sin ningun hecho puntual de hoy en ninguno de
    # ellos (mismo patron que el mapa de un tercero: una cifra/reclamo
    # repartido entre muchos estados, no una protesta especifica y actual).
    # El marcador exige "informe del" antes del nombre del observatorio (no
    # solo la mencion de la institucion) para no afectar articulos de
    # cobertura LOCAL de una noche puntual que solo citan al OVCS como
    # corroboracion secundaria de un hecho ya descrito con evidencia propia
    # (caso real ya cubierto, 07-08-2026: "Protestas en siete estados...
    # en La Isabelica, municipio Valencia... En San Mateo, Aragua, tambien
    # protestaron... El Observatorio Venezolano de Conflictividad Social
    # (OVCS), por su parte, registro un total de 11 protestas en ocho
    # estados" -- ese articulo SI describe hechos locales puntuales, la
    # mencion del OVCS es solo un dato adicional, no el eje del articulo).
    "informe del observatorio venezolano de conflictividad social",
    # Ampliado (18-08-2026, PASADO_POR_FALLA_TECNICA): un articulo sobre
    # inundaciones REALES y puntuales en Acarigua-Araure (Portuguesa) cierra
    # con el boletin de pronostico rutinario del Inameh, que enumera 19
    # estados de lluvia PRONOSTICADA para las proximas horas ("...que
    # abarcaran los estados Bolivar, Amazonas, Monagas, Sucre... y Zulia...
    # que afectaran las regiones de Bolivar, Amazonas, Delta Amacuro...").
    # A diferencia de _es_boletin_pronostico_inameh_sin_inundacion_real()
    # (que exige AUSENCIA total de evidencia fuerte de inundacion en el
    # articulo, y por eso no aplica aqui -- el articulo SI tiene evidencia
    # real, solo que para Portuguesa, no para los demas 18 estados
    # enumerados), este mecanismo de proximidad SI distingue: Portuguesa se
    # mantiene porque su mencion real (con "anegaron", lejos de la lista de
    # pronostico) sigue encontrando una ventana valida antes que la del
    # pronostico, mientras que Zulia -- mencionado UNICAMENTE dentro de la
    # lista de pronostico -- se descarta por falta de evidencia local
    # especifica cerca de esa unica mencion.
    "abarcaran los estados", "abarcarán los estados",
    "afectaran las regiones de", "afectarán las regiones de",
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
    # Ampliado (19-08-2026): "destaco"/"destacó" faltaba -- ver caso real
    # de "Vargas" mas abajo.
    "destaco", "destacó",
    # Ampliado (02-09-2026, PASADO_POR_FALLA_TECNICA): un reportaje sobre
    # sequia citaba varias veces a un meteorologo de apellido "Vargas"
    # (alias de La Guaira) en tiempo PRESENTE/plural, formas no cubiertas
    # por la lista original (solo pasado/3a persona singular): "«...»,
    # DICE Vargas", "Datos aportado por Vargas SEÑALAN que...", "Vargas
    # REFIERE que...". Ver tambien el chequeo de "por Nombre" mas abajo en
    # _es_mencion_de_persona_citada, para "lo explicado POR Vargas".
    "dice", "senalan", "refiere",
}

# Ampliado (19-08-2026, PASADO_POR_FALLA_TECNICA): el chequeo original solo
# miraba la palabra INMEDIATAMENTE antes/despues del nombre, lo que no
# cubre el patron, muy comun en prensa venezolana, de "Nombre Apellido,
# cargo o descripcion breve, VERBO_DE_CITA que..." -- el verbo casi nunca
# queda pegado al nombre. Caso real: "Julio Cesar Vargas, directivo
# principal de Criabufalos de Venezuela, destaco el valor estrategico de
# la iniciativa" generaba una alerta de salud publica en el estado La
# Guaira (alias "Vargas") en un articulo que trata enteramente sobre un
# censo de ganado bovino en Apure -- "Vargas" es apellido del vocero
# citado, no el estado. Se busca el verbo de atribucion hasta 12 tokens
# despues del nombre (suficiente para cubrir un cargo/titulo breve entre
# comas, sin extenderse tanto que empiece a alcanzar la cita de OTRA
# persona mencionada mas adelante en el articulo).
_VENTANA_VERBO_ATRIBUCION_CITA = 12

# Ampliado (02-09-2026, PASADO_POR_FALLA_TECNICA): las dos ampliaciones de
# arriba no bastaban para dos construcciones reales mas del mismo articulo
# de "Vargas" meteorologo:
# 1) "..., dijo Luis Vargas, meteorologo consultado..." -- el verbo de cita
#    precede al NOMBRE DE PILA, no al apellido/alias de estado, quedando 2
#    tokens antes de "Vargas" en vez de justo antes.
# 2) "De acuerdo con lo explicado por Vargas, la sequia..." -- construccion
#    pasiva "PARTICIPIO por NOMBRE", donde el participio (no un verbo
#    conjugado) es la señal de cita, y precede a "por", no al nombre.
# _PARTICIPIOS_ATRIBUCION_CITA cubre el patron 2. Para el patron 1 se exige
# ademas que la palabra intermedia (el supuesto nombre de pila) NO sea una
# palabra funcional comun -- de lo contrario "declaro que Bolivar sufre..."
# (un verbo de cita seguido de "que" + el estado real, sin ningun nombre de
# persona) se excluiria por error.
_PARTICIPIOS_ATRIBUCION_CITA = {
    "explicado", "dicho", "senalado", "indicado", "declarado", "afirmado",
    "manifestado", "comentado", "sostenido", "denunciado", "advertido",
    "reiterado", "destacado", "precisado", "aportado", "referido",
}
_PALABRAS_FUNCIONALES_NO_NOMBRE = {
    "que", "de", "del", "en", "con", "por", "para", "y", "o", "a", "al",
    "la", "el", "los", "las", "un", "una", "se", "su", "sus", "mas", "más",
    "pero", "si", "no", "ya", "es", "esta", "está", "fue", "ha", "han",
}


def _es_mencion_de_persona_citada(tokens, pos):
    """True si la mencion en `pos` de un nombre de estado que tambien es un
    apellido comun esta en realidad atribuyendo una cita a una persona
    (ver comentario arriba), no nombrando el estado. Exige que la palabra
    inmediatamente anterior no sea un calificador de lugar conocido (para
    no descartar lugares reales como "Ciudad Bolivar" o "estado Bolivar")
    Y que haya un verbo de atribucion de cita justo antes, justo despues,
    o dentro de una ventana corta despues (ver _VENTANA_VERBO_ATRIBUCION_CITA),
    o alguna de las dos construcciones de dos tokens antes (ver comentario
    arriba)."""
    anterior = tokens[pos - 1] if pos > 0 else ""
    if anterior in _CALIFICADORES_LUGAR_ANTES_DE_NOMBRE:
        return False
    if anterior in _VERBOS_ATRIBUCION_CITA:
        return True
    ventana_siguiente = tokens[pos + 1: pos + 1 + _VENTANA_VERBO_ATRIBUCION_CITA]
    if any(t in _VERBOS_ATRIBUCION_CITA for t in ventana_siguiente):
        return True
    if pos >= 2:
        anterior2 = tokens[pos - 2]
        if anterior == "por" and anterior2 in _PARTICIPIOS_ATRIBUCION_CITA:
            return True
        if anterior2 in _VERBOS_ATRIBUCION_CITA and anterior not in _PALABRAS_FUNCIONALES_NO_NOMBRE:
            return True
    return False


# Caso real (20-08-2026, PASADO_POR_FALLA_TECNICA): "el Gobierno
# estadounidense afirmo que los migrantes estaban vinculados con la
# organizacion criminal Tren de Aragua" -- en un articulo sobre
# deportaciones de venezolanos a Liberia, sin ningun hecho local en el
# estado Aragua -- disparaba ubicacion=Aragua solo por el nombre del grupo
# criminal transnacional "Tren de Aragua" (frecuente en coberturas de
# migracion/seguridad), no el estado. Igual que _es_mencion_de_persona_citada,
# se filtra en la deteccion de posiciones para no anclar ninguna ventana
# ahi.
def _es_mencion_tren_de_aragua(tokens, pos):
    return pos >= 2 and tokens[pos - 1] == "de" and tokens[pos - 2] == "tren"


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
        and not _es_mencion_tren_de_aragua(tokens, i)
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
                if tipo == "sismo" and _es_taller_salud_mental_post_sismo_sin_evidencia_real(texto_completo_norm):
                    break
                if tipo == "sismo" and _es_anuncio_institucional_bomberos_sin_incendio_real(texto_completo_norm, "sismo"):
                    break
                if tipo == "tsunami" and _es_nombre_institucional_tsunami_sin_evidencia_real(texto_completo_norm):
                    break
                if tipo == "tsunami" and _es_tsunami_descartado_explicitamente(texto_completo_norm):
                    break
                if tipo == "salud_publica" and _es_boletin_estadistico_salud_sin_alarma(texto_completo_norm):
                    break
                if tipo == "orden_publico" and _es_manifestacion_pacifica_sin_evidencia_fuerte(texto_completo_norm):
                    break
                if tipo == "orden_publico" and _es_presentacion_libro_memoria_sin_disturbio_actual(texto_completo_norm):
                    break
                if tipo == "infraestructura_electrica" and _es_anuncio_corpoelec_sin_falla(texto_completo_norm):
                    break
                if tipo == "infraestructura_electrica" and _es_formacion_comite_seguimiento_apagones_sin_falla_real(texto_completo_norm):
                    break
                if tipo == "infraestructura_electrica" and _es_queja_cronica_electrica_sin_hecho_verificable(texto_completo_norm):
                    break
                if tipo == "explosion" and _es_cartucho_lacrimogeno_sin_explosivo_real(texto_completo_norm):
                    break
                if tipo == "explosion" and _es_falsa_alarma_sin_explosivo_real(texto_completo_norm):
                    break
                if tipo == "ataque_armado" and _es_captura_fugitivo_sin_ataque_en_curso(texto_completo_norm):
                    break
                if tipo == "inundacion" and _es_boletin_pronostico_inameh_sin_inundacion_real(texto_completo_norm):
                    break
                if tipo == "deslizamiento" and _es_derrumbe_de_techo_no_deslizamiento(texto_completo_norm):
                    break
                if tipo == "deslizamiento" and _es_limpieza_escombros_terremoto_sin_deslizamiento_real(texto_completo_norm):
                    break
                if tipo == "infraestructura_electrica" and _es_protesta_electrica_con_tipo_incorrecto(texto_completo_norm):
                    break
                if tipo == "incendio" and _es_anuncio_institucional_bomberos_sin_incendio_real(texto_completo_norm):
                    break
                if tipo == "emergencia_metro" and _es_anuncio_tarifario_metro_sin_falla_real(texto_completo_norm):
                    break
                if tipo == "infraestructura_agua" and _es_agua_restablecida_sin_falla_actual(texto_completo_norm):
                    break
                if tipo == "sequia" and _es_sequia_historica_religiosa(texto_completo_norm):
                    break
                if not _tipo_con_contexto_conflictivo(fuente_norm, tipo):
                    tipos_encontrados.append(tipo)
                break
    # Ver _es_derrumbe_de_techo_no_deslizamiento() y
    # _es_protesta_electrica_con_tipo_incorrecto(): a diferencia de los
    # demas filtros decisivos de arriba (que solo descartan el tipo), estos
    # SI reclasifican -- el hecho sigue siendo una emergencia real, solo que
    # del tipo correcto, asi que se agrega el tipo correcto en vez de
    # dejar el evento sin ningun tipo.
    if "colapso_estructural" not in tipos_encontrados and _es_derrumbe_de_techo_no_deslizamiento(texto_completo_norm):
        tipos_encontrados.append("colapso_estructural")
    if "orden_publico" not in tipos_encontrados and _es_protesta_electrica_con_tipo_incorrecto(texto_completo_norm):
        tipos_encontrados.append("orden_publico")
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
        if "sismo" in nuevo["tipos"] and _es_sismo_extranjero_con_epicentro_conocido_sin_municipio(texto_norm, nuevo["municipio"]):
            continue
        if "sequia" in nuevo["tipos"] and _es_sequia_atribuida_a_otro_estado(texto_norm, ubicacion):
            nuevo["tipos"] = [t for t in nuevo["tipos"] if t != "sequia"]
            if not nuevo["tipos"]:
                continue
        if "deslizamiento" in nuevo["tipos"] and _es_derrumbe_atribuido_a_otro_estado(texto_norm, ubicacion):
            nuevo["tipos"] = [t for t in nuevo["tipos"] if t != "deslizamiento"]
            if not nuevo["tipos"]:
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
