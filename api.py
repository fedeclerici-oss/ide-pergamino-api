from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
import json
import math
import os
import requests

app = FastAPI(title="IDE Pergamino API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# =========================
# CONFIG
# =========================

DATA_URL = "https://github.com/fedeclerici-oss/ide-pergamino-api/releases/download/v1.0.0/ide_normalizado.json"
DATA_PATH = "ide_normalizado.json"

lugares = []

# =========================
# UTILIDADES
# =========================

def distancia_metros(lat1, lon1, lat2, lon2):
    R = 6371000
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)

    a = (
        math.sin(dphi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    )
    return 2 * R * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def texto_match(lugar, q):
    q = q.lower()
    for campo in ["nombre", "tipo", "subtipo", "descripcion", "capa_origen"]:
        valor = lugar.get(campo)
        if valor and q in str(valor).lower():
            return True
    return False


# =========================
# CARGA DE DATOS
# =========================

@app.on_event("startup")
def cargar_datos():
    global lugares

    if not os.path.exists(DATA_PATH):
        print("⬇️ Descargando GeoJSON desde GitHub Release...")
        r = requests.get(DATA_URL, timeout=60)
        r.raise_for_status()
        with open(DATA_PATH, "wb") as f:
            f.write(r.content)

    with open(DATA_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    lugares = data if isinstance(data, list) else data.get("features", [])
    print(f"✅ {len(lugares)} lugares cargados")


# =========================
# ENDPOINTS
# =========================

@app.get("/")
def health():
    return {
        "status": "ok",
        "lugares_cargados": len(lugares)
    }


@app.get("/buscar")
def buscar(
    q: str = Query(..., min_length=2),
    limit: int = 10
):
    resultados = [
        l for l in lugares if texto_match(l, q)
    ][:limit]

    return {
        "query": q,
        "cantidad": len(resultados),
        "resultados": resultados
    }


@app.get("/buscar_contexto")
def buscar_contexto(
    q: str = Query(..., min_length=2),
    lat: float | None = None,
    lon: float | None = None,
    limit: int = 10
):
    candidatos = [l for l in lugares if texto_match(l, q)]

    if not candidatos:
        return {
            "mensaje": f"No encontré resultados para '{q}', pero puedo buscar algo parecido si querés.",
            "estrategia": "sin_resultados",
            "resultados": []
        }

    if lat is None or lon is None:
        return {
            "mensaje": f"Encontré {len(candidatos)} resultados para '{q}'.",
            "estrategia": "texto_sin_ubicacion",
            "resultados": candidatos[:limit]
        }

    enriquecidos = []
    for l in candidatos:
        if l.get("lat") is None or l.get("lon") is None:
            continue
        d = distancia_metros(lat, lon, l["lat"], l["lon"])
        l2 = l.copy()
        l2["distancia_m"] = round(d, 1)
        enriquecidos.append(l2)

    enriquecidos.sort(key=lambda x: x["distancia_m"])

    cerca_300 = [l for l in enriquecidos if l["distancia_m"] <= 300]
    cerca_1000 = [l for l in enriquecidos if 300 < l["distancia_m"] <= 1000]

    if cerca_300:
        return {
            "mensaje": f"Encontré {len(cerca_300)} resultados a menos de 300 metros.",
            "estrategia": "cercania_300m",
            "resultados": cerca_300[:limit]
        }

    if cerca_1000:
        return {
            "mensaje": f"No hay resultados inmediatos, pero encontré {len(cerca_1000)} cerca tuyo (hasta 1 km).",
            "estrategia": "cercania_1000m",
            "resultados": cerca_1000[:limit]
        }

    return {
        "mensaje": "No encontré nada cerca, pero te muestro las coincidencias más relevantes.",
        "estrategia": "fallback_distancia",
        "resultados": enriquecidos[:limit]
    }
