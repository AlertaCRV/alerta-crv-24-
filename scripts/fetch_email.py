import os
import unicodedata
from datetime import datetime, timedelta, timezone

import msal
import requests

from classify import detectar_ubicacion

TIPO_MAP = {
    "sismo": "sismo",
    "incendio": "incendio",
    "inundacion": "inundacion",
    "deslizamiento": "deslizamiento",
    "falla electrica": "infraestructura_electrica",
    "falla de agua": "infraestructura_agua",
    "vialidad": "vialidad",
    "orden publico": "orden_publico",
    "salud publica": "salud_publica",
}

SEVERIDADES_VALIDAS = {"critico", "alto", "medio", "bajo"}


def _normalizar(texto):
    texto = texto.strip().lower()
    return "".join(c for c in unicodedata.normalize("NFD", texto) if unicodedata.category(c) != "Mn")


def _obtener_access_token():
    client_id = os.environ["OUTLOOK_CLIENT_ID"]
    tenant_id = os.environ["OUTLOOK_TENANT_ID"]
    refresh_token = os.environ["OUTLOOK_REFRESH_TOKEN"]

    app = msal.PublicClientApplication(
        client_id,
        authority=f"https://login.microsoftonline.com/{tenant_id}",
    )
    result = app.acquire_token_by_refresh_token(refresh_token, scopes=["Mail.Read"])
    if "access_token" not in result:
        raise Exception(f"No se pudo obtener token de acceso: {result.get('error_description')}")
    return result["access_token"]


def _parsear_asunto(asunto):
    """Espera el formato: EMERGENCIA | Estado | Tipo | Severidad"""
    partes = [p.strip() for p in asunto.split("|")]
    if len(partes) != 4 or _normalizar(partes[0]) != "emergencia":
        return None

    _, estado_raw, tipo_raw, severidad_raw = partes

    ubicacion, _ = detectar_ubicacion(f"#{estado_raw.replace(' ', '')}")
    tipo = TIPO_MAP.get(_normalizar(tipo_raw))
    severidad = _normalizar(severidad_raw)
    if severidad not in SEVERIDADES_VALIDAS:
        severidad = "sin_clasificar"

    if not ubicacion or not tipo:
        return None

    return ubicacion, tipo, severidad


def fetch_email_items(ventana_horas=12):
    try:
        token = _obtener_access_token()
    except Exception as e:
        print(f"[WARN] No se pudo autenticar con Outlook: {e}")
        return []

    limite = (datetime.now(timezone.utc) - timedelta(hours=ventana_horas)).strftime("%Y-%m-%dT%H:%M:%SZ")
    url = (
        "https://graph.microsoft.com/v1.0/me/messages"
        f"?$filter=receivedDateTime ge {limite}"
        "&$select=subject,bodyPreview,receivedDateTime,from,webLink"
        "&$top=50"
    )
    headers = {"Authorization": f"Bearer {token}"}

    resp = requests.get(url, headers=headers)
    if not resp.ok:
        print(f"[WARN] Error consultando Outlook: {resp.status_code} {resp.text}")
        return []

    items = []
    for mensaje in resp.json().get("value", []):
        parsed = _parsear_asunto(mensaje.get("subject", ""))
        if not parsed:
            continue
        ubicacion, tipo, severidad = parsed
        remitente = mensaje.get("from", {}).get("emailAddress", {}).get("address", "desconocido")

        items.append({
            "fuente_nombre": f"Reporte institucional ({remitente})",
            "fuente_tipo": "correo",
            "peso": 1.5,
            "texto": f"{mensaje.get('subject', '')}. {mensaje.get('bodyPreview', '')}",
            "link": mensaje.get("webLink", ""),
            "fecha": mensaje["receivedDateTime"],
            "_preclasificado": {"ubicacion": ubicacion, "tipos": [tipo], "severidad": severidad},
        })

    return items
