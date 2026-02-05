from fastapi import FastAPI
from pydantic import BaseModel
from geopy.distance import geodesic
import json
import os

app = FastAPI(title="IDE Pergamino API")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_PATH = os.path.join(BASE_DIR, "ide_normalizado.json")

with open(DATA_PATH, "r", encoding="utf-8") as f:
    DATA = json.load(f)

class Consulta(BaseModel):
    lat: float
    lon: float
    radio_m: int = 300

def consultar_zona(lat, lon, radio_m):
    resultados = []

    for item in DATA:
        lat2 = item.get("lat")
        lon2 = item.get("lon")

        if lat2 is None or lon2 is None:
            continue
        if not (-90 <= lat2 <= 90 and -180 <= lon2 <= 180):
            continue

        d = geodesic((lat, lon), (lat2, lon2)).meters
        if d <= radio_m:
            item_copy = item.copy()
            item_copy["distancia_m"] = round(d)
            resultados.append(item_copy)

    return resultados

@app.post("/consultar_zona")
def consultar(q: Consulta):
    data = consultar_zona(q.lat, q.lon, q.radio_m)

    resumen = {}
    for i in data:
        resumen[i["tipo"]] = resumen.get(i["tipo"], 0) + 1

    return {
        "total": len(data),
        "resumen": resumen,
        "items": data[:20]
    }
