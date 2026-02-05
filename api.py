from fastapi import FastAPI, Query
import json
import os
import requests
from geopy.distance import geodesic

app = FastAPI(
    title="IDE Pergamino API",
    version="1.0"
)

# =========================
# CONFIG SEGURA PARA RENDER
# =========================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_FILE = os.path.join(BASE_DIR, "ide_normalizado.json")

DATA_URL = "https://github.com/fedeclerici-oss/ide-pergamino-api/releases/download/v1-data/ide_normalizado.json"

# =========================
# DESCARGA GARANTIZADA
# =========================

def cargar_datos():
    if not os.path.exists(DATA_FILE):
        print("⬇️ Descargando ide_normalizado.json...")
        r = requests.get(DATA_URL)
        r.raise_for_status()
        with open(DATA_FILE, "wb") as f:
            f.write(r.content)
        print("✅ Archivo descargado")

    with open(DATA_FILE, encoding="utf-8") as f:
        data = json.load(f)

    return data

DATA = cargar_datos()
FEATURES = DATA.get("features", [])

# =========================
# HELPERS
# =========================

def texto_en_feature(feature, texto):
    texto = texto.lower()
    props = feature.get("properties", {})
    return any(texto in str(v).lower() for v in props.values())

def distancia_km(lat1, lon1, lat2, lon2):
    return geodesic((lat1, lon1), (lat2, lon2)).km

# =========================
# ENDPOINTS
# =========================

@app.get("/")
def root():
    return {
        "status": "ok",
        "features": len(FEATURES)
    }

@app.get("/buscar_texto")
def buscar_texto(q: str, limit: int = 20):
    resultados = [f for f in FEATURES if texto_en_feature(f, q)]
    return resultados[:limit]

@app.get("/buscar_cerca")
def buscar_cerca(
    lat: float,
    lon: float,
    radio_km: float = 1.0,
    limit: int = 20
):
    encontrados = []

    for f in FEATURES:
        geom = f.get("geometry", {})
        if geom.get("type") != "Point":
            continue

        lon_f, lat_f = geom["coordinates"]
        d = distancia_km(lat, lon, lat_f, lon_f)

        if d <= radio_km:
            f["distancia_km"] = round(d, 3)
            encontrados.append(f)

    encontrados.sort(key=lambda x: x["distancia_km"])
    return encontrados[:limit]
