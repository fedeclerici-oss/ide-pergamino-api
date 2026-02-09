from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
import json
import os
import requests
import math

# ================= CONFIG =================

DRIVE_FILE_ID = "1PJvXqycmcOlld23pusWBbx3M4yEuE_To"
DATA_DIR = "data"
DATA_PATH = f"{DATA_DIR}/lugares.geojson"

# =========================================

app = FastAPI(
    title="IDE Pergamino API",
    description="Búsqueda de lugares, escuelas y contexto urbano",
    version="1.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

lugares = []

# ---------- UTILIDADES ----------

def descargar_desde_drive():
    os.makedirs(DATA_DIR, exist_ok=True)
    url = f"https://drive.google.com/uc?id={DRIVE_FILE_ID}"
    r = requests.get(url, stream=True)
    r.raise_for_status()

    with open(DATA_PATH, "wb") as f:
        for chunk in r.iter_content(chunk_size=1024 * 1024):
            if chunk:
                f.write(chunk)

def distancia(lat1, lon1, lat2, lon2):
    return math.sqrt((lat1 - lat2) ** 2 + (lon1 - lon2) ** 2)

# ---------- CARGA INICIAL ----------

@app.on_event("startup")
def cargar_datos():
    global lugares

    if not os.path.exists(DATA_PATH):
        print("⬇️ Descargando GeoJSON desde Google Drive...")
        descargar_desde_drive()

    with open(DATA_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    lugares = data.get("features", [])
    print(f"✅ Lugares cargados en memoria: {len(lugares)}")

# ---------- ENDPOINTS ----------

@app.get("/")
def home():
    return {
        "status": "ok",
        "total_lugares": len(lugares)
    }

@app.get("/buscar")
def buscar(
    q: str = Query(..., description="Texto libre: escuela, plaza, calle"),
    lat: float | None = None,
    lon: float | None = None,
):
    q = q.lower()
    resultados = []

    for f in lugares:
        props = f.get("properties", {})

        nombre = str(props.get("nombre", "")).lower()
        tipo = str(props.get("tipo", "")).lower()

        if q in nombre or q in tipo:
            item = {
                "id": props.get("id"),
                "nombre": props.get("nombre"),
                "tipo": props.get("tipo"),
                "lat": props.get("lat"),
                "lon": props.get("lon"),
                "fuente": props.get("fuente"),
            }

            if lat and lon and props.get("lat") and props.get("lon"):
                item["distancia"] = distancia(
                    lat, lon, props["lat"], props["lon"]
                )

            resultados.append(item)

    if not resultados:
        return {
            "mensaje": "No se encontró coincidencia exacta",
            "sugerencia": "Probá con otros términos (ej: escuela, plaza, calle)"
        }

    resultados = sorted(resultados, key=lambda x: x.get("distancia", 0))
    return resultados[:10]

@app.get("/debug")
def debug():
    if not lugares:
        return {"error": "No hay datos cargados"}

    ejemplo = lugares[0].get("properties", {})
    return {
        "tipo": str(type(lugares)),
        "cantidad": len(lugares),
        "ejemplo": ejemplo
    }





