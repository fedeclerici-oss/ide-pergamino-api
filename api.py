from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path
import json

app = FastAPI(
    title="API Lugares",
    description="API para servir lugares desde un GeoJSON",
    version="1.0.0",
)

# CORS (abrimos todo por ahora, después se ajusta)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---- RUTA ABSOLUTA AL ARCHIVO ----
BASE_DIR = Path(__file__).resolve().parent
DATA_PATH = BASE_DIR / "data" / "lugares.geojson"

# ---- CARGA DEL GEOJSON ----
try:
    with open(DATA_PATH, "r", encoding="utf-8") as f:
        GEOJSON_DATA = json.load(f)
except FileNotFoundError:
    raise RuntimeError(f"No se encontró el archivo: {DATA_PATH}")

# ---- ENDPOINTS ----

@app.get("/")
def root():
    return {
        "status": "ok",
        "message": "API de Lugares funcionando 🚀"
    }

@app.get("/lugares")
def get_lugares():
    return GEOJSON_DATA

@app.get("/lugares/{lugar_id}")
def get_lugar_by_id(lugar_id: str):
    features = GEOJSON_DATA.get("features", [])

    for feature in features:
        props = feature.get("properties", {})
        if str(props.get("id")) == lugar_id:
            return feature

    raise HTTPException(status_code=404, detail="Lugar no encontrado")





