import json
import os
from datetime import datetime, timedelta, timezone
from dateutil import parser as dateparser

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ESTADO_PATH = os.path.join(BASE_DIR, "data", "publicados.json")
DIAS_RETENCION = 3


def _fecha_dia_dedup(evento):
    """El dia calendario usado para la clave de deduplicacion se ancla a la
    fuente MAS TEMPRANA del evento (fecha_evento_temprana), no a la mas
    reciente (fecha_evento) -- una cobertura continua de varios dias sobre
    el mismo hecho (ej. una via bloqueada por un deslizamiento) hace que
    fecha_evento avance con cada articulo de seguimiento, y si cruza la
    medianoche UTC el evento se trataba, por error, como uno nuevo."""
    fecha = evento.get("fecha_evento_temprana", evento["fecha_evento"])
    return dateparser.isoparse(fecha).date().isoformat()


def _clave_evento(evento):
    fecha_dia = _fecha_dia_dedup(evento)
    clave = f"{evento['tipo']}::{evento['ubicacion']}::{fecha_dia}"
    if evento["tipo"] == "sismo" and evento.get("magnitud") is not None:
        clave += f"::mag{evento['magnitud']}"
    return clave


def _mismo_sismo_ya_publicado(evento, publicados, fecha_dia):
    """Para tipo=sismo: True si este mismo sismo (por magnitud coincidente, o
    porque el texto menciona explicitamente otra ubicacion) ya fue publicado
    hoy bajo una ubicacion distinta -- para no repetir la alerta del mismo
    sismo sentido en varios estados. El alcance temporal es el dia
    calendario (no una ventana de horas): un medio puede publicar de noche
    sobre un sismo ocurrido en la manana y sigue siendo el mismo evento."""
    if evento["tipo"] != "sismo":
        return False
    for clave, previo in publicados.items():
        partes = clave.split("::")
        if len(partes) < 3 or partes[0] != "sismo" or partes[2] != fecha_dia:
            continue
        otra_ubicacion = partes[1]
        if otra_ubicacion == evento["ubicacion"]:
            continue
        if evento.get("magnitud") is not None and len(partes) >= 4 and partes[3] == f"mag{evento['magnitud']}":
            return True
        if otra_ubicacion in evento.get("tambien_mencionado_en", []):
            return True
    return False


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
    tipo+ubicacion en un dia distinto se trata como un evento nuevo.

    Para tipo=sismo se filtra ademas por _mismo_sismo_ya_publicado: un mismo
    sismo reportado el mismo dia bajo otra ubicacion (misma magnitud, o
    mencion cruzada explicita de estados) no genera una alerta duplicada."""
    nuevos = []
    for evento in eventos:
        fecha_dia = _fecha_dia_dedup(evento)
        if _mismo_sismo_ya_publicado(evento, publicados, fecha_dia):
            continue
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
