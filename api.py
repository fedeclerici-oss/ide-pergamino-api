from fastapi import FastAPI
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

# memoria por sesión
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
    a = (
        math.sin(dphi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    )
    return 2 * R * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def texto_match(lugar, texto):
    t = texto.lower()
    for campo in ["nombre", "tipo", "subtipo", "descripcion", "capa_origen"]:
        v = lugar.get(campo)
        if v and t in str(v).lower():
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
        r = requests.get(DATA_URL, timeout=120)
        r.raise_for_status()
        with open(DATA_PATH, "wb") as f:
            f.write(r.content)

    with open(DATA_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    if isinstance(data, list):
        lugares = data
    elif isinstance(data, dict) and "features" in data:
        lugares = data["features"]
    else:
        lugares = []

    print(f"✅ Lugares cargados: {len(lugares)}")

# =========================
# INTERPRETACIÓN HUMANA
# =========================
def interpretar(pregunta: str):
    p = pregunta.lower().strip()

    categorias = {
        "escuela": ["escuela", "colegio", "primaria", "secundaria"],
        "hospital": ["hospital", "clinica", "sanatorio", "caps", "salita"],
        "plaza": ["plaza", "parque"],
        "calle": ["calle", "avenida", "av", "bulevar"],
    }

    palabras_cercania = [
        "cerca", "cercano", "cercana",
        "por aca", "por acá", "alrededor",
        "más cerca", "mas cerca"
    ]

    palabras_lista = [
        "todos", "todas", "lista", "ver",
        "mostrar", "hay", "existen"
    ]

    categoria = None
    for c, palabras in categorias.items():
        if any(w in p for w in palabras):
            categoria = c
            break

    quiere_cercania = any(w in p for w in palabras_cercania)
    quiere_lista = any(w in p for w in palabras_lista)

    # preguntas cortas tipo "escuelas"
    if categoria and len(p.split()) <= 2:
        quiere_lista = True

    return {
        "categoria": categoria,
        "quiere_cercania": quiere_cercania,
        "quiere_lista": quiere_lista,
    }

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

    intent = interpretar(pregunta)
    mem = memoria.get(session_id, {})

    categoria = intent["categoria"] or mem.get("categoria")
    lat = lat if lat is not None else mem.get("lat")
    lon = lon if lon is not None else mem.get("lon")

    if categoria is None:
        return {
            "respuesta": "¿Qué tipo de lugar estás buscando?",
            "datos": [],
        }

    memoria[session_id] = {
        "categoria": categoria,
        "lat": lat,
        "lon": lon,
        "ts": time.time(),
    }

    candidatos = [l for l in lugares if texto_match(l, categoria)]

    if not candidatos:
        return {
            "respuesta": f"No encontré {categoria}.",
            "datos": [],
        }

    # SIN UBICACIÓN → lista útil
    if lat is None or lon is None:
        return {
            "respuesta": f"Encontré {len(candidatos)} {categoria}. Si me decís dónde estás, te digo el más cercano.",
            "datos": candidatos[:5],
        }

    # CON UBICACIÓN → cercanía real
    enriquecidos = []
    for l in candidatos:
        if l.get("lat") is None or l.get("lon") is None:
            continue
        d = distancia_metros(lat, lon, l["lat"], l["lon"])
        l2 = l.copy()
        l2["distancia_m"] = round(d, 1)
        enriquecidos.append(l2)

    if not enriquecidos:
        return {
            "respuesta": "Tengo lugares, pero no coordenadas para calcular cercanía.",
            "datos": [],
        }

    enriquecidos.sort(key=lambda x: x["distancia_m"])
    top = enriquecidos[:3]

    return {
        "respuesta": f"El lugar más cercano está a {top[0]['distancia_m']} metros.",
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
        "sesiones_activas": len(memoria),
    }


