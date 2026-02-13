from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional
import json
import math
import os
import requests
import time
import google.generativeai as genai

app = FastAPI(title="IDE Pergamino BOT - RAG Municipal (Low Memory)")

# =========================
# CORS
# =========================
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# =========================
# CONFIG
# =========================
DATA_URL = "https://github.com/fedeclerici-oss/ide-pergamino-api/releases/download/v1.0.0/ide_normalizado.json"
DATA_PATH = "ide_normalizado.json"

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
    modelo_ia = genai.GenerativeModel("gemini-1.5-flash")
else:
    modelo_ia = None

memoria = {}
MEMORIA_TTL = 600


# =========================
# UTILIDADES
# =========================
def normalizar(texto):
    return texto.lower().strip()


def limpiar_memoria():
    ahora = time.time()
    for k in list(memoria.keys()):
        if ahora - memoria[k]["ts"] > MEMORIA_TTL:
            del memoria[k]


# =========================
# BUSQUEDA LIVIANA (SIN RAM)
# =========================
def buscar_en_base(pregunta, max_resultados=5):
    pregunta = normalizar(pregunta)
    resultados = []

    if not os.path.exists(DATA_PATH):
        return resultados

    with open(DATA_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
        registros = data if isinstance(data, list) else data.get("features", [])

        for l in registros:
            texto = f"{l.get('nombre','')} {l.get('tipo','')} {l.get('capa_origen','')}".lower()
            if any(p in texto for p in pregunta.split()):
                resultados.append(l)
                if len(resultados) >= max_resultados:
                    break

    return resultados


# =========================
# IA + RAG
# =========================
def responder(pregunta, lat=None, lon=None):

    resultados = buscar_en_base(pregunta)

    # 🔹 Si encuentra en base municipal → responde sin IA
    if resultados:
        respuesta = "Encontré estos registros municipales:\n\n"
        for l in resultados:
            respuesta += f"• {l.get('nombre')} ({l.get('tipo')})\n"

            if l.get("lat") and l.get("lon"):
                respuesta += f"https://www.google.com/maps?q={l.get('lat')},{l.get('lon')}\n"

            respuesta += "\n"

        return respuesta.strip()

    # 🔹 Si no encuentra → usa Gemini
    if not modelo_ia:
        return "No encontré datos en la base municipal y la IA no está configurada."

    prompt = f"""
Sos un asistente municipal inteligente de la ciudad de Pergamino.
Respondé claro, breve y profesional.
Si es una consulta municipal, orientá al vecino correctamente.

Pregunta:
{pregunta}
"""

    try:
        response = modelo_ia.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"Error IA: {str(e)}"


# =========================
# STARTUP (SIN CARGAR EN RAM)
# =========================
@app.on_event("startup")
def startup_event():
    if not os.path.exists(DATA_PATH):
        print("Descargando base municipal...")
        r = requests.get(DATA_URL, timeout=120)
        r.raise_for_status()
        with open(DATA_PATH, "wb") as f:
            f.write(r.content)

    print("✅ Archivo listo (no cargado en memoria)")


# =========================
# ENDPOINT BOT
# =========================
@app.get("/bot")
def bot(
    session_id: str,
    pregunta: str,
    lat: Optional[float] = None,
    lon: Optional[float] = None,
):
    limpiar_memoria()

    mem = memoria.get(session_id, {})

    if lat is None:
        lat = mem.get("lat")
    if lon is None:
        lon = mem.get("lon")

    memoria[session_id] = {
        "lat": lat,
        "lon": lon,
        "ts": time.time()
    }

    respuesta = responder(pregunta, lat, lon)

    return {
        "respuesta": respuesta
    }


# =========================
# TELEGRAM WEBHOOK
# =========================
@app.post("/telegram")
async def telegram_webhook(request: Request):
    data = await request.json()

    if "message" in data:
        chat_id = data["message"]["chat"]["id"]

        if "location" in data["message"]:
            lat = data["message"]["location"]["latitude"]
            lon = data["message"]["location"]["longitude"]

            resultado = bot(
                session_id=str(chat_id),
                pregunta="¿Qué hay en esta zona?",
                lat=lat,
                lon=lon
            )
        else:
            text = data["message"].get("text", "")
            resultado = bot(
                session_id=str(chat_id),
                pregunta=text
            )

        requests.post(
            f"https://api.telegram.org/bot{os.environ.get('TELEGRAM_TOKEN')}/sendMessage",
            json={
                "chat_id": chat_id,
                "text": resultado["respuesta"],
                "disable_web_page_preview": True
            }
        )

    return {"ok": True}
