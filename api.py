from fastapi import FastAPI, Query
import json
import requests
import unicodedata
from pathlib import Path
from math import radians, cos, sin, asin, sqrt
from pyproj import Transformer

app = FastAPI(title="IDE Pergamino API")

DATA_URL = "https://github.com/fedeclerici-oss/ide-pergamino-api/releases/download/v1.0.0/ide_normalizado.json"
DATA_PATH = Path("data.json")

DATA = []
INDEX = []

# POSGAR / Gauss Kruger → WGS84
transformer = Transformer.from_crs("EPSG:22185", "EPSG:4326", always_xy=True)

INTENCIONES = {
    "escuela": ["escuela", "colegio", "educacion", "jardin"],
    "salud": ["hospital", "salita", "caps"],
    "espacio_verde": ["plaza", "parque"],
    "calle": ["calle", "avenida"]
}


def normalizar(txt: str) -> str:
    if not txt:
        return ""
    txt = unicodedata.normalize("NFKD", txt).encode("ascii", "ignore").decode("utf-8")
    return txt.lower()


def detectar_intencion(q: str):
    for tipo, palabras in INTENCIONES.items():
        for p in palabras:
            if p in q:
                return tipo
    return None


def haversine(lat1, lon1, lat2, lon2):
    R = 6371  # km
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
    return 2 * R * asin(sqrt(a))


@app.on_event("startup")
def cargar_datos():
    global DATA, INDEX

    if not DATA_PATH.exists():
        r = requests.get(DATA_URL, timeout=60)
        r.raise_for_status()
        DATA_PATH.write_bytes(r.content)

    DATA = json.loads(DATA_PATH.read_text(encoding="utf-8"))

    INDEX = []

    for item in DATA:
        lat_p = item.get("lat")
        lon_p = item.get("lon")

        if lat_p and lon_p:
            lon_w, lat_w = transformer.transform(lon_p, lat_p)
        else:
            lat_w = lon_w = None

        texto = " ".join([
            item.get("nombre", ""),
            item.get("descripcion", ""),
            item.get("tipo", ""),
            item.get("subtipo", ""),
            item.get("capa_origen", "")
        ])

        INDEX.append({
            "raw": item,
            "texto": normalizar(texto),
            "tipo": normalizar(item.get("tipo", "")),
            "lat": lat_w,
            "lon": lon_w
        })

    print(f"✅ Cargados {len(INDEX)} registros con coordenadas reales")


@app.get("/buscar")
def buscar(
    q: str = Query(...),
    lat: float | None = None,
    lon: float | None = None,
    limit: int = 10
):
    qn = normalizar(q)
    intencion = detectar_intencion(qn)

    resultados = []

    for item in INDEX:
        score = 0

        if qn in item["texto"]:
            score += 3

        if intencion and intencion in item["texto"]:
            score += 2

        distancia = None
        if lat and lon and item["lat"] and item["lon"]:
            distancia = haversine(lat, lon, item["lat"], item["lon"])
            score += max(0, 5 - distancia)  # más cerca = más score

        if score > 0:
            resultados.append({
                "score": score,
                "distancia_km": round(distancia, 2) if distancia else None,
                "data": item["raw"]
            })

    resultados.sort(key=lambda x: (x["distancia_km"] is not None, -x["score"], x["distancia_km"] or 999))

    if not resultados:
        return {
            "query": q,
            "mensaje": "Sin coincidencias claras, resultados generales",
            "resultados": DATA[:limit]
        }

    return {
        "query": q,
        "intencion": intencion,
        "total": len(resultados),
        "resultados": resultados[:limit]
    }


