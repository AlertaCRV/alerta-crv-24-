"""Pruebas de scripts/verify.py -- agrupacion de fuentes del mismo evento.

Cada caso reproduce un hallazgo real ya documentado en
docs/roadmap_evolucion.md.
"""

from classify import clasificar_item
from verify import agrupar_y_verificar


def _item_de(fecha, texto, indice, ubicacion="Falcon"):
    # El texto menciona tanto "La Guaira" (procedencia) como "Falcon"
    # (destino) -- clasificar_item() devuelve un item por cada estado
    # mencionado (division multiestado), asi que hay que elegir el de
    # Falcon explicitamente en vez de asumir un solo resultado.
    resultado = clasificar_item({"texto": texto})
    item = next(r for r in resultado if r.get("ubicacion") == ubicacion)
    item["fecha"] = fecha
    item["fuente_nombre"] = f"Reporte de filial ({fecha[:10]})"
    item["peso"] = 1.5
    item["link"] = f"fuente-{indice}"
    item["fuente_tipo"] = "correo"
    return item


def test_municipio_y_parroquia_no_se_mezclan_entre_fuentes_distintas():
    # Caso real (30-07-2026): 3 reportes de la misma filial sobre el mismo
    # grupo de personas desplazadas. El mas reciente dice "municipio
    # Zamora" (sin parroquia); uno mas viejo dice "parroquia Las Calderas,
    # municipio Colina". Antes del fix, el evento fusionado terminaba en
    # "Municipio Zamora, Parroquia Las Calderas" -- una combinacion que no
    # existe (Las Calderas es parroquia de Colina, no de Zamora), porque
    # municipio y parroquia se elegian cada uno por separado del miembro
    # mas reciente que tuviera ESE campo, sin exigir que vinieran del
    # mismo lugar real.
    textos = [
        (
            "2026-07-07T16:00:00+00:00",
            "Familias que salieron de su lugar de origen en el estado La "
            "Guaira se encuentran ahora en parroquia Las Calderas, "
            "municipio Colina, estado Falcon, como personas desplazadas.",
        ),
        (
            "2026-07-28T16:00:00+00:00",
            "Familias que salieron de su lugar de origen en el estado La "
            "Guaira se encuentran ahora en municipio Colina, estado "
            "Falcon, como personas desplazadas.",
        ),
        (
            "2026-07-29T16:17:25+00:00",
            "Familias que salieron de su lugar de origen en el estado La "
            "Guaira se encuentran ahora en municipio Zamora, estado "
            "Falcon, como personas desplazadas.",
        ),
    ]
    items = [_item_de(fecha, texto, i) for i, (fecha, texto) in enumerate(textos)]

    eventos = agrupar_y_verificar(items)

    assert len(eventos) == 1
    evento = eventos[0]
    assert evento["municipio"] == "Zamora"
    # Las Calderas es parroquia de Colina, no de Zamora -- nunca debe
    # aparecer emparejada con Zamora, aunque sea la unica parroquia
    # mencionada en todo el cluster.
    assert evento["parroquia"] is None


def test_parroquia_se_conserva_si_coincide_con_el_municipio_elegido():
    # Caso de control: si dos fuentes distintas coinciden en el MISMO
    # municipio, una parroquia mencionada por una fuente mas vieja (pero
    # del mismo municipio) sigue siendo valida y no debe perderse.
    textos = [
        (
            "2026-07-28T16:00:00+00:00",
            "Familias que salieron de su lugar de origen en el estado La "
            "Guaira se encuentran ahora en municipio Colina, estado "
            "Falcon, como personas desplazadas.",
        ),
        (
            "2026-07-07T16:00:00+00:00",
            "Familias que salieron de su lugar de origen en el estado La "
            "Guaira se encuentran ahora en parroquia Las Calderas, "
            "municipio Colina, estado Falcon, como personas desplazadas.",
        ),
    ]
    items = [_item_de(fecha, texto, i) for i, (fecha, texto) in enumerate(textos)]

    eventos = agrupar_y_verificar(items)

    assert len(eventos) == 1
    evento = eventos[0]
    assert evento["municipio"] == "Colina"
    assert evento["parroquia"] == "Las Calderas"
