import email
import imaplib
import os
import re
from datetime import timezone
from email.header import decode_header
from email.utils import parseaddr, parsedate_to_datetime

IMAP_HOST = "imap.gmail.com"

# El reenvio automatico/manual de Outlook suele anteponer "FW:"/"Fwd:"/"RV:"
# al asunto original -- se quita solo por prolijidad (para que
# fuente_nombre/texto no arrastren el prefijo), no porque el clasificador lo
# necesite: detectar_ubicacion()/detectar_tipo() escanean todo el texto, no
# dependen de que el asunto empiece de una forma particular. Se quita en un
# bucle (no una sola vez) porque una cadena de varios reenvios puede acumular
# mas de un prefijo ("Fwd: RV: ...").
_PREFIJO_REENVIO_RE = re.compile(r"^\s*(fwd?|rv|re)\s*:\s*", re.IGNORECASE)


def _quitar_prefijos_reenvio(asunto):
    anterior = None
    while anterior != asunto:
        anterior = asunto
        asunto = _PREFIJO_REENVIO_RE.sub("", asunto).strip()
    return asunto


def _decodificar_header(valor):
    if not valor:
        return ""
    resultado = []
    for texto, codificacion in decode_header(valor):
        if isinstance(texto, bytes):
            resultado.append(texto.decode(codificacion or "utf-8", errors="replace"))
        else:
            resultado.append(texto)
    return "".join(resultado)


def _extraer_cuerpo(mensaje):
    """Prefiere texto plano; si el correo solo trae HTML, le quita las
    etiquetas (mismo criterio que fetch_rss.py con el resumen de RSS)."""
    if mensaje.is_multipart():
        texto_plano = None
        texto_html = None
        for parte in mensaje.walk():
            if parte.get_content_disposition() == "attachment":
                continue
            content_type = parte.get_content_type()
            payload = parte.get_payload(decode=True)
            if payload is None:
                continue
            charset = parte.get_content_charset() or "utf-8"
            texto = payload.decode(charset, errors="replace")
            if content_type == "text/plain" and texto_plano is None:
                texto_plano = texto
            elif content_type == "text/html" and texto_html is None:
                texto_html = texto
        if texto_plano:
            return texto_plano
        if texto_html:
            return re.sub(r"<[^>]+>", " ", texto_html)
        return ""

    payload = mensaje.get_payload(decode=True)
    if payload is None:
        return mensaje.get_payload() or ""
    charset = mensaje.get_content_charset() or "utf-8"
    texto = payload.decode(charset, errors="replace")
    if mensaje.get_content_type() == "text/html":
        texto = re.sub(r"<[^>]+>", " ", texto)
    return texto


def fetch_gmail_items(ventana_horas=12):
    """Lee los correos institucionales reenviados a la cuenta Gmail dedicada
    (ver docs/roadmap_evolucion.md, seccion sobre el reemplazo de la
    integracion con Outlook/Microsoft Graph, que requeria permisos de
    administrador del tenant institucional). `ventana_horas` se recibe por
    consistencia de firma con los demas fetch_*_items(), pero no filtra por
    fecha -- IMAP SEARCH SINCE solo tiene granularidad de dia, no de horas.
    En su lugar se leen los mensajes no vistos y se marcan como vistos al
    procesarlos, para nunca reprocesar el mismo correo dos veces.

    A diferencia de una version anterior de este fetcher (para Outlook), NO
    exige que el asunto siga un formato rigido tipo "EMERGENCIA | Estado |
    Tipo | Severidad" -- los reportes reales de las filiales llegan en
    lenguaje natural (ej. "Actualizacion de desplazados de La Guaira en los
    municipios Colina, Zamora y Tocopero"), nunca en ese formato. En su
    lugar, cada correo se entrega como un item de texto libre (asunto +
    cuerpo), igual que un item de fetch_rss_items() -- clasificar_item() en
    classify.py hace la deteccion de ubicacion/tipo/severidad a partir del
    texto, exactamente como ya hace con los articulos de RSS."""
    address = os.environ.get("GMAIL_ADDRESS")
    app_password = os.environ.get("GMAIL_APP_PASSWORD")
    if not address or not app_password:
        print(
            "[WARN] GMAIL_ADDRESS/GMAIL_APP_PASSWORD no configurados, se omite "
            "la recoleccion de correos institucionales"
        )
        return []

    try:
        conexion = imaplib.IMAP4_SSL(IMAP_HOST)
        conexion.login(address, app_password)
        conexion.select("INBOX")
    except Exception as e:
        print(f"[WARN] No se pudo conectar/autenticar con Gmail: {e}")
        return []

    items = []
    try:
        estado, datos = conexion.search(None, "UNSEEN")
        if estado != "OK":
            print(f"[WARN] Error buscando correos no leidos: {estado}")
            return []

        for num in datos[0].split():
            try:
                estado, msg_datos = conexion.fetch(num, "(RFC822)")
                if estado != "OK" or not msg_datos or not msg_datos[0]:
                    continue
                mensaje = email.message_from_bytes(msg_datos[0][1])

                asunto = _quitar_prefijos_reenvio(_decodificar_header(mensaje.get("Subject", "")))
                _, remitente_email = parseaddr(_decodificar_header(mensaje.get("From", "")))
                message_id = (mensaje.get("Message-ID") or "").strip("<>")

                try:
                    fecha = parsedate_to_datetime(mensaje.get("Date"))
                    if fecha.tzinfo is None:
                        fecha = fecha.replace(tzinfo=timezone.utc)
                except Exception:
                    fecha = None

                cuerpo = _extraer_cuerpo(mensaje)
                texto = f"{asunto}. {cuerpo}".strip()
                if texto and fecha:
                    items.append({
                        "fuente_nombre": f"Reporte institucional ({remitente_email or 'desconocido'})",
                        "fuente_tipo": "correo",
                        "peso": 1.5,
                        "texto": texto,
                        "link": (
                            f"https://mail.google.com/mail/u/0/#search/rfc822msgid:{message_id}"
                            if message_id else ""
                        ),
                        "fecha": fecha.isoformat(),
                    })
            except Exception as e:
                print(f"[WARN] No se pudo procesar un correo: {e}")
            finally:
                # Se marca como leido siempre, tenga o no texto/fecha
                # utilizable -- de lo contrario un correo problematico
                # quedaria como no leido para siempre y se reprocesaria (sin
                # efecto) en cada corrida.
                try:
                    conexion.store(num, "+FLAGS", "\\Seen")
                except Exception:
                    pass
    finally:
        try:
            conexion.close()
            conexion.logout()
        except Exception:
            pass

    return items


if __name__ == "__main__":
    for i in fetch_gmail_items():
        print(i["fuente_nombre"], "-", i["texto"][:80])
