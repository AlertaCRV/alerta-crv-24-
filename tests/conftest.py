import pathlib
import sys

# scripts/ no es un paquete instalable (no tiene __init__.py ni setup.py) --
# se agrega directamente al path de import, igual que ya hacían las
# validaciones manuales de cada sesión de auditoría.
RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "scripts"))
