from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional
import json
import math
import os
import requests
import time
from openai import OpenAI

app = FastAPI(title="IDE Pergamino BOT API")

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


def limpiar_memoria():
    ahora = time.time()
    for k in list(memoria.keys()):
        if ahora - memoria[k]["ts"] > MEMORIA_TTL:
            del memoria[k]


def interpretar(pregunta: str):
    p = pregunta.lower()

    categorias = {
        "escuela": ["escuela", "colegio", "primaria", "secundaria"],
        "hospital": ["hospital", "clinica", "caps", "salita", "sanatorio", "salud"],
        "plaza": ["plaza", "parque"],
        "calle": ["calle", "avenida", "av", "bulevar"]
    }

    categoria = None
    for c, palabras in categorias.items():
        if any(w in p for w in palabras):
            categoria = c
            break

    quiere_cercania = any(x in p for x in ["cerca", "cercano", "alrededor", "más cerca"])

    return categoria, quiere_cercania


def responder_con_ia(pregunta):
    if not client:
        return "No tengo IA configurada."

    try:
        completion = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "Sos un asistente municipal de Pergamino. Respondé claro y breve."},
                {"role": "user", "content": pregunta}
            ]
        )
        return completion.choices[0].message.content
    except:
        return "No pude procesar la consulta en este momento."


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
    print(f"✅ {len(lugares)} lugares cargados")


# =========================
# BOT
# =========================
@app.get("/bot")
def bot(
    session_id: str,
    pregunta: str,
    lat: Optional[float] = None,
    lon: Optional[float] = None,
):
    limpiar_memoria()

    categoria, quiere_cercania = interpretar(pregunta)
    mem = memoria.get(session_id, {})

    if categoria is None:
        categoria = mem.get("categoria")

    if lat is None or lon is None:
        lat = mem.get("lat")
        lon = mem.get("lon")

    memoria[session_id] = {
        "categoria": categoria,
        "lat": lat,
        "lon": lon,
        "ts": time.time()
    }

    # =========================
    # SI NO HAY CATEGORIA → IA
    # =========================
    if categoria is None:
        respuesta_ia = responder_con_ia(pregunta)
        return {"respuesta": respuesta_ia, "datos": []}

    candidatos = [
        l for l in lugares
        if categoria in str(l.get("tipo", "")).lower()
        or categoria in str(l.get("nombre", "")).lower()
    ]

    # =========================
    # SI NO ENCUENTRA DATOS → IA
    # =========================
    if not candidatos:
        respuesta_ia = responder_con_ia(pregunta)
        return {"respuesta": respuesta_ia, "datos": []}

    # =========================
    # SIN UBICACIÓN → GOOGLE MAPS
    # =========================
    if lat is None or lon is None:
        top = candidatos[:3]
        texto = ""

        for l in top:
            nombre = l.get("nombre", "Sin nombre")
            lat_l = l.get("lat")
            lon_l = l.get("lon")

            if lat_l and lon_l:
                link = f"https://www.google.com/maps/search/?api=1&query={lat_l},{lon_l}"
            else:
                link = "Ubicación no disponible"

            texto += f"{nombre}\n{link}\n\n"

        return {"respuesta": texto.strip(), "datos": top}

    # =========================
    # CON UBICACIÓN → MÁS CERCANO
    # =========================
    enriquecidos = []

    for l in candidatos:
        if l.get("lat") and l.get("lon"):
            d = distancia_metros(lat, lon, l["lat"], l["lon"])
            l2 = l.copy()
            l2["distancia_m"] = round(d, 1)
            enriquecidos.append(l2)

    enriquecidos.sort(key=lambda x: x["distancia_m"])

    if not enriquecidos:
        return {"respuesta": "No encontré resultados con coordenadas.", "datos": []}

    top = enriquecidos[:3]

    texto = f"El más cercano está a {top[0]['distancia_m']} metros.\n\n"

    for l in top:
        link = f"https://www.google.com/maps/search/?api=1&query={l['lat']},{l['lon']}"
        texto += f"{l.get('nombre','Sin nombre')}\n{link}\n\n"

    return {"respuesta": texto.strip(), "datos": top}


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
                pregunta="zona",
                lat=lat,
                lon=lon
            )
            respuesta = resultado["respuesta"]

        else:
            text = data["message"].get("text", "")
            resultado = bot(
                session_id=str(chat_id),
                pregunta=text
            )
            respuesta = resultado["respuesta"]

        requests.post(
            f"https://api.telegram.org/bot{os.environ.get('TELEGRAM_TOKEN')}/sendMessage",
            json={
                "chat_id": chat_id,
                "text": respuesta,
                "disable_web_page_preview": True
            }
        )

    return {"ok": True}
