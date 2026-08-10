import json
import os
from datetime import datetime, timedelta, timezone
from dateutil import parser as dateparser

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ESTADO_PATH = os.path.join(BASE_DIR, "data", "publicados.json")
DIAS_RETENCION = 3

# Ventana usada para tratar dos reportes del mismo tipo+ubicacion, pero de
# fuentes/dias distintos, como el mismo evento en vez de uno nuevo -- ej. dos
# medios que cubren la misma inundacion con 6+ horas de diferencia y que,
# por caer en corridas distintas, nunca se agrupan juntos en verify.py.
# Excluye sismo (tiene su propio mecanismo de correlacion cruzada, ver
# _mismo_sismo_ya_publicado) y orden_publico (durante disturbios, el mismo
# tipo+ubicacion puede repetirse genuinamente dia a dia, y agruparlos
# ocultaria eventos reales distintos).
VENTANA_HORAS_MISMO_EVENTO = 36
TIPOS_SIN_VENTANA_MISMO_EVENTO = {"sismo", "orden_publico"}

# incendio tambien quedaba excluido de la ventana hasta el 31-07-2026: un
# estado populoso como Distrito Capital puede tener varios incendios
# genuinamente distintos en menos de 36h (caso real, 30-07-2026: una
# explosion de gas en la avenida Nueva Granada reutilizo por error su clave
# para un incendio COMPLETAMENTE DISTINTO al dia siguiente -- una libreria
# del CCCT -- solo por compartir tipo+ubicacion). Pero excluirlo por
# completo genero el problema opuesto: dos articulos de seguimiento sobre
# el MISMO incendio (mismo centro comercial, un dia despues) nunca se
# fusionaban y quedaban como alertas duplicadas -- caso real (31-07-2026):
# el incendio del centro comercial Los Cedros en Porlamar (Nueva Esparta) y
# el incendio del CCCT (originalmente mal ubicado en Distrito Capital, ver
# classify.py) se publicaron dos veces cada uno. Para incendio
# especificamente, la ventana SI aplica pero exige ademas que el municipio
# coincida (ver _resolver_clave) -- evita el falso positivo original (la
# explosion de gas tenia municipio Libertador, el CCCT no tenia municipio
# detectado todavia) sin reintroducir el problema de las alertas
# duplicadas (dos reportes del mismo incendio casi siempre nombran, entre
# ambos, el mismo municipio).
TIPOS_CON_VENTANA_EXIGE_MISMO_MUNICIPIO = {"incendio"}


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
    sobre un sismo ocurrido en la manana y sigue siendo el mismo evento.

    Tambien cubre el MISMO estado: `_clave_evento()` agrega la magnitud a la
    clave de sismo precisamente para distinguir dos sismos genuinamente
    distintos el mismo dia en el mismo estado -- pero un sismo real suele
    reportarse primero con una magnitud preliminar y despues con la
    definitiva (revisada por el organismo sismologico), lo que hace que la
    clave cambie aunque sea el mismo evento. Caso real (10-08-2026): el
    mismo sismo de Colombia sentido en Zulia se publico primero como
    `sismo::Zulia::2026-08-10::mag7.4` (14:34 UTC, magnitud ya revisada por
    el Servicio Geologico Colombiano) y, mas de 3 horas despues, otra fuente
    lo reporto de nuevo como `sismo::Zulia::2026-08-10::mag6.6` (17:40 UTC,
    usando la magnitud preliminar aun no actualizada) -- mismo sismo, mismo
    estado, mismo dia, tratado como una alerta nueva solo por la magnitud
    distinta en la clave. Como `sismo` esta excluido de la ventana de
    "mismo evento" de `_resolver_clave()` (ver TIPOS_SIN_VENTANA_MISMO_EVENTO),
    ese mecanismo tampoco lo detecta -- se necesita este chequeo explicito."""
    if evento["tipo"] != "sismo":
        return False
    for clave, previo in publicados.items():
        partes = clave.split("::")
        if len(partes) < 3 or partes[0] != "sismo" or partes[2] != fecha_dia:
            continue
        otra_ubicacion = partes[1]
        if otra_ubicacion == evento["ubicacion"]:
            return True
        if evento.get("magnitud") is not None and len(partes) >= 4 and partes[3] == f"mag{evento['magnitud']}":
            return True
        if otra_ubicacion in evento.get("tambien_mencionado_en", []):
            return True
    return False


def _resolver_clave(evento, publicados):
    """Devuelve la clave bajo la que este evento debe registrarse: si hay un
    evento ya publicado del mismo tipo+ubicacion dentro de
    VENTANA_HORAS_MISMO_EVENTO (comparando la fuente mas temprana de cada
    uno), se reutiliza esa clave existente -- se trata como el mismo
    evento, no uno nuevo, aunque nunca se hayan agrupado juntos en la misma
    corrida. Sismo y orden_publico quedan fuera de esta logica (ver
    TIPOS_SIN_VENTANA_MISMO_EVENTO) y usan siempre la clave por dia exacto.
    Incendio (ver TIPOS_CON_VENTANA_EXIGE_MISMO_MUNICIPIO) exige ademas que
    el municipio coincida en ambos lados -- si cualquiera de los dos no
    tiene municipio detectado, no se reutiliza la clave (mismo criterio
    conservador que evito el falso positivo original de este mecanismo)."""
    if evento["tipo"] not in TIPOS_SIN_VENTANA_MISMO_EVENTO:
        fecha_nueva = dateparser.isoparse(evento.get("fecha_evento_temprana", evento["fecha_evento"]))
        limite = timedelta(hours=VENTANA_HORAS_MISMO_EVENTO)
        exige_municipio = evento["tipo"] in TIPOS_CON_VENTANA_EXIGE_MISMO_MUNICIPIO
        for clave, previo in publicados.items():
            partes = clave.split("::")
            if len(partes) < 3 or partes[0] != evento["tipo"] or partes[1] != evento["ubicacion"]:
                continue
            if exige_municipio and (
                not evento.get("municipio")
                or not previo.get("municipio")
                or evento["municipio"] != previo["municipio"]
            ):
                continue
            fecha_previa_str = previo.get("fecha_evento_temprana")
            if fecha_previa_str:
                fecha_previa = dateparser.isoparse(fecha_previa_str)
            else:
                # Entradas guardadas antes de que se empezara a registrar
                # fecha_evento_temprana (27-07-2026) no tienen ese campo --
                # sin este fallback, un evento real ya publicado antes de esa
                # fecha nunca se reconoce como "el mismo evento" en corridas
                # posteriores (por mas que este dentro de la ventana), y
                # termina republicado como una alerta duplicada. Se usa el
                # mediodia del dia codificado en la propia clave como fecha
                # aproximada (en vez de medianoche) para no perder hasta 12h
                # de margen real de la ventana de 36h por el solo hecho de
                # anclar al comienzo del dia.
                try:
                    fecha_previa = dateparser.isoparse(partes[2]).replace(
                        hour=12, tzinfo=timezone.utc
                    )
                except (ValueError, IndexError):
                    continue
            if abs(fecha_nueva - fecha_previa) <= limite:
                return clave
    return _clave_evento(evento)


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


def _entrada_publicados(evento):
    return {
        "severidad": evento["severidad"],
        "confirmado": evento["confirmado"],
        "fecha_deteccion": evento["fecha_deteccion"],
        "fecha_evento_temprana": evento.get("fecha_evento_temprana", evento["fecha_evento"]),
        "municipio": evento.get("municipio"),
    }


def filtrar_nuevos(eventos, publicados):
    """Evita republicar el mismo evento (tipo+ubicacion+dia, o tipo+ubicacion
    dentro de VENTANA_HORAS_MISMO_EVENTO para tipos que no sean sismo/
    orden_publico) repetidamente en cada corrida, salvo que haya subido de
    severidad o cambiado su estado de confirmación.

    Para tipo=sismo se filtra ademas por _mismo_sismo_ya_publicado: un mismo
    sismo reportado el mismo dia bajo otra ubicacion (misma magnitud, o
    mencion cruzada explicita de estados) no genera una alerta duplicada.

    Caso real (10-08-2026): un sismo de magnitud 7.4 con epicentro en
    Colombia, sentido en 4 estados venezolanos distintos, se publico como 4
    alertas separadas (Distrito Capital, Tachira, Zulia, Miranda) en una
    misma corrida -- _mismo_sismo_ya_publicado() solo comparaba cada evento
    contra `publicados` (el estado YA persistido de corridas anteriores),
    nunca contra los otros eventos del mismo sismo detectados en la MISMA
    corrida, porque este bucle nunca escribia en `publicados` hasta
    terminar (esa escritura ocurria despues, en marcar_publicados(),
    llamada por separado desde main.py). Ahora cada evento aceptado se
    registra en `publicados` de inmediato -- el segundo/tercer estado del
    mismo sismo, procesado a continuacion dentro del mismo bucle, ya lo
    encuentra y se descarta como duplicado."""
    nuevos = []
    for evento in eventos:
        fecha_dia = _fecha_dia_dedup(evento)
        if _mismo_sismo_ya_publicado(evento, publicados, fecha_dia):
            continue
        clave = _resolver_clave(evento, publicados)
        previo = publicados.get(clave)
        if previo is None:
            evento["clave_dedup"] = clave
            nuevos.append(evento)
            publicados[clave] = _entrada_publicados(evento)
        elif previo["severidad"] != evento["severidad"] or previo["confirmado"] != evento["confirmado"]:
            # Es una actualizacion del mismo evento (p.ej. subio de severidad),
            # no uno nuevo -- se marca con la misma clave para que
            # actualizar_datos_sitio() reemplace la entrada anterior en vez de
            # agregar una segunda entrada duplicada para el mismo hecho real.
            evento["clave_dedup"] = clave
            nuevos.append(evento)
            publicados[clave] = _entrada_publicados(evento)
    return nuevos


def marcar_publicados(eventos, publicados):
    for evento in eventos:
        clave = _resolver_clave(evento, publicados)
        publicados[clave] = _entrada_publicados(evento)
    return publicados
