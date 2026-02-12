from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional
import json
import math
import os
import requests
import time
from openai import OpenAI

app = FastAPI(title="IDE Pergamino BOT Inteligente")

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
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")

client = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None

lugares = []
memoria = {}
MEMORIA_TTL = 600  # 10 minutos


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
# BUSQUEDA SIMPLE EN BASE
# =========================
def buscar_en_base(pregunta, lat=None, lon=None, radio=2000, max_resultados=5):
    pregunta = normalizar(pregunta)
    resultados = []

    for l in lugares:
        nombre = l.get("nombre", "").lower()
        tipo = l.get("tipo", "").lower()
        capa = l.get("capa_origen", "").lower()

        texto = f"{nombre} {tipo} {capa}"

        if any(p in texto for p in pregunta.split()):
            if lat and lon and l.get("lat") and l.get("lon"):
                dist = distancia_metros(lat, lon, l["lat"], l["lon"])
                if dist <= radio:
                    l["distancia"] = round(dist, 1)
                    resultados.append(l)
            else:
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
Distancia: {l.get('distancia', 'N/D')} metros
---
"""
    return contexto


# =========================
# RESPUESTA CON IA (RAG)
# =========================
def responder_con_rag(pregunta, lat=None, lon=None):
    if not client:
        return "La IA no está configurada correctamente."

    resultados = buscar_en_base(pregunta, lat, lon)

    contexto = construir_contexto(resultados) if resultados else "No hay registros municipales relevantes."

    prompt_sistema = """
Sos un asistente municipal inteligente de Pergamino.
Respondé usando prioritariamente el contexto municipal proporcionado.
Si hay coordenadas, agregá link de Google Maps.
Si no hay datos suficientes, respondé de forma clara y breve.
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
# CARGA DE DATOS
# =========================
@app.on_event("startup")
def cargar_datos():
    global lugares

    if not os.path.exists(DATA_PATH):
        print("Descargando base IDE...")
        r = requests.get(DATA_URL, timeout=60)
        r.raise_for_status()
        with open(DATA_PATH, "wb") as f:
            f.write(r.content)

    with open(DATA_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    # SOLO guardamos campos necesarios (optimiza memoria)
    lugares = []
    for item in data:
        lugares.append({
            "nombre": item.get("nombre"),
            "tipo": item.get("tipo"),
            "capa_origen": item.get("capa_origen"),
            "lat": item.get("lat"),
            "lon": item.get("lon"),
        })

    print(f"✅ {len(lugares)} registros cargados")


# =========================
# ENDPOINT PRINCIPAL
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

    return {"respuesta": respuesta}


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

            respuesta = responder_con_rag(
                "¿Qué hay cerca?",
                lat,
                lon
            )
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
