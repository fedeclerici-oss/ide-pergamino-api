import os
import requests

TELEGRAM_TOKEN = os.environ.get("8194327418:AAHPcGcIP_2yWROgXix7LN-mIERODW8qny0")
API_URL = os.environ.get("https://ide-pergamino-api.onrender.com")

TG_API = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"

def enviar(chat_id, texto):
    requests.post(
        f"{TG_API}/sendMessage",
        json={
            "chat_id": chat_id,
            "text": texto
        },
        timeout=20
    )

def handler(update):
    message = update.get("message")
    if not message:
        return

    chat_id = message["chat"]["id"]
    texto = message.get("text", "")

    lat = None
    lon = None

    if "location" in message:
        lat = message["location"]["latitude"]
        lon = message["location"]["longitude"]

    params = {
        "session_id": str(chat_id),
        "pregunta": texto
    }

    if lat and lon:
        params["lat"] = lat
        params["lon"] = lon

    try:
        r = requests.get(f"{API_URL}/bot", params=params, timeout=30)
        data = r.json()
        respuesta = data.get("respuesta", "No entendí bien 😅")
    except Exception:
        respuesta = "Hubo un problema técnico, intentá de nuevo 🙏"

    enviar(chat_id, respuesta)
