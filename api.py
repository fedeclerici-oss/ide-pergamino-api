from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional
import json
import math
import os
import requests
import time

app = FastAPI(title="IDE Pergamino API")

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

# memoria simple
memoria = {}
MEMORIA_TTL = 300  # segundos

# =========================
# UTILIDADES
# =========================
def distancia_metros(lat1, lon1, lat2, lon2):
    R = 6371000
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * R * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def texto_match(lugar, q):
    q = q.lower()
    for campo in ["nombre", "tipo", "subtipo", "descripcion", "capa_origen"]:
        valor = lugar.get(campo)
        if valor and q in str(valor).lower():
            return True
    return False


def limpiar_memoria():
    ahora = time.time()
    for k in list(memoria.keys()):
        if ahora - memoria[k]["ts"] > MEMORIA_TTL:
            del memoria[k]

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
# INTERPRETAR
# =========================
def interpretar(pregunta: str):
    p = pregunta.lower()
    categorias = {
        "escuela": ["escuela", "colegio", "primaria", "secundaria"],
        "hospital": ["hospital", "clinica", "caps", "salita"],
        "plaza": ["plaza", "parque"],
        "calle": ["calle", "avenida", "av"],
    }

    categoria = None
    for c, palabras in categorias.items():
        if any(w in p for w in palabras):
            categoria = c
            break

    usa_cercania = any(x in p for x in ["cerca", "por acá", "alrededor"])
    return categoria, usa_cercania

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

    categoria, usa_cercania = interpretar(pregunta)
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
        "ts": time.time(),
    }

    candidatos = [l for l in lugares if texto_match(l, categoria)]

    if not candidatos:
        return {"respuesta": f"No encontré {categoria}.", "datos": []}

    if lat is None or lon is None:
        return {
            "respuesta": f"Encontré {len(candidatos)} {categoria}. Decime dónde estás.",
            "datos": candidatos[:5],
        }

    enriquecidos = []
    for l in candidatos:
        if l.get("lat") is None or l.get("lon") is None:
            continue
        d = distancia_metros(lat, lon, l["lat"], l["lon"])
        l2 = l.copy()
        l2["distancia_m"] = round(d, 1)
        enriquecidos.append(l2)

    enriquecidos.sort(key=lambda x: x["distancia_m"])
    top = enriquecidos[:3]

    return {
        "respuesta": f"El más cercano está a {top[0]['distancia_m']} metros.",
        "datos": top,
    }

# =========================
# HEALTH
# =========================
@app.get("/")
def health():
    return {
        "status": "ok",
        "lugares": len(lugares),
        "sesiones": len(memoria),
    }


