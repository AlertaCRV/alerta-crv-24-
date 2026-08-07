"""Suite de regresion para classify.py sobre casos reales o de control ya
documentados en docs/roadmap_evolucion.md.

Cada caso vive en casos_clasificacion.jsonl (JSON Lines, uno por linea,
append-only: nunca se reescribe una linea existente, solo se agregan
nuevas al final -- mismo espiritu que el roadmap). Ver
docs/plan_confiabilidad_clasificacion.md para el formato completo y como
agregar un caso nuevo.
"""

import json
import pathlib

import pytest

from classify import clasificar_item, es_relevante

CASOS_PATH = pathlib.Path(__file__).parent / "casos_clasificacion.jsonl"

# Casos cuyo "esperado" original quedo superado por un fix POSTERIOR y mas
# general (no se reescribe la linea original en casos_clasificacion.jsonl --
# es append-only, ver docstring del modulo -- se marca xfail aqui, mismo
# mecanismo que test_classify_regresion_historico.py). El comportamiento
# correcto vigente se cubre con un caso nuevo agregado al final del archivo.
_CASOS_SUPERADOS_POR_FIX_POSTERIOR = {
    "salud_publica_donaciones_preventivas_caraballeda_2026-07-29": (
        "Auditoria diaria automatica (07-08-2026): _ventana_cerca() dejo de "
        "emparejar solo la PRIMERA PALABRA de un nombre de estado multi-"
        "palabra (bug que causaba, en otro caso real, una alerta falsa en "
        "'La Guaira' anclada a un 'la' cualquiera del texto). Con el fix, la "
        "posicion real de 'La Guaira' en este texto (la primera palabra del "
        "articulo) ya no encuentra 'enfermedades' dentro de la ventana de "
        "proximidad (75 palabras de distancia) -- antes coincidia por "
        "casualidad con OTRO 'la' (de 'mantener la higiene'), a solo 4 "
        "palabras de 'enfermedades'. El resultado practico no cambia (el "
        "evento sigue sin ser relevante, ver el caso de reemplazo agregado "
        "al final de este archivo con el mismo texto)."
    ),
}


def _con_marca_de_limitacion_conocida(caso):
    razon = _CASOS_SUPERADOS_POR_FIX_POSTERIOR.get(caso["id"])
    if razon is None:
        return pytest.param(caso, id=caso["id"])
    return pytest.param(caso, id=caso["id"], marks=pytest.mark.xfail(reason=razon, strict=False))


def _cargar_casos():
    casos = []
    with open(CASOS_PATH, encoding="utf-8") as f:
        for numero_linea, linea in enumerate(f, start=1):
            linea = linea.strip()
            if not linea:
                continue
            try:
                caso = json.loads(linea)
            except json.JSONDecodeError as e:
                raise ValueError(f"{CASOS_PATH}:{numero_linea}: JSON invalido -- {e}") from e
            for campo in ("id", "descripcion", "texto", "esperado"):
                assert campo in caso, f"{CASOS_PATH}:{numero_linea}: falta el campo '{campo}'"
            casos.append(caso)
    ids = [c["id"] for c in casos]
    duplicados = {i for i in ids if ids.count(i) > 1}
    assert not duplicados, f"ids duplicados en {CASOS_PATH}: {duplicados}"
    return casos


CASOS = _cargar_casos()


@pytest.mark.parametrize("caso", [_con_marca_de_limitacion_conocida(c) for c in CASOS])
def test_caso_clasificacion(caso):
    resultado = clasificar_item({"texto": caso["texto"]})
    por_ubicacion = {item.get("ubicacion"): item for item in resultado}

    for ubicacion_prohibida in caso.get("no_debe_aparecer_ubicacion", []):
        assert ubicacion_prohibida not in por_ubicacion, (
            f"{caso['id']}: se esperaba que '{ubicacion_prohibida}' NO apareciera "
            f"como ubicacion detectada, pero aparecio con tipos={por_ubicacion[ubicacion_prohibida].get('tipos')}"
        )

    for esperado in caso["esperado"]:
        ubicacion = esperado.get("ubicacion")
        assert ubicacion in por_ubicacion, (
            f"{caso['id']}: se esperaba la ubicacion '{ubicacion}' en el resultado, "
            f"pero no aparecio (ubicaciones detectadas: {list(por_ubicacion)})"
        )
        item = por_ubicacion[ubicacion]
        for campo, valor_esperado in esperado.items():
            if campo == "ubicacion":
                continue
            if campo == "relevante":
                assert es_relevante(item) == valor_esperado, (
                    f"{caso['id']}: es_relevante() = {es_relevante(item)}, se esperaba {valor_esperado}"
                )
            elif campo == "tipos_incluye":
                assert valor_esperado in item.get("tipos", []), (
                    f"{caso['id']}: se esperaba '{valor_esperado}' entre los tipos detectados, "
                    f"tipos={item.get('tipos')}"
                )
            else:
                assert item.get(campo) == valor_esperado, (
                    f"{caso['id']}: campo '{campo}' = {item.get(campo)!r}, se esperaba {valor_esperado!r}"
                )
