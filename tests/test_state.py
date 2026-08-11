"""Pruebas de scripts/state.py -- deduplicacion de eventos entre corridas.

Cada caso reproduce un hallazgo real ya documentado en
docs/roadmap_evolucion.md.
"""

from state import _resolver_clave, filtrar_nuevos


def _evento(tipo, ubicacion, fecha_evento_temprana, severidad="alto", confirmado=True, magnitud=None):
    evento = {
        "tipo": tipo,
        "ubicacion": ubicacion,
        "severidad": severidad,
        "confirmado": confirmado,
        "fecha_evento": fecha_evento_temprana,
        "fecha_evento_temprana": fecha_evento_temprana,
        "fecha_deteccion": fecha_evento_temprana,
    }
    if magnitud is not None:
        evento["magnitud"] = magnitud
    return evento


def test_incendio_no_reutiliza_clave_de_otro_incendio_distinto():
    # Caso real (30-07-2026): una explosion de gas en la avenida Nueva
    # Granada (29-07, 17:06, "alto", dos heridos, ya publicada y
    # corroborada por 3 fuentes) quedo sobrescrita al dia siguiente por un
    # incendio COMPLETAMENTE DISTINTO (una libreria del CCCT, 30-07,
    # 14:46) solo porque ambos son tipo=incendio, ubicacion=Distrito
    # Capital, dentro de la ventana de 36h de "mismo evento" -- la alerta
    # original desaparecio del sitio publico sin dejar rastro.
    publicados = {}
    explosion_gas = _evento("incendio", "Distrito Capital", "2026-07-29T17:06:27+00:00")
    clave_explosion = _resolver_clave(explosion_gas, publicados)
    publicados[clave_explosion] = {
        "severidad": explosion_gas["severidad"],
        "confirmado": explosion_gas["confirmado"],
        "fecha_deteccion": explosion_gas["fecha_deteccion"],
        "fecha_evento_temprana": explosion_gas["fecha_evento_temprana"],
    }

    incendio_ccct = _evento("incendio", "Distrito Capital", "2026-07-30T14:46:56+00:00")
    clave_ccct = _resolver_clave(incendio_ccct, publicados)

    assert clave_ccct != clave_explosion, (
        "un incendio distinto en el mismo estado, dentro de 36h del anterior, "
        "no debe reutilizar la clave del primero -- se perderia la alerta original"
    )


def test_inundacion_si_reutiliza_clave_del_mismo_evento_en_curso():
    # Caso de control: la ventana de "mismo evento" sigue funcionando para
    # tipos NO excluidos -- dos fuentes distintas sobre la misma inundacion
    # en curso, separadas por unas horas y corridas distintas, deben seguir
    # tratandose como un solo evento (no uno duplicado por cada fuente).
    publicados = {}
    primer_reporte = _evento("inundacion", "Zulia", "2026-07-27T12:00:00+00:00")
    clave_primera = _resolver_clave(primer_reporte, publicados)
    publicados[clave_primera] = {
        "severidad": primer_reporte["severidad"],
        "confirmado": primer_reporte["confirmado"],
        "fecha_deteccion": primer_reporte["fecha_deteccion"],
        "fecha_evento_temprana": primer_reporte["fecha_evento_temprana"],
    }

    reporte_seguimiento = _evento("inundacion", "Zulia", "2026-07-28T10:00:00+00:00")
    clave_seguimiento = _resolver_clave(reporte_seguimiento, publicados)

    assert clave_seguimiento == clave_primera


def test_filtrar_nuevos_no_descarta_incendio_distinto_por_severidad_igual():
    # filtrar_nuevos() solo republica un evento con clave repetida si subio
    # de severidad o confirmacion -- con incendio ahora excluido de la
    # ventana de "mismo evento", un segundo incendio real con la MISMA
    # severidad que uno ya publicado (caso realista: ambos "sin_clasificar")
    # debe seguir contando como nuevo, no descartarse por parecer una
    # actualizacion sin cambios del primero.
    publicados = {}
    primero = _evento("incendio", "Distrito Capital", "2026-07-29T17:06:27+00:00", severidad="alto")
    nuevos = filtrar_nuevos([primero], publicados)
    assert len(nuevos) == 1
    for evento in nuevos:
        publicados[evento["clave_dedup"]] = {
            "severidad": evento["severidad"],
            "confirmado": evento["confirmado"],
            "fecha_deteccion": evento["fecha_deteccion"],
            "fecha_evento_temprana": evento["fecha_evento_temprana"],
        }

    segundo = _evento("incendio", "Distrito Capital", "2026-07-30T14:46:56+00:00", severidad="alto")
    nuevos_2 = filtrar_nuevos([segundo], publicados)
    assert len(nuevos_2) == 1
    assert nuevos_2[0]["clave_dedup"] != primero["clave_dedup"]


def test_sismo_mismo_estado_con_magnitud_revisada_no_se_duplica():
    # Caso real (10-08-2026): el mismo sismo de Colombia sentido en Zulia se
    # publico primero con la magnitud ya revisada por el Servicio Geologico
    # Colombiano (7.4, 14:34 UTC) y, mas de 3 horas despues, otra fuente lo
    # reporto de nuevo usando la magnitud preliminar aun no actualizada
    # (6.6, 17:40 UTC) -- mismo estado, mismo dia, mismo sismo real, pero la
    # magnitud distinta en la clave (`_clave_evento`) lo hacia pasar como una
    # alerta nueva. `_mismo_sismo_ya_publicado()` debe descartarlo.
    publicados = {}
    primer_reporte = _evento("sismo", "Zulia", "2026-08-10T13:30:20+00:00", magnitud=7.4)
    nuevos = filtrar_nuevos([primer_reporte], publicados)
    assert len(nuevos) == 1

    segundo_reporte = _evento("sismo", "Zulia", "2026-08-10T15:03:26+00:00", magnitud=6.6)
    nuevos_2 = filtrar_nuevos([segundo_reporte], publicados)
    assert nuevos_2 == []


def test_sismo_otro_estado_con_magnitud_distinta_si_es_evento_nuevo():
    # Control: un sismo real DISTINTO (magnitud distinta y ningun indicio de
    # ser el mismo evento) en un estado que ya tuvo un sismo publicado ese
    # mismo dia sigue contando como una alerta nueva -- el fix no debe
    # fusionar dos sismos genuinamente diferentes solo por coincidir tipo y
    # estado el mismo dia calendario.
    publicados = {}
    primer_reporte = _evento("sismo", "Zulia", "2026-08-10T13:30:20+00:00", magnitud=7.4)
    filtrar_nuevos([primer_reporte], publicados)

    segundo_estado = _evento("sismo", "Tachira", "2026-08-10T16:00:00+00:00", magnitud=5.1)
    nuevos = filtrar_nuevos([segundo_estado], publicados)
    assert len(nuevos) == 1


def test_sismo_mismo_estado_dia_siguiente_no_se_duplica():
    # Caso real (11-08-2026): el mismo sismo de Colombia sentido en Zulia
    # (mag 7.4, ocurrido el lunes 10-08) genero una TERCERA alerta un dia
    # despues -- una fuente (Notiapure) publico el martes 11-08 una nota de
    # reaccion ("Habitantes de Maracaibo evacuaron preventivamente...")
    # cuya fecha_evento_temprana (fecha de PUBLICACION de esa nota, no del
    # sismo en si) cae en el dia calendario siguiente. Antes del fix,
    # `_mismo_sismo_ya_publicado()` exigia el mismo dia EXACTO (partes[2]
    # != fecha_dia) y no encontraba el reporte original del dia anterior.
    publicados = {}
    primer_reporte = _evento("sismo", "Zulia", "2026-08-10T14:34:38+00:00", magnitud=7.4)
    nuevos = filtrar_nuevos([primer_reporte], publicados)
    assert len(nuevos) == 1

    reporte_dia_siguiente = _evento("sismo", "Zulia", "2026-08-11T20:26:22+00:00", magnitud=7.4)
    nuevos_2 = filtrar_nuevos([reporte_dia_siguiente], publicados)
    assert nuevos_2 == []


def test_sismo_mismo_estado_muy_separado_en_el_tiempo_si_es_evento_nuevo():
    # Control: un sismo real DISTINTO en el mismo estado, separado por mas
    # de 1 dia calendario del anterior, sigue contando como una alerta
    # nueva -- la tolerancia de +/-1 dia agregada para el caso de arriba no
    # debe fusionar sismos separados por semanas/meses solo por compartir
    # estado.
    publicados = {}
    primer_reporte = _evento("sismo", "Zulia", "2026-08-10T14:34:38+00:00", magnitud=7.4)
    filtrar_nuevos([primer_reporte], publicados)

    reporte_lejano = _evento("sismo", "Zulia", "2026-08-20T09:00:00+00:00", magnitud=6.0)
    nuevos = filtrar_nuevos([reporte_lejano], publicados)
    assert len(nuevos) == 1
