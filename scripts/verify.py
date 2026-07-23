from datetime import datetime, timezone
from dateutil import parser as dateparser

from config_loader import load_settings


def _clave_cluster(item):
    tipo_principal = item["tipos"][0]
    return (tipo_principal, item["ubicacion"])


def agrupar_y_verificar(items):
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
            nombre = m["fuente_nombre"]
            if nombre not in fuentes_unicas or m["peso"] > fuentes_unicas[nombre]["peso"]:
                fuentes_unicas[nombre] = m

        score = sum(f["peso"] for f in fuentes_unicas.values())
        severidades = [m["severidad"] for m in miembros if m["severidad"] != "sin_clasificar"]
        orden_severidad = ["critico", "alto", "medio", "bajo"]
        severidad_final = next((s for s in orden_severidad if s in severidades), "sin_clasificar")

        fecha_mas_reciente = max(miembros, key=lambda m: dateparser.isoparse(m["fecha"]))["fecha"]

        municipio = next((m.get("municipio") for m in miembros if m.get("municipio")), None)
        parroquia = next((m.get("parroquia") for m in miembros if m.get("parroquia")), None)
        texto_muestra = max(miembros, key=lambda m: m["peso"])["texto"]

        eventos.append({
            "tipo": tipo,
            "ubicacion": ubicacion,
            "municipio": municipio,
            "parroquia": parroquia,
            "texto_muestra": texto_muestra,
            "severidad": severidad_final,
            "score": round(score, 2),
            "confirmado": score >= umbral,
            "num_fuentes": len(fuentes_unicas),
            "fuentes": [
                {"nombre": f["fuente_nombre"], "link": f["link"], "fecha": f["fecha"]}
                for f in fuentes_unicas.values()
            ],
            "fecha_evento": fecha_mas_reciente,
            "fecha_deteccion": datetime.now(timezone.utc).isoformat(),
        })

    return eventos
