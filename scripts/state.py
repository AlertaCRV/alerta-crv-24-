import json
import os
from datetime import datetime, timedelta, timezone
from dateutil import parser as dateparser

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ESTADO_PATH = os.path.join(BASE_DIR, "data", "publicados.json")
DIAS_RETENCION = 3


def _clave_evento(evento):
    fecha_dia = dateparser.isoparse(evento["fecha_evento"]).date().isoformat()
    return f"{evento['tipo']}::{evento['ubicacion']}::{fecha_dia}"


def cargar_publicados():
    if not os.path.exists(ESTADO_PATH):
        return {}
    with open(ESTADO_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def guardar_publicados(publicados):
    os.makedirs(os.path.dirname(ESTADO_PATH), exist_ok=True)
    limite = datetime.now(timezone.utc) - timedelta(days=DIAS_RETENCION)
    limpio = {
        k: v for k, v in publicados.items()
        if datetime.fromisoformat(v["fecha_deteccion"]) > limite
    }
    with open(ESTADO_PATH, "w", encoding="utf-8") as f:
        json.dump(limpio, f, ensure_ascii=False, indent=2)


def filtrar_nuevos(eventos, publicados):
    """Evita republicar el mismo evento (tipo+ubicacion+dia) repetidamente en cada corrida,
    salvo que haya subido de severidad o cambiado su estado de confirmación. Un mismo
    tipo+ubicacion en un dia distinto se trata como un evento nuevo."""
    nuevos = []
    for evento in eventos:
        clave = _clave_evento(evento)
        previo = publicados.get(clave)
        if previo is None:
            nuevos.append(evento)
        elif previo["severidad"] != evento["severidad"] or previo["confirmado"] != evento["confirmado"]:
            nuevos.append(evento)
    return nuevos


def marcar_publicados(eventos, publicados):
    for evento in eventos:
        clave = _clave_evento(evento)
        publicados[clave] = {
            "severidad": evento["severidad"],
            "confirmado": evento["confirmado"],
            "fecha_deteccion": evento["fecha_deteccion"],
        }
    return publicados
