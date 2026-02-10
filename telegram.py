import os
import requests
from fastapi import FastAPI, Request

# =========================
# CONFIG
# =========================
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
API_URL = os.getenv("API_URL")  # ej: https://ide-pergamino-api.onrender.com

if not TELEGRAM_TOKEN or not API_URL:
    raise RuntimeError("Faltan variables de entorno TELEGRAM_TOKEN o API_URL")

TELEGRAM_API = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"

app = FastAPI(title="IDE Pergamino Telegram Bot")

# =========================
# UTIL
# =========================
def enviar_mensaje(chat_id: int, texto: str):
    requests.post(
        f"{TELEGRAM_API}/sendMessage",
        json={
            "chat_id": chat_id,
            "text": texto,
            "parse_mode": "HTML"
        },
        timeout=10
    )

# =========================
# WEBHOOK
# =========================
@app.post("/telegram")
async def telegram_webhook(req: Request):
    data = await req.json()

    if "message" not in data:
        return {"ok": True}

    mensaje = data["message"]
    chat_id = mensaje["chat"]["id"]
    texto = mensaje.get("text", "")

    if not texto:
        enviar_mensaje(chat_id, "No entendí el mensaje 😅")
        return {"ok": True}

    # session por chat
    session_id = f"telegram_{chat_id}"

    try:
        r = requests.get(
            f"{API_URL}/bot",
            params={
                "session_id": session_id,
                "pregunta": texto
            },
            timeout=15
        )
        r.raise_for_status()
        res = r.json()
    except Exception:
        enviar_mensaje(chat_id, "Hubo un problema hablando con la API 😬")
        return {"ok": True}

    respuesta = res.get("respuesta", "No encontré respuesta.")
    datos = res.get("datos", [])

    mensaje_final = respuesta

    if datos:
        mensaje_final += "\n\n"
        for d in datos:
            nombre = d.get("nombre", "Sin nombre")
            dist = d.get("distancia_m")
            if dist is not None:
                mensaje_final += f"📍 {nombre} ({dist} m)\n"
            else:
                mensaje_final += f"📍 {nombre}\n"

    enviar_mensaje(chat_id, mensaje_final)

    return {"ok": True}

# =========================
# HEALTH
# =========================
@app.get("/")
def health():
    return {"status": "telegram bot ok"}
