import json
import os
from collections import Counter, defaultdict
from datetime import datetime, timezone

from dateutil import parser as dateparser

from historico import leer_historico

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DASHBOARD_PATH = os.path.join(BASE_DIR, "docs", "data", "estadisticas.json")


def _mes(fecha_iso):
    dt = dateparser.isoparse(fecha_iso)
    return f"{dt.year:04d}-{dt.month:02d}"


def calcular_estadisticas(registros):
    """V1 del dashboard (acordada el 26/07/2026): conteo por tipo, ranking de
    estados (total vs. confirmadas), cruce estado x tipo, y distribución de
    severidad. Deja fuera latencia de detección, confirmado-vs-tiempo, rachas
    y duración de fallas -- diferidos hasta validar con uso real."""
    por_tipo = Counter()
    por_estado_total = Counter()
    por_estado_confirmado = Counter()
    cruce_estado_tipo = defaultdict(Counter)
    por_severidad = Counter()
    serie_mensual_por_tipo = defaultdict(Counter)

    for r in registros:
        tipo = r.get("tipo") or "sin_clasificar"
        estado = r.get("ubicacion") or "sin_ubicacion"
        severidad = r.get("severidad") or "sin_clasificar"

        por_tipo[tipo] += 1
        por_estado_total[estado] += 1
        if r.get("confirmado"):
            por_estado_confirmado[estado] += 1
        cruce_estado_tipo[estado][tipo] += 1
        por_severidad[severidad] += 1

        fecha_evento = r.get("fecha_evento")
        if fecha_evento:
            serie_mensual_por_tipo[tipo][_mes(fecha_evento)] += 1

    fechas_evento = [r["fecha_evento"] for r in registros if r.get("fecha_evento")]
    periodo_cubierto = {
        "desde": min(fechas_evento) if fechas_evento else None,
        "hasta": max(fechas_evento) if fechas_evento else None,
    }

    return {
        # Todo indicador de este panel es un acumulado historico -- nunca se
        # muestra sin decir a que periodo corresponde, para no dar la falsa
        # impresion de un dato "actual" cuando en realidad puede cubrir
        # meses o anos.
        "actualizado": datetime.now(timezone.utc).isoformat(),
        "periodo_cubierto": periodo_cubierto,
        "total_eventos": len(registros),
        "por_tipo": dict(por_tipo),
        "ranking_estados": [
            {
                "estado": estado,
                "total": total,
                "confirmados": por_estado_confirmado.get(estado, 0),
            }
            for estado, total in por_estado_total.most_common()
        ],
        "cruce_estado_tipo": {
            estado: dict(tipos) for estado, tipos in cruce_estado_tipo.items()
        },
        "por_severidad": dict(por_severidad),
        "serie_mensual_por_tipo": {
            tipo: dict(meses) for tipo, meses in serie_mensual_por_tipo.items()
        },
    }


def actualizar_dashboard():
    registros = leer_historico()
    estadisticas = calcular_estadisticas(registros)
    os.makedirs(os.path.dirname(DASHBOARD_PATH), exist_ok=True)
    with open(DASHBOARD_PATH, "w", encoding="utf-8") as f:
        json.dump(estadisticas, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    actualizar_dashboard()
