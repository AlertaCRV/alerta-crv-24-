"""Pruebas de los filtros deterministas de verify_ai.py -- corren ANTES de
la llamada a la IA y no dependen de que Groq este disponible, asi que son
puras funciones de texto, faciles de probar sin mockear la API.

Cada caso reproduce un hallazgo real ya documentado en
docs/roadmap_evolucion.md (citado en cada test) mas su contraparte de
control, para que una futura modificacion de estos filtros no reabra el
mismo falso positivo/negativo.
"""

from verify_ai import (
    _deslizamiento_estructura_sin_evidencia_fuerte,
    _es_retrospectiva_obvia,
    _incendio_vehiculo_sin_evidencia_fuerte,
    _sismo_sin_evidencia_fuerte,
    _vialidad_sin_evidencia_fuerte,
)


# --- vialidad: "Filtro determinista para vialidad" (26-07-2026) ---------

def test_vialidad_choque_individual_con_fallecido_se_descarta():
    # Caso real: choque entre dos motorizados con un fallecido, se habia
    # publicado como severidad CRITICA sin ser un accidente masivo.
    texto = "Un choque entre dos motorizados dejo un fallecido en la autopista."
    assert _vialidad_sin_evidencia_fuerte(texto) is True


def test_vialidad_accidente_masivo_no_se_descarta():
    texto = "Colision multiple en la autopista deja varios heridos y un autobus accidentado."
    assert _vialidad_sin_evidencia_fuerte(texto) is False


def test_vialidad_transporte_publico_no_se_descarta():
    texto = "Volcamiento de autobus deja pasajeros lesionados en la via."
    assert _vialidad_sin_evidencia_fuerte(texto) is False


# --- incendio vehicular: "Dos falsos positivos mas" (27-07-2026) --------

def test_incendio_gandola_aislada_se_descarta():
    # Caso real: una gandola incendiada en la autopista, incidente
    # vehicular rutinario, no una emergencia.
    texto = "Una gandola se incendio en la autopista, generando congestionamiento."
    assert _incendio_vehiculo_sin_evidencia_fuerte(texto) is True


def test_incendio_vehiculo_requiere_ambas_condiciones_a_la_vez():
    # Accidente multiple SIN victimas mencionadas: sigue descartandose --
    # el usuario pidio explicitamente que ambas condiciones se cumplan a
    # la vez, no basta una sola (a diferencia del filtro de vialidad).
    texto = "Accidente multiple entre varios vehiculos genero un incendio en la autopista."
    assert _incendio_vehiculo_sin_evidencia_fuerte(texto) is True


def test_incendio_vehiculo_multiple_y_victimas_no_se_descarta():
    texto = "Accidente multiple entre varios vehiculos genero un incendio con varios heridos."
    assert _incendio_vehiculo_sin_evidencia_fuerte(texto) is False


def test_incendio_forestal_no_pasa_por_este_filtro():
    texto = "Un incendio forestal consume varias hectareas de vegetacion."
    assert _incendio_vehiculo_sin_evidencia_fuerte(texto) is False


# --- deslizamiento vs. colapso estructural viejo: (28-07-2026) ----------

def test_derrumbe_de_pared_por_filtraciones_se_descarta():
    # Caso real: colapso de una pared de iglesia por filtraciones de años,
    # sin lluvia ni movimiento de tierra -- se habia clasificado como
    # deslizamiento solo por la palabra "derrumbe".
    texto = "Filtraciones y humedad generan colapso parcial en iglesia San Fernando Rey de Ospino."
    assert _deslizamiento_estructura_sin_evidencia_fuerte(texto) is True


def test_derrumbe_de_tierra_por_lluvia_no_se_descarta():
    texto = "Fuertes lluvias provocaron un derrumbe de tierra que bloqueo la via, ladera abajo."
    assert _deslizamiento_estructura_sin_evidencia_fuerte(texto) is False


# --- sismo: "Filtro determinista para sismos" (26-07-2026) --------------

def test_sismo_menor_sin_dano_se_descarta():
    texto = "Un sismo de magnitud 3.2 se registro en el oriente del pais."
    assert _sismo_sin_evidencia_fuerte(texto, "Medio Cualquiera") is True


def test_sismo_fuerte_y_sentido_no_se_descarta():
    texto = "Un sismo de magnitud 5.5 se sintio con fuerza en la capital."
    assert _sismo_sin_evidencia_fuerte(texto, "Medio Cualquiera") is False


def test_sismo_con_dano_real_no_se_descarta_sin_importar_magnitud():
    texto = "Un temblor dejo heridos y una vivienda colapsada, aunque su magnitud fue menor."
    assert _sismo_sin_evidencia_fuerte(texto, "Medio Cualquiera") is False


def test_sismo_fuente_sismologica_oficial_no_se_descarta():
    texto = "Un sismo de magnitud 4.5 se registro en la region occidental."
    assert _sismo_sin_evidencia_fuerte(texto, "FUNVISIS") is False


# --- retrospectiva obvia (aniversario/"N meses despues") ----------------

def test_aniversario_de_sismo_es_retrospectiva():
    texto = "A un mes del terremoto en Vargas, continuan las labores de reconstruccion."
    assert _es_retrospectiva_obvia(texto) is True


def test_doblete_sismico_es_retrospectiva():
    # Caso real: "tras el doblete sismico, los rescatistas encontraron..."
    # -- variante de redaccion que el patron original no cubria.
    texto = "Tras el doblete sismico, los rescatistas encontraron un autobus bajo los escombros."
    assert _es_retrospectiva_obvia(texto) is True


def test_sismo_nuevo_no_es_retrospectiva():
    texto = "Un sismo de magnitud 5.0 sacudio la region esta madrugada."
    assert _es_retrospectiva_obvia(texto) is False


def test_dia_n_posterior_a_es_retrospectiva():
    # Caso real (05-08-2026, La Guaira): rescate de cuerpos "en el dia 41
    # posterior a los terremotos... del pasado 24 de junio" se publico
    # como un sismo NUEVO -- es la unidad de tiempo ANTES del numero
    # ("dia 41 posterior a"), variante que el patron original ("41 dias
    # despues") no cubria.
    texto = (
        "La extraccion de estos cuerpos se concreto en el dia 41 posterior "
        "a los terremotos de magnitudes 7.5 y 7.2 que azotaron el territorio "
        "nacional el pasado 24 de junio."
    )
    assert _es_retrospectiva_obvia(texto) is True


# --- municipio/parroquia del cluster deben aparecer en las fuentes -------
# aprobadas, no solo en cualquier miembro del cluster crudo (31-07-2026) ---

from verify_ai import _finalizar_evento  # noqa: E402


def _miembro(texto, fuente_nombre="Fuente", peso=0.6, fecha="2026-07-31T12:00:00+00:00",
             link="https://ejemplo.com", severidad="sin_clasificar"):
    return {
        "texto": texto, "fuente_nombre": fuente_nombre, "peso": peso,
        "fecha": fecha, "link": link, "severidad": severidad,
    }


def test_municipio_del_cluster_se_descarta_si_ninguna_fuente_aprobada_lo_nombra():
    # Caso real (31-07-2026): un cluster de "incendio en Distrito Capital"
    # tenia una fuente aprobada sobre el CCCT (sin nombrar ningun
    # municipio) y otra fuente del mismo cluster, sobre un hecho distinto,
    # que si mencionaba "Parroquia La Vega, Municipio Libertador" -- esa
    # fuente fue rechazada por la IA (no es el mismo hecho), pero el evento
    # publicado terminaba con esa parroquia/municipio de todos modos,
    # porque verify.agrupar_y_verificar() los fija ANTES de saber cuales
    # fuentes se aprobarian.
    evento = {
        "tipo": "incendio", "ubicacion": "Distrito Capital",
        "municipio": "Libertador", "parroquia": "La Vega",
    }
    aprobado = _miembro("Incendio en el CCCT, en el este de Caracas, cinco personas afectadas.")
    grupos_aprobados = [[aprobado]]
    resultado = _finalizar_evento(evento, grupos_aprobados)
    assert resultado["municipio"] is None
    assert resultado["parroquia"] is None


def test_municipio_del_cluster_se_conserva_si_la_fuente_aprobada_lo_nombra():
    evento = {
        "tipo": "incendio", "ubicacion": "Miranda",
        "municipio": "Chacao", "parroquia": None,
    }
    aprobado = _miembro("Incendio en el CCCT, ubicado en el municipio Chacao.")
    grupos_aprobados = [[aprobado]]
    resultado = _finalizar_evento(evento, grupos_aprobados)
    assert resultado["municipio"] == "Chacao"
