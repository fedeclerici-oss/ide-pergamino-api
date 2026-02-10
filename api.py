from fastapi import FastAPI, Query
import json
import math
import requests
from typing import Optional

app = FastAPI(
    title="IDE Pergamino API",
    description="Búsqueda contextual de lugares, calles y servicios",
    version="1.0.0",
)

# =========================
# CONFIG
# =========================

GEOJSON_URL = (
    "https://github.com/fedeclerici-oss/ide-pergamino-api/"
    "releases/download/v1.0.0/ide_normalizado.json"
)

lugares = []


# =========================
# UTILIDADES
# =========================

def haversine(lat1, lon1, lat2, lon2):
    R = 6371  # km
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)

    a = (
        math.sin(dphi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    )
    return 2 * R * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def normalizar(texto: str) -> str:
    return texto.lower().strip()


# =========================
# STARTUP
# =========================

@app.on_event("startup")
def cargar_datos():
    global lugares
    print("⬇️ Descargando GeoJSON desde GitHub Release...")

    resp = requests.get(GEOJSON_URL, timeout=60)
    resp.raise_for_status()

    data = resp.json()

    if "features" not in data:
        raise RuntimeError("❌ El archivo no es un GeoJSON válido")

    lugares = []

    for f in data["features"]:
        props = f.get("properties", {})
        geom = f.get("geometry", {})

        if not geom or "coordinates" not in geom:
            continue

        lon, lat = geom["coordinates"]

        lugares.append({
            "id": props.get("id"),
            "tipo": props.get("tipo"),
            "subtipo": props.get("subtipo"),
            "nombre": props.get("nombre"),
            "descripcion": props.get("descripcion"),
            "lat": lat,
            "lon": lon,
            "fuente": props.get("fuente"),
            "capa_origen": props.get("capa_origen"),
        })

    print(f"✅ Datos cargados: {len(lugares)} registros")


# =========================
# ENDPOINTS
# =========================

@app.get("/")
def home():
    return {
        "status": "ok",
        "lugares_cargados": len(lugares)
    }


@app.get("/buscar")
def buscar(
    q: str = Query(..., description="Texto a buscar"),
    limit: int = 10
):
    qn = normalizar(q)

    resultados = [
        l for l in lugares
        if l["nombre"] and qn in normalizar(l["nombre"])
    ]

    return {
        "cantidad": len(resultados),
        "resultados": resultados[:limit]
    }


@app.get("/buscar_contexto")
def buscar_contexto(
    q: str = Query(..., description="Texto a buscar"),
    lat: Optional[float] = None,
    lon: Optional[float] = None,
    limit: int = 5
):
    qn = normalizar(q)

    candidatos = [
        l for l in lugares
        if l["nombre"] and qn in normalizar(l["nombre"])
    ]

    # Si hay coordenadas, ordenamos por cercanía real
    if lat is not None and lon is not None:
        for l in candidatos:
            l["distancia_km"] = haversine(
                lat, lon, l["lat"], l["lon"]
            )

        candidatos.sort(key=lambda x: x["distancia_km"])
    else:
        # Si no hay coords → igual respondemos
        for l in candidatos:
            l["distancia_km"] = None

    return {
        "cantidad": len(candidatos),
        "resultados": candidatos[:limit]
    }

