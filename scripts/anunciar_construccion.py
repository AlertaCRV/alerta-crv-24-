import os

import requests

from config_loader import load_settings

MENSAJE = (
    "🚧 AVISO: Sistema en fase de pruebas 🚧\n\n"
    "Este canal y el sitio web de Sala Situacional / Gestión del Riesgo de "
    "Desastre se encuentran actualmente en construcción y fase de pruebas.\n\n"
    "Durante este período, es posible que se publiquen alertas con errores, "
    "inexactitudes, o ubicaciones incorrectas mientras se ajusta el sistema. "
    "Por favor, verifica la información de forma independiente antes de "
    "tomar decisiones basadas en estos reportes."
)


def main():
    settings = load_settings()["telegram_bot"]
    token = os.environ[settings["token_env"]]
    chat_id = os.environ[settings["chat_id_env"]]

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    resp = requests.post(url, data={
        "chat_id": chat_id,
        "text": MENSAJE,
        "disable_web_page_preview": True,
    })
    if not resp.ok:
        raise RuntimeError(f"No se pudo publicar en Telegram: {resp.status_code} {resp.text}")
    print("Anuncio publicado en Telegram.")


if __name__ == "__main__":
    main()
