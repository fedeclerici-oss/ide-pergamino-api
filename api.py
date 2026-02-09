import os
import json
import requests
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware

# =========================
# CONFIG
# =========================

DATA_DIR = "data"
DATA_PATH = os.path.join(DATA_DIR, "lugares_v3.geojson")



# Link DIRECTO de descarga desde Drive (MUY IMPORTANTE)
DRIVE_URL = "https://drive.google.com/uc?export=download&id=1PJvXqycmcOlld23pusWBbx3M4yEuE_To"

lugares = []

# =========================
# APP
# =========================

app = FastAPI(
    title="IDE Pergamino API",
    description="Búsqueda flexible de lugares (texto + contexto)",
    version="1.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# =========================
# UTILIDADES
# =========================

def descargar_desde_drive():
    response = requests.get(DRIVE_DOWNLOAD_URL, timeout=120)
    response.raise_for_status()

    with open(DATA_PATH, "wb") as f:
        f.write(response.content)

def normalizar(texto: str) -> str:
    return texto.lower().strip()

# =========================
# STARTUP
# =========================

@app.on_event("startup")
def cargar_datos():
    global lugares

    os.makedirs(DATA_DIR, exist_ok=True)

    necesita_descarga = True

    if os.path.exists(DATA_PATH):
        size = os.path.getsize(DATA_PATH)
        print(f"📦 Archivo existente: {size} bytes")
        if size > 10_000:
            necesita_descarga = False
        else:
            print("⚠️ Archivo muy chico, se vuelve a descargar")

    if necesita_descarga:
        print("⬇️ Descargando GeoJSON desde Google Drive...")
        descargar_desde_drive()

    try:
        with open(DATA_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        with open(DATA_PATH, "rb") as f:
            inicio = f.read(200)
        raise RuntimeError(
            f"❌ Error leyendo GeoJSON.\n"
            f"Primeros bytes del archivo:\n{inicio}"
        ) from e

    lugares = data.get("features", [])
    print(f"✅ Lugares cargados correctamente: {len(lugares)}")

# =========================
# ENDPOINTS
# =========================

@app.get("/")
def root():
    return {
        "status": "ok",
        "lugares_cargados": len(lugares)
    }

@app.get("/debug")
def debug():
    return {
        "tipo": str(type(lugares)),
        "cantidad": len(lugares),
        "ejemplo": lugares[0]["properties"] if lugares else None
    }

@app.get("/buscar")
def buscar(
    q: str = Query(..., description="Texto a buscar"),
    limit: int = 10
):
    """
    Búsqueda flexible:
    - primero exacta
    - si no hay, busca por contexto
    """

    q_norm = normalizar(q)
    resultados_exactos = []
    resultados_contexto = []

    for f in lugares:
        props = f.get("properties", {})
        nombre = normalizar(props.get("nombre", ""))
        descripcion = normalizar(props.get("descripcion", "") or "")
        tipo = normalizar(props.get("tipo", "") or "")
        subtipo = normalizar(props.get("subtipo", "") or "")

        texto_completo = f"{nombre} {descripcion} {tipo} {subtipo}"

        if q_norm in nombre:
            resultados_exactos.append(f)
        elif q_norm in texto_completo:
            resultados_contexto.append(f)

    resultados = resultados_exactos or resultados_contexto

    return {
        "query": q,
        "total_exactos": len(resultados_exactos),
        "total_contexto": len(resultados_contexto),
        "devueltos": len(resultados[:limit]),
        "resultados": resultados[:limit]
    }

# =========================
# PARA EJECUTAR LOCAL
# =========================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api:app", host="0.0.0.0", port=8000, reload=True)



