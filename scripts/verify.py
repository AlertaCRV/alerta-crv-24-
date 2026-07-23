from datetime import datetime
from dateutil import parser as dateparser

from config_loader import load_settings


def _clave_cluster(item):
    tipo_principal = item["tipos"][0]
    return (tipo_principal, item["ubicacion"])


def agrupar_y_verificar(items):
    """Agrupa items por (tipo, ubicacion) dentro de una ventana de tiempo y calcula
    un score de confianza sumando los pesos de las fuentes involucradas.
    Devuelve una lista de 'eventos' listos para redactar."""
    settings = load_settings()["verificacion"]
    umbral = settings["umbral_confirmado"]

    clusters = {}
    for item in items:
        clave = _clave_cluster(item)
        clusters.setdefault(clave, []).append(item)

    eventos = []
    for (tipo, ubicacion), miembros in clusters.items():
        fuentes_unicas = {}
        for m in miembros:
            # una fuente solo cuenta una vez por evento, se queda con el peso más alto reportado
            nombre = m["fuente_nombre"]
            if nombre not in fuentes_unicas or m["peso"] > fuentes_unicas[nombre]["peso"]:
                fuentes_unicas[nombre] = m

        score = sum(f["peso"] for f in fuentes_unicas.values())
        severidades = [m["severidad"] for m in miembros if m["severidad"] != "sin_clasificar"]
        orden_severidad = ["critico", "alto", "medio", "bajo"]
        severidad_final = next((s for s in orden_severidad if s in severidades), "sin_clasificar")

        fecha_mas_reciente = max(miembros, key=lambda m: dateparser.isoparse(m["fecha"]))["fecha"]

        eventos.append({
            "tipo": tipo,
            "ubicacion": ubicacion,
            "severidad": severidad_final,
            "score": round(score, 2),
            "confirmado": score >= umbral,
            "num_fuentes": len(fuentes_unicas),
            "fuentes": [
                {"nombre": f["fuente_nombre"], "link": f["link"], "fecha": f["fecha"]}
                for f in fuentes_unicas.values()
            ],
            "fecha_evento": fecha_mas_reciente,
            "fecha_deteccion": datetime.utcnow().isoformat(),
        })

    return eventos
