import json
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HISTORICO_PATH = os.path.join(BASE_DIR, "data", "historico_eventos.jsonl")

CAMPOS_HISTORICO = [
    "tipo",
    "ubicacion",
    "municipio",
    "parroquia",
    "severidad",
    "confirmado",
    "num_fuentes",
    "score",
    "fecha_evento",
    "fecha_deteccion",
]


def registrar_historico(eventos_nuevos):
    """Agrega al registro histórico de solo-append una línea por cada evento
    publicado en esta corrida. A diferencia de data/publicados.json (caché de
    deduplicación con retención de 3 días), este archivo no se purga: es la
    base para la analítica histórica del panel público."""
    if not eventos_nuevos:
        return
    os.makedirs(os.path.dirname(HISTORICO_PATH), exist_ok=True)
    with open(HISTORICO_PATH, "a", encoding="utf-8") as f:
        for evento in eventos_nuevos:
            registro = {campo: evento.get(campo) for campo in CAMPOS_HISTORICO}
            f.write(json.dumps(registro, ensure_ascii=False) + "\n")


def leer_historico():
    if not os.path.exists(HISTORICO_PATH):
        return []
    registros = []
    with open(HISTORICO_PATH, "r", encoding="utf-8") as f:
        for linea in f:
            linea = linea.strip()
            if linea:
                registros.append(json.loads(linea))
    return registros
