import os
import requests
from flask import Flask, request

app = Flask(__name__)

# =========================
# CONFIG TELEGRAM
# =========================
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
TELEGRAM_API_URL = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"

# =========================
# FUNCION PARA RESPONDER
# =========================
def send_message(chat_id, text):
    url = f"{TELEGRAM_API_URL}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text
    }
    requests.post(url, json=payload)

# =========================
# WEBHOOK TELEGRAM
# =========================
@app.route("/telegram/webhook", methods=["POST"])
def telegram_webhook():
    data = request.get_json()

    if not data:
        return "ok"

    message = data.get("message")
    if not message:
        return "ok"

    chat_id = message["chat"]["id"]
    text = message.get("text", "").lower()

    # ---- LOGICA DEL BOT ----
    if text in ["/start", "hola", "hi"]:
        send_message(chat_id, "👋 Hola! El bot está vivo y funcionando.")
    else:
        send_message(chat_id, f"📩 Recibí tu mensaje: {text}")

    return "ok"

# =========================
# HEALTH CHECK (Render)
# =========================
@app.route("/")
def index():
    return "API Telegram OK"

# =========================
# MAIN
# =========================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)


