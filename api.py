from fastapi import FastAPI, HTTPException
import requests
import json
import os

app = FastAPI(title="IDE Pergamino API")

# =========================
# Config
# =========================
GEOJSON_URL = "https://github.com/fedeclerici-oss/ide-pergamino-api/releases/download/v1.0.0/ide_normalizado.json"
LOCAL_FILE = "data.json"

data_cache = None


# =========================
# Startup
# =========================
@app.on_event("startup")
def cargar_datos():
    global data_cache

    try:
        print("⬇️ Descargando JSON desde GitHub Releases...")
        r = requests.get(GEOJSON_URL, timeout=60)
        r.raise_for_status()

        # 🔴 Protección clave: GitHub ok, pero por las dudas
        if r.text.lstrip().startswith("<!DOCTYPE html"):
            raise RuntimeError("El archivo descargado es HTML, no JSON")

        with open(LOCAL_FILE, "wb") as f:
            f.write(r.content)

        with open(LOCAL_FILE, "r", encoding="utf-8") as f:
            data_cache = json.load(f)

        print("✅ JSON cargado correctamente")

    except Exception as e:
        print("❌ Error leyendo JSON")
        raise RuntimeError(f"Error cargando datos: {e}")


# =========================
# Endpoints
# =========================
@app.get("/")
def root():
    return {
        "status": "ok",
        "features": len(data_cache.get("features", [])) if data_cache else 0
    }


@app.get("/features")
def get_features(limit: int = 100):
    if not data_cache:
        raise HTTPException(status_code=500, detail="Datos no cargados")

    return data_cache.get("features", [])[:limit]


@app.get("/feature/{index}")
def get_feature(index: int):
    features = data_cache.get("features", [])

    if index < 0 or index >= len(features):
        raise HTTPException(status_code=404, detail="Índice fuera de rango")

    return features[index]




