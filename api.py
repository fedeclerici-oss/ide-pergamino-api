from fastapi import FastAPI, Query
import requests
from geopy.distance import geodesic

app = FastAPI(title="IDE Pergamino API")

DATA_URL = "https://github.com/fedeclerici-oss/ide-pergamino-api/releases/download/v1-data/ide_normalizado.json"

FEATURES = []


def cargar_datos_remotos():
    global FEATURES
    print("Descargando ide_normalizado.json")

    response = requests.get(DATA_URL, timeout=60)
    response.raise_for_status()
    data = response.json()

    if isinstance(data, list):
        FEATURES = data
    elif isinstance(data, dict):
        FEATURES = data.get("features", [])
    else:
        FEATURES = []

    print("Datos cargados:", len(FEATURES))


cargar_datos_remotos()


@app.get("/")
def root():
    return {
        "status": "ok",
        "features": len(FEATURES)
    }


@app.get("/buscar_texto")
def buscar_texto(q: str = Query(..., min_length=2)):
    q = q.lower()
    resultados = []

    for f in FEATURES:
        props = f.get("properties", {})
        texto = " ".join([str(v).lower() for v in props.values()])

        if q in texto:
            resultados.append(f)

    return {
        "query": q,
        "total": len(resultados),
        "resultados": resultados[:50]
    }


@app.get("/buscar_cerca")
def buscar_cerca(
    lat: float,
    lon: float,
    radio_m: float = 500
):
    centro = (lat, lon)
    resultados = []

    for f in FEATURES:
        geom = f.get("geometry", {})
        if geom.get("type") != "Point":
            continue

        coords = geom.get("coordinates", [])
        if len(coords) != 2:
            continue

        punto = (coords[1], coords[0])
        distancia = geodesic(centro, punto).meters

        if distancia <= radio_m:
            item = f.copy()
            ite



