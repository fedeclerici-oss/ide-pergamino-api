import os
import requests
from fastapi import FastAPI, Request

app = FastAPI()

# =========================
# CONFIG TELEGRAM
# =========================
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
TELEGRAM_API_URL = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"

# =========================
# FUNCION PARA RESPONDER
# =========================
def send_message(chat_id: int, text: str):
    url = f"{TELEGRAM_API_URL}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text
    }
    requests.post(url, json=payload)

# =========================
# WEBHOOK TELEGRAM
# =========================
@app.post("/telegram/webhook")
async def telegram_webhook(request: Request):
    data = await request.json()

    if "message" not in data:
        return {"ok": True}

    message = data["message"]
    chat_id = message["chat"]["id"]
    text = message.get("text", "").lower()

    # ---- LOGICA DEL BOT ----
    if text in ["/start", "hola", "hi"]:
        send_message(chat_id, "👋 Hola! El bot está activo y escuchando.")
    else:
        send_message(chat_id, f"📩 Entendí esto: {text}")

    return {"ok": True}

# =========================
# HEALTH CHECK
# =========================
@app.get("/")
def root():
    return {"status": "API Telegram OK"}


