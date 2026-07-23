import os
from datetime import datetime, timedelta, timezone

from telethon.sync import TelegramClient
from telethon.sessions import StringSession

from config_loader import load_sources, load_settings


def fetch_telegram_items(ventana_horas=12):
    """Lee mensajes recientes de los canales de Telegram configurados, usando Telethon."""
    settings = load_settings()["telethon"]
    api_id = int(os.environ[settings["api_id_env"]])
    api_hash = os.environ[settings["api_hash_env"]]
    session_string = os.environ[settings["session_env"]]

    limite = datetime.now(timezone.utc) - timedelta(hours=ventana_horas)
    items = []

    with TelegramClient(StringSession(session_string), api_id, api_hash) as client:
        for canal in load_sources().get("telegram", []):
            username = canal["username"]
            if username.startswith("PLACEHOLDER"):
                continue
            try:
                for mensaje in client.iter_messages(username, limit=50):
                    if mensaje.date < limite:
                        break
                    if not mensaje.text:
                        continue
                    items.append({
                        "fuente_nombre": canal["nombre"],
                        "fuente_tipo": "telegram",
                        "peso": canal.get("peso", 0.5),
                        "texto": mensaje.text,
                        "link": f"https://t.me/{username}/{mensaje.id}",
                        "fecha": mensaje.date.isoformat(),
                    })
            except Exception as e:
                print(f"[WARN] No se pudo leer el canal {username}: {e}")

    return items


if __name__ == "__main__":
    for i in fetch_telegram_items():
        print(i["fuente_nombre"], "-", i["texto"][:80])
