from fastapi import FastAPI, Query
import requests
import math

app = FastAPI(
    title="IDE Pergamino API",
    description="API de consulta geográfica IDE Pergamino",
    version="1.0"
)

# =========================
# CONFIG
# =========================

DATA_URL = "https://github.com/fedeclerici-oss/ide-pergamino-api/releases/download/v1-data/ide_normalizado.json"

LUGARES = []


# =========================
# UTILIDADES
# =========================

def distancia_m(lat1, lon1, lat2, lon2):
    """
    Distancia aproximada en metros (Haversine)
    """
    R = 6371000  # radio tierra en metros
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)

    a = (
        math.sin(dphi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    )
    return 2 * R * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def cargar_datos_remotos():
    global LUGARES
    print("⬇️ Descargando ide_normalizado.json...")

    r = requests.get(DATA_URL)
    r.raise_for_status()

    data = r.json()

    # ⚠️ TU JSON ES UNA LISTA, NO UN DICCIONARIO
    if isinstance(data, list):
        LUGARES = data
    else:
        LUGARES = data.get("features", [])

    print(f"✅ Lugares cargados: {len(LUGARES)}")


# =========================
# STARTUP
# =========================

cargar_datos_remotos()


# =========================
# ENDPOINTS
# =========================

@app.get("/")
def root():
    return {
        "status": "ok",
        "lugares_cargados": len(LUGARES)
    }


@app.get("/debug/lugares")
def debug_lugares():
    return {
        "tipo": str(type(LUGARES)),
        "cantidad": len(LUGARES),
        "ejemplo": LUGARES[0] if LUGARES else None
    }


@app.get("/buscar_texto")
def buscar_texto(
    q: str = Query(..., description="Texto a buscar, ej: escuela, plaza")
):
    texto = q.lower()
    resultados = []

    for l in LUGARES:
        blob = " ".join([
            str(l.get("nombre", "")),
            str(l.get("tipo", "")),
            str(l.get("categoria", "")),
            str(l.get("descripcion", ""))
        ]).lower()

        if texto in blob:
            resultados.append(l)

    return {
        "query": q,
        "resultados": len(resultados),
        "lugares": resultados[:50]  # límite
    }


@app.get("/buscar_cerca")
def buscar_cerca(
    lat: float,
    lon: float,
    radio_m: int = 300
):
    encontrados = []

    for l in LUGARES:
        lat2 = l.get("lat")
        lon2 = l.get("lon")

        if lat2 is None or lon2 is None:
            continue

        d = distancia_m(lat, lon, lat2, lon2)

        if d <= radio_m:
            l2 = l.copy()
            l2["distancia_m"] = round(d, 1)
            encontrados.append(l2)

    encontrados.sort(key=lambda x: x["distancia_m"])

    return {
        "lat": lat,
        "lon": lon,
        "radio_m": radio_m,
        "resultados": len(encontrados),
        "lugares": encontrados[:50]
    }



