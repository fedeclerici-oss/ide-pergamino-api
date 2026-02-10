from fastapi import FastAPI
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
# INTERPRETACIÓN HUMANA
# =========================
def interpretar(pregunta: str):
    p = pregunta.lower().strip()

    categorias = {
        "escuela": ["escuela", "colegio", "primaria", "secundaria"],
        "hospital": ["hospital", "clinica", "sanatorio", "caps", "salita"],
        "plaza": ["plaza", "parque"],
    }

    cercania = [
        "cerca", "más cerca", "mas cerca", "cercano",
        "por aca", "por acá", "alrededor",
    ]

    siguiente = [
        "otro", "otra", "siguiente", "más",
        "otro más", "otra opción",
    ]

    categoria = None
    for c, palabras in categorias.items():
        if any(w in p for w in palabras):
            categoria = c
            break

    return {
        "categoria": categoria,
        "quiere_cercania": any(w in p for w in cercania),
        "quiere_siguiente": any(w in p for w in siguiente),
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

    info = interpretar(pregunta)
    mem = memoria.get(session_id, {})

    categoria = info["categoria"] or mem.get("categoria")
    lat = lat if lat is not None else mem.get("lat")
    lon = lon if lon is not None else mem.get("lon")

    if categoria is None:
        return {
            "respuesta": "¿Qué tipo de lugar estás buscando?",
            "datos": [],
        }

    candidatos = [l for l in lugares if texto_match(l, categoria)]

    if not candidatos:
        return {
            "respuesta": f"No encontré {categoria}.",
            "datos": [],
        }

    if lat is None or lon is None:
        memoria[session_id] = {
            "categoria": categoria,
            "lat": None,
            "lon": None,
            "resultados": [],
            "indice": 0,
            "ts": time.time(),
        }
        return {
            "respuesta": f"Encontré {len(candidatos)} {categoria}. Decime dónde estás y te digo el más cercano.",
            "datos": candidatos[:5],
        }

    # calcular distancias
    enriquecidos = []
    for l in candidatos:
        if l.get("lat") and l.get("lon"):
            l2 = l.copy()
            l2["distancia_m"] = round(
                distancia_metros(lat, lon, l["lat"], l["lon"]), 1
            )
            enriquecidos.append(l2)

    enriquecidos.sort(key=lambda x: x["distancia_m"])

    indice = mem.get("indice", 0)

    # siguiente opción
    if info["quiere_siguiente"]:
        indice += 1

    if indice >= len(enriquecidos):
        return {
            "respuesta": "No tengo más opciones cercanas.",
            "datos": [],
        }

    elegido = enriquecidos[indice]

    memoria[session_id] = {
        "categoria": categoria,
        "lat": lat,
        "lon": lon,
        "resultados": enriquecidos,
        "indice": indice,
        "ts": time.time(),
    }

    return {
        "respuesta": f"{elegido.get('nombre', 'Este')} está a {elegido['distancia_m']} metros.",
        "datos": [elegido],
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


