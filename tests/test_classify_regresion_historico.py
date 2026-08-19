"""Regresion automatica de classify.py contra el texto real de TODAS las
fuentes ya publicadas y auditadas en data/historico_fuentes_texto.jsonl.

Esto automatiza un paso que, hasta ahora, cada sesion de auditoria repetia
a mano con un script de una sola vez: "se corrio una regresion contra las
N fuentes ya publicadas, ningun otro caso cambio de resultado salvo el
corregido aqui" (ver docs/roadmap_evolucion.md, aparece en casi cada
entrada desde el 27-07-2026). Al leer el archivo en vivo (no una copia
fija), esta prueba crece sola con cada nuevo evento que se publica y
audita -- sin necesidad de portar casos a mano.

Solo se afirma "el tipo ya conocido esta entre los tipos detectados"
(tipos_incluye), no una lista exacta ni la severidad: cada linea de
historico_fuentes_texto.jsonl guarda el tipo/severidad del EVENTO ya
fusionado (puede combinar varias fuentes), no necesariamente el resultado
exacto de clasificar una sola fuente por separado. Para aserciones
exactas y curadas caso por caso, ver test_classify_casos.py.
"""

import json
import pathlib

import pytest

from classify import clasificar_item

RAIZ = pathlib.Path(__file__).resolve().parent.parent
HISTORICO_PATH = RAIZ / "data" / "historico_fuentes_texto.jsonl"

# Limitaciones YA CONOCIDAS y documentadas en docs/roadmap_evolucion.md
# ("División de artículos multiestado en alertas independientes",
# 27-07-2026: "la separación mejora sustancialmente pero no es perfecta"),
# no bugs nuevos: una fuente aislada puede resolver a un solo estado de un
# corredor que menciona dos a la vez sin puntuacion entre ellos (p.ej.
# "Barinas-Mérida"), mientras el EVENTO fusionado (con otras fuentes que sí
# nombran ambos estados por separado) sí queda con la ubicacion correcta.
# Se marcan como xfail (no bloquean la suite) en vez de excluirse: si algun
# dia esto se corrige, aparecera como XPASS y se debe quitar de esta lista.
_LIMITACIONES_CONOCIDAS = {
    "deslizamiento::Barinas::Primicia (Bolivar)": (
        "Corredor 'Barinas-Mérida' sin puntuacion entre ambos nombres de "
        "estado; esta fuente aislada resuelve solo a Merida. El evento "
        "publicado es correcto porque se fusiona con otras fuentes que sí "
        "nombran Barinas explicitamente (ver verify.agrupar_y_verificar)."
    ),
    # Caso real (31-07-2026): el incendio del CCCT esta en el municipio
    # Chacao (estado Miranda, ver classify.py LISTA_NEGRA_POR_ESTADO/
    # _REMAPEO_MUNICIPIO_A_ESTADO), pero solo una de las 4 fuentes del
    # evento fusionado ("Noticias de Aqui") nombra "municipio Chacao"
    # explicitamente -- las otras 3 solo dicen "Caracas"/"este de Caracas",
    # que aisladas resuelven a Distrito Capital (el mismo patron ambiguo
    # que origino el bug). El evento publicado es correcto porque se
    # fusiona con la fuente que si nombra Chacao.
    "incendio::Miranda::La Verdad (Zulia)": (
        "Solo dice 'este de Caracas', sin nombrar Chacao -- aislada resuelve "
        "a Distrito Capital. El evento fusionado es correcto porque otra "
        "fuente del mismo cluster (Noticias de Aqui) si nombra 'municipio "
        "Chacao' explicitamente."
    ),
    "incendio::Miranda::La Prensa de Monagas": (
        "Mismo caso que 'incendio::Miranda::La Verdad (Zulia)': no nombra "
        "Chacao, aislada resuelve a Distrito Capital."
    ),
    "incendio::Miranda::Reporte Confidencial (Nueva Esparta)": (
        "Mismo caso que 'incendio::Miranda::La Verdad (Zulia)': no nombra "
        "Chacao, aislada resuelve a Distrito Capital."
    ),
    # Caso real (18-08-2026): se agrego un filtro decisivo en classify.py
    # (_es_sismo_extranjero_con_epicentro_conocido_sin_municipio) para
    # descartar alertas de sismo en estados venezolanos sin evidencia local
    # cuando el texto solo describe el terremoto de magnitud 7.4 con
    # epicentro en San Jose del Palmar, Choco, Colombia (10-08-2026) -- ver
    # docs/roadmap_evolucion.md, auditoria 18-08-2026. Este filtro exige la
    # AUSENCIA de municipio detectado para no afectar el caso real y ya
    # publicado de Zulia (donde SI hay evidencia local: "sacude el Zulia",
    # municipio Maracaibo). El texto ALMACENADO de esta fuente aislada
    # ("La Verdad (Zulia)") esta truncado ("...en el departamento de Choco,
    # […]") y nunca llega a mencionar "Maracaibo" -- ese municipio solo lo
    # aporta la SEGUNDA fuente del mismo evento fusionado ("El Periodico de
    # Monagas": "percibido... en Maracaibo, estado Zulia, Venezuela"), que
    # SI pasa esta prueba de forma aislada. El evento publicado sigue siendo
    # correcto porque se fusiona con esa segunda fuente.
    "sismo::Zulia::La Verdad (Zulia)": (
        "Texto almacenado truncado ('[…]'), nunca menciona Maracaibo -- "
        "aislada, sin municipio detectado, la cae el nuevo filtro decisivo "
        "de epicentro extranjero conocido. El evento fusionado es correcto "
        "porque la segunda fuente del cluster (El Periodico de Monagas) SI "
        "nombra 'Maracaibo, estado Zulia' explicitamente."
    ),
}


def _con_marca_de_limitacion_conocida(caso):
    razon = _LIMITACIONES_CONOCIDAS.get(caso["id"])
    if razon is None:
        return pytest.param(caso, id=caso["id"])
    return pytest.param(caso, id=caso["id"], marks=pytest.mark.xfail(reason=razon, strict=False))


def _cargar_casos_historico():
    if not HISTORICO_PATH.exists():
        return []
    casos = []
    with open(HISTORICO_PATH, encoding="utf-8") as f:
        for linea in f:
            linea = linea.strip()
            if not linea:
                continue
            evento = json.loads(linea)
            for fuente in evento.get("fuentes", []):
                if not fuente.get("texto"):
                    continue
                casos.append(
                    {
                        "id": f"{evento['tipo']}::{evento['ubicacion']}::{fuente['nombre']}",
                        "tipo": evento["tipo"],
                        "ubicacion": evento["ubicacion"],
                        "texto": fuente["texto"],
                    }
                )
    return casos


CASOS = _cargar_casos_historico()


@pytest.mark.skipif(not CASOS, reason="data/historico_fuentes_texto.jsonl vacio o ausente")
@pytest.mark.parametrize("caso", [_con_marca_de_limitacion_conocida(c) for c in CASOS])
def test_fuente_historica_mantiene_tipo_y_ubicacion(caso):
    resultado = clasificar_item({"texto": caso["texto"]})
    por_ubicacion = {item.get("ubicacion"): item for item in resultado}
    assert caso["ubicacion"] in por_ubicacion, (
        f"{caso['id']}: '{caso['ubicacion']}' ya no se detecta como ubicacion "
        f"(ubicaciones detectadas ahora: {list(por_ubicacion)}). "
        "Si este cambio es intencional (un fix legitimo retracta esta fuente), "
        "usa scripts/validar_configs.py + revision manual antes de aceptarlo, "
        "no ignores esta falla sin mirarla."
    )
    tipos = por_ubicacion[caso["ubicacion"]].get("tipos", [])
    assert caso["tipo"] in tipos, (
        f"{caso['id']}: se esperaba '{caso['tipo']}' entre los tipos detectados "
        f"para '{caso['ubicacion']}', tipos actuales={tipos}"
    )
