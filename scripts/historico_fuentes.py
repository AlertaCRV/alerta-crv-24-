import json
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HISTORICO_FUENTES_PATH = os.path.join(BASE_DIR, "data", "historico_fuentes_texto.jsonl")


def registrar_texto_fuentes(eventos_nuevos):
    """Guarda el texto completo de cada fuente de cada evento publicado, en un
    archivo aparte de data/historico_eventos.jsonl -- ese otro archivo lo lee
    build_dashboard.py en cada corrida y debe seguir liviano; el texto
    completo (mucho mas pesado, y con contenido de terceros) solo lo
    necesita build_informes.py al generar los informes narrativos.

    MUTA cada evento en eventos_nuevos, eliminandole la clave
    "_texto_fuentes_completo": debe llamarse ANTES de redactar_noticia()/
    actualizar_datos_sitio(), para que ese texto completo nunca llegue al
    JSON publico del sitio."""
    if not eventos_nuevos:
        return
    os.makedirs(os.path.dirname(HISTORICO_FUENTES_PATH), exist_ok=True)
    with open(HISTORICO_FUENTES_PATH, "a", encoding="utf-8") as f:
        for evento in eventos_nuevos:
            fuentes_texto = evento.pop("_texto_fuentes_completo", [])
            registro = {
                "tipo": evento["tipo"],
                "ubicacion": evento["ubicacion"],
                "severidad": evento["severidad"],
                "confirmado": evento["confirmado"],
                "fecha_evento": evento["fecha_evento"],
                "fecha_deteccion": evento["fecha_deteccion"],
                "fuentes": fuentes_texto,
            }
            f.write(json.dumps(registro, ensure_ascii=False) + "\n")


def leer_texto_fuentes():
    if not os.path.exists(HISTORICO_FUENTES_PATH):
        return []
    registros = []
    with open(HISTORICO_FUENTES_PATH, "r", encoding="utf-8") as f:
        for linea in f:
            linea = linea.strip()
            if linea:
                registros.append(json.loads(linea))
    return registros
