from fastapi import FastAPI
import requests
from geopy.distance import geodesic

app = FastAPI(
    title="IDE Pergamino API",
    version="1.0"
)

# =========================
# CONFIG
# =========================

DATA_URL = (
    "https://github.com/fedeclerici-oss/"
    "ide-pergamino-api/releases/download/"
    "v1-data/ide_normalizado.json"
)

DATA = []
FEATURES = []

# =========================
# CARGA DE DATOS REMOTOS
# =========================

def cargar_datos_remotos():
    global DATA, FEATURES

    print("⬇️ Descargando ide_normalizado.json...")
    r = requests.get(DATA_URL, timeout=60)
    r.raise_for_status()

    DATA = r.json()
    FEATURES = DATA.get("features", [])

    print(f"✅ Datos cargados: {len(FEATURES)} features")


cargar_datos_remotos()

# =========================
# HELPERS
# =========================

def contiene_texto(feature, texto):
    texto = texto.lower()
    props = feature.get("properties", {})
    return any(texto in str(v).lower() for v in props.values())


# =========================
# ENDPOINTS
# =========================

@app.get("/")
def root():
    return {
        "status": "ok",
        "features": len(FEATURES)
    }


@app.get("/buscar_texto")
def buscar_texto(q: str, limit: int = 20):
    resultados = []

    for f in FEATURES:
        if contiene_texto(f, q):
            resultados.append(f)

    return resultados[:limit]


@app.get("/buscar_cerca")
def buscar_cerca(
    lat: float,
    lon: float,
    radio_km: float = 1.0,
    limit: int = 20
):
    encontrados = []

    for f in FEATURES:
        geom = f.get("geometry", {})
        if geom.get("type") != "Point":
            continue

        lon_f, lat_f = geom["coordinates"]

        try:
            d = geodesic((lat, lon), (lat_f, lon_f)).km
        except Exception:
            continue

        if d <= radio_km:
            f_out = f.copy()
            f_out["distancia_km"] = round(d, 3)
            encontrados.append(f_out)

    encontrados.sort(key=lambda x: x["distancia_km"])
    return encontrados[:limit]

