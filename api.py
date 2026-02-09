from fastapi import FastAPI, Query
import requests
from geopy.distance import geodesic

app = FastAPI(title="IDE Pergamino API")

DATA_URL = "https://github.com/fedeclerici-oss/ide-pergamino-api/releases/download/v1-data/ide_normalizado.json"

FEATURES = []


def cargar_datos_remotos():
    global FEATURES
    print("⬇️ Descargando ide_normalizado.json...")

    r = requests.get(DATA_URL, timeout=60)
    r.raise_for_status()
    data = r.json()

    # 🧠 SOPORTA LISTA O FEATURECOLLECTION
    if isinstance(data, list):
        FEATURES = data
    elif isinstance(data, dict):
        FEATURES = data.get("features", [])
    else:
        FEATURES = []

    print(f"✅ Datos cargados: {len(FEATURES)} features")


# 🔥 se carga una sola vez al iniciar
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
        texto = " ".join(str(v).lower() for v in props.values())

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
        dist = geodesic(centro, punto).meters

        if dist <= radio_m:
            f_copy = f.copy()
            f_copy["distance_m"] = round(dist, 2)
            resultados.append(f_copy)

    return {
        "lat": lat,
        "lon": lon,
        "radio_m": radio_m,
        "total": len(resultados),
        "resultados": sorted(resultados, key=lambda x: x["distance]()


