from fastapi import FastAPI
import json
import os
import requests
from geopy.distance import geodesic

app = FastAPI(
    title="IDE Pergamino API",
    version="1.0"
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_FILE = os.path.join(BASE_DIR, "ide_normalizado.json")

DATA_URL = "https://github.com/fedeclerici-oss/ide-pergamino-api/releases/download/v1-data/ide_normalizado.json"


def cargar_datos():
    if not os.path.exists(DATA_FILE):
        r = requests.get(DATA_URL)
        r.raise_for_status()
        with open(DATA_FILE, "wb") as f:
            f.write(r.content)

    with open(DATA_FILE, encoding="utf-8") as f:
        return json.load(f)


DATA = cargar_datos()
FEATURES = DATA.get("features", [])


@app.get("/")
def root():
    return {
        "status": "ok",
        "features": len(FEATURES)
    }


@app.get("/buscar_texto")
def buscar_texto(q: str, limit: int = 20):
    q = q.lower()
    resultados = []

    for f in FEATURES:
        props = f.get("properties", {})
        if any(q in str(v).lower() for v in props.values()):
            resultados.append(f)

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
        d = geodesic((lat, lon), (lat_f, lon_f)).km

        if d <= radio_km:
            f["distancia_km"] = round(d, 3)
            encontrados.append(f)

    encontrados.sort(key=lambda x: x["distancia_km"])
    return encontrados[:limit]

