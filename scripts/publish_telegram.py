import os

import requests

from config_loader import load_settings


def publicar_en_telegram(noticias):
    settings = load_settings()["telegram_bot"]
    token = os.environ[settings["token_env"]]
    chat_id = os.environ[settings["chat_id_env"]]

    url = f"https://api.telegram.org/bot{token}/sendMessage"

    for noticia in noticias:
        resp = requests.post(url, data={
            "chat_id": chat_id,
            "text": noticia["texto"],
            "disable_web_page_preview": True,
        })
        if not resp.ok:
            print(f"[ERROR] No se pudo publicar en Telegram: {resp.status_code} {resp.text}")
