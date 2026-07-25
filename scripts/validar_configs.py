"""Valida que los archivos de configuracion y estado del repo tengan
sintaxis correcta (YAML/JSON) y que los scripts compilen, para atrapar
en CI errores como los que rompieron el monitoreo en produccion:
data/publicados.json corrupto y una indentacion invalida en
config/keywords.yaml. Se ejecuta en cada push/PR (ver
.github/workflows/validar.yml)."""

import compileall
import json
import sys
from pathlib import Path

import yaml

RAIZ = Path(__file__).resolve().parent.parent

ARCHIVOS_YAML = [
    "config/settings.yaml",
    "config/estados.yaml",
    "config/keywords.yaml",
    "config/sources.yaml",
]

ARCHIVOS_JSON = [
    "config/ubicaciones_detalle.json",
    "data/publicados.json",
    "docs/data/noticias.json",
]


def _buscar_listas(nodo):
    """Recorre un YAML ya parseado y devuelve todas las listas de strings
    encontradas (las hojas tipo lista de palabras clave)."""
    if isinstance(nodo, list):
        yield nodo
    elif isinstance(nodo, dict):
        for v in nodo.values():
            yield from _buscar_listas(v)


def _validar_keywords_sin_fusion(ruta, errores):
    """Chequeo semantico especifico: un YAML con indentacion irregular puede
    seguir siendo sintacticamente valido pero fusionar dos items de lista en
    un solo string (el bug real que rompio 'emergencia nacional' +
    'emergencia regional' en una sola entrada). Ninguna palabra clave
    legitima de este archivo contiene ' - ' en medio, asi que ese patron es
    una senal fuerte de fusion accidental."""
    try:
        datos = yaml.safe_load(ruta.read_text(encoding="utf-8"))
    except yaml.YAMLError:
        return  # ya se reporta como error de sintaxis en validar_yaml
    for lista in _buscar_listas(datos):
        for item in lista:
            if isinstance(item, str) and " - " in item:
                errores.append(
                    f"{ruta.name}: posible fusion de dos entradas por "
                    f"indentacion irregular -- '{item}'"
                )


def validar_yaml(errores):
    for rel in ARCHIVOS_YAML:
        ruta = RAIZ / rel
        if not ruta.exists():
            errores.append(f"{rel}: archivo no encontrado")
            continue
        try:
            yaml.safe_load(ruta.read_text(encoding="utf-8"))
        except yaml.YAMLError as e:
            errores.append(f"{rel}: YAML invalido -- {e}")

    ruta_keywords = RAIZ / "config/keywords.yaml"
    if ruta_keywords.exists():
        _validar_keywords_sin_fusion(ruta_keywords, errores)


def validar_json(errores):
    for rel in ARCHIVOS_JSON:
        ruta = RAIZ / rel
        if not ruta.exists():
            errores.append(f"{rel}: archivo no encontrado")
            continue
        contenido = ruta.read_text(encoding="utf-8")
        if not contenido.strip():
            errores.append(f"{rel}: archivo vacio (se esperaba al menos '{{}}' o '[]')")
            continue
        try:
            json.loads(contenido)
        except json.JSONDecodeError as e:
            errores.append(f"{rel}: JSON invalido -- {e}")


def validar_scripts(errores):
    ok = compileall.compile_dir(str(RAIZ / "scripts"), quiet=1, force=True)
    if not ok:
        errores.append("scripts/: uno o mas archivos .py no compilan (ver salida arriba)")


def main():
    errores = []
    validar_yaml(errores)
    validar_json(errores)
    validar_scripts(errores)

    if errores:
        print("Validacion de configuracion FALLIDA:\n")
        for e in errores:
            print(f"  - {e}")
        sys.exit(1)

    print("Validacion de configuracion OK: YAML, JSON y scripts sin errores de sintaxis.")


if __name__ == "__main__":
    main()
