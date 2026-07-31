"""Pruebas de scripts/state.py -- deduplicacion de eventos entre corridas.

Cada caso reproduce un hallazgo real ya documentado en
docs/roadmap_evolucion.md.
"""

from state import _resolver_clave, filtrar_nuevos


def _evento(tipo, ubicacion, fecha_evento_temprana, severidad="alto", confirmado=True):
    return {
        "tipo": tipo,
        "ubicacion": ubicacion,
        "severidad": severidad,
        "confirmado": confirmado,
        "fecha_evento": fecha_evento_temprana,
        "fecha_evento_temprana": fecha_evento_temprana,
        "fecha_deteccion": fecha_evento_temprana,
    }


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
