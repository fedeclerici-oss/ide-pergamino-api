from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional
import json
import math
import os
import requests
import time
from openai import OpenAI

app = FastAPI(title="IDE Pergamino BOT - RAG Municipal")

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

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
client = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None

lugares = []
memoria = {}
MEMORIA_TTL = 600


# =========================
# UTILIDADES
# =========================
def distancia_metros(lat1, lon1, lat2, lon2):
    R = 6371000
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlambda/2)**2
    return 2 * R * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def normalizar(texto):
    return texto.lower().strip()


def limpiar_memoria():
    ahora = time.time()
    for k in list(memoria.keys()):
        if ahora - memoria[k]["ts"] > MEMORIA_TTL:
            del memoria[k]


# =========================
# BUSQUEDA BASE MUNICIPAL
# =========================
def buscar_en_base(pregunta, max_resultados=5):
    pregunta = normalizar(pregunta)
    resultados = []

    for l in lugares:
        texto = f"{l.get('nombre','')} {l.get('tipo','')} {l.get('capa_origen','')}".lower()
        if any(p in texto for p in pregunta.split()):
            resultados.append(l)

    return resultados[:max_resultados]


def construir_contexto(resultados):
    contexto = ""
    for l in resultados:
        contexto += f"""
Nombre: {l.get('nombre')}
Tipo: {l.get('tipo')}
Capa: {l.get('capa_origen')}
Latitud: {l.get('lat')}
Longitud: {l.get('lon')}
---
"""
    return contexto


# =========================
# IA CON CONTEXTO (RAG)
# =========================
def responder_con_rag(pregunta, lat=None, lon=None):
    if not client:
        return "La IA no está configurada."

    resultados = buscar_en_base(pregunta)

    contexto = construir_contexto(resultados) if resultados else "No se encontraron registros relevantes."

    prompt_sistema = """
Sos un asistente municipal inteligente de Pergamino.
Respondé usando la información del contexto si existe.
Si hay coordenadas, incluí un link de Google Maps.
Si el contexto no tiene datos suficientes, respondé con información general clara y breve.
"""

    prompt_usuario = f"""
Pregunta del ciudadano:
{pregunta}

Contexto municipal:
{contexto}
"""

    try:
        completion = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": prompt_sistema},
                {"role": "user", "content": prompt_usuario}
            ],
            temperature=0.3
        )

        return completion.choices[0].message.content

    except Exception as e:
        return f"Error en IA: {str(e)}"


# =========================
# CARGA DATOS
# =========================
@app.on_event("startup")
def cargar_datos():
    global lugares

    if not os.path.exists(DATA_PATH):
        r = requests.get(DATA_URL, timeout=60)
        r.raise_for_status()
        with open(DATA_PATH, "wb") as f:
            f.write(r.content)

    with open(DATA_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    lugares = data if isinstance(data, list) else data.get("features", [])
    print(f"✅ {len(lugares)} registros cargados")


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

    respuesta = responder_con_rag(pregunta, lat, lon)

    return {
        "respuesta": respuesta,
        "datos_usados": buscar_en_base(pregunta)
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
