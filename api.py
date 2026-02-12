from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional
import json
import math
import os
import requests
import time

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
        "hospital": ["hospital", "clinica", "caps", "salita", "sanatorio"],
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


# =========================
# CONSULTAS POR CAPA (NUEVO)
# =========================
def contar_por_capa(nombre_parcial):
    coincidencias = [
        l for l in lugares
        if nombre_parcial in str(l.get("capa_origen", "")).lower()
    ]
    return len(coincidencias)


def detectar_consulta_estadistica(pregunta: str):
    p = pregunta.lower()

    if "cuánt" not in p and "cuantos" not in p:
        return None

    if "luminaria" in p:
        total = contar_por_capa("luminaria")
        return f"Hay {total} luminarias registradas."

    if "semaforo" in p:
        total = contar_por_capa("semaforo")
        return f"Hay {total} semáforos registrados."

    if "barrio" in p:
        total = contar_por_capa("barrios")
        return f"Hay {total} barrios registrados."

    if "cloaca" in p:
        total = contar_por_capa("cloaca")
        return f"Hay {total} registros vinculados a cloacas."

    if "agua" in p:
        total = contar_por_capa("agua")
        return f"Hay {total} registros vinculados a red de agua."

    if "total" in p:
        return f"El IDE tiene {len(lugares)} registros totales cargados."

    return None


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
# BOT INTELIGENTE
# =========================
@app.get("/bot")
def bot(
    session_id: str,
    pregunta: str,
    lat: Optional[float] = None,
    lon: Optional[float] = None,
):
    limpiar_memoria()

    # 🔥 PRIMERO: detectar consultas estadísticas
    estadistica = detectar_consulta_estadistica(pregunta)
    if estadistica:
        return {"respuesta": estadistica, "datos": []}

    categoria, quiere_cercania = interpretar(pregunta)
    mem = memoria.get(session_id, {})

    if categoria is None:
        categoria = mem.get("categoria")

    if lat is None or lon is None:
        lat = mem.get("lat")
        lon = mem.get("lon")

    if categoria is None:
        return {"respuesta": "¿Qué tipo de lugar estás buscando?", "datos": []}

    memoria[session_id] = {
        "categoria": categoria,
        "lat": lat,
        "lon": lon,
        "ts": time.time()
    }

    candidatos = [
        l for l in lugares
        if categoria in str(l.get("tipo", "")).lower()
        or categoria in str(l.get("nombre", "")).lower()
    ]

    if not candidatos:
        return {"respuesta": f"No encontré {categoria}.", "datos": []}

    if lat is None or lon is None:
        return {
            "respuesta": f"Encontré {len(candidatos)} {categoria}. Si me pasás tu ubicación te digo el más cercano.",
            "datos": candidatos[:5]
        }

    enriquecidos = []
    for l in candidatos:
        if l.get("lat") and l.get("lon"):
            d = distancia_metros(lat, lon, l["lat"], l["lon"])
            l2 = l.copy()
            l2["distancia_m"] = round(d, 1)
            enriquecidos.append(l2)

    enriquecidos.sort(key=lambda x: x["distancia_m"])
    top = enriquecidos[:3]

    return {
        "respuesta": f"El más cercano está a {top[0]['distancia_m']} metros.",
        "datos": top
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
                pregunta="cerca",
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
                "text": resultado["respuesta"]
            }
        )

    return {"ok": True}



