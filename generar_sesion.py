from telethon.sync import TelegramClient
from telethon.sessions import StringSession

api_id = int(input("Ingresa tu api_id: "))
api_hash = input("Ingresa tu api_hash: ")

with TelegramClient(StringSession(), api_id, api_hash) as client:
    print("\n\nTU SESSION STRING (guárdala, es secreta):\n")
    print(client.session.save())
