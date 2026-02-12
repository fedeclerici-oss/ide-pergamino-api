from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional
import json
import math
import os
import requests
from openai import OpenAI

app = FastAPI(title="IDE Pergamino BOT Liviano")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DATA_URL = "https://github.com/fedeclerici-oss/ide-pergamino-api/releases/download/v1.0.0/ide_normalizado.json"

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")

client = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None


# =========================
# UTILIDAD DISTANCIA
# =========================
def distancia_metros(lat1, lon1, lat2, lon2):
    R = 6371000
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlambda/2)**2
    return 2 * R * math.atan2(math.sqrt(a), math.sqrt(1 - a))


# =========================
# BUSQUEDA EN STREAMING
# =========================
def buscar_en_base(pregunta, lat=None, lon=None, radio=2000, max_resultados=5):
    pregunta = pregunta.lower()
    resultados = []

    r = requests.get(DATA_URL, timeout=60)
    data = r.json()

    for item in data:
        nombre = str(item.get("nombre", "")).lower()
        tipo = str(item.get("tipo", "")).lower()
        capa = str(item.get("capa_origen", "")).lower()

        texto = f"{nombre} {tipo} {capa}"

        if any(p in texto for p in pregunta.split()):
            if lat and lon and item.get("lat") and item.get("lon"):
                dist = distancia_metros(lat, lon, item["lat"], item["lon"])
                if dist <= radio:
                    resultados.append({
                        "nombre": item.get("nombre"),
                        "tipo": item.get("tipo"),
                        "lat": item.get("lat"),
                        "lon": item.get("lon"),
                        "distancia": round(dist, 1)
                    })
            else:
                resultados.append({
                    "nombre": item.get("nombre"),
                    "tipo": item.get("tipo"),
                    "lat": item.get("lat"),
                    "lon": item.get("lon"),
                })

        if len(resultados) >= max_resultados:
            break

    return resultados


# =========================
# RESPUESTA CON IA
# =========================
def responder_con_rag(pregunta, lat=None, lon=None):
    if not client:
        return "IA no configurada."

    resultados = buscar_en_base(pregunta, lat, lon)

    contexto = json.dumps(resultados, indent=2)

    prompt = f"""
Sos un asistente municipal de Pergamino.

Pregunta:
{pregunta}

Datos municipales encontrados:
{contexto}

Respondé usando esos datos.
Si hay coordenadas, agregá link Google Maps.
Si no hay datos suficientes, decilo claramente.
"""

    try:
        completion = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3
        )

        return completion.choices[0].message.content

    except Exception as e:
        return f"Error IA: {str(e)}"


# =========================
# ENDPOINT
# =========================
@app.get("/bot")
def bot(
    pregunta: str,
    lat: Optional[float] = None,
    lon: Optional[float] = None,
):
    respuesta = responder_con_rag(pregunta, lat, lon)
    return {"respuesta": respuesta}


# =========================
# TELEGRAM
# =========================
@app.post("/telegram")
async def telegram_webhook(request: Request):
    data = await request.json()

    if "message" in data:
        chat_id = data["message"]["chat"]["id"]

        if "location" in data["message"]:
            lat = data["message"]["location"]["latitude"]
            lon = data["message"]["location"]["longitude"]
            respuesta = responder_con_rag("¿Qué hay cerca?", lat, lon)
        else:
            text = data["message"].get("text", "")
            respuesta = responder_con_rag(text)

        if TELEGRAM_TOKEN:
            requests.post(
                f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
                json={
                    "chat_id": chat_id,
                    "text": respuesta,
                    "disable_web_page_preview": True
                }
            )

    return {"ok": True}
