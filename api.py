from fastapi import FastAPI, Query
import requests
import json

app = FastAPI(title="IDE Pergamino API")

DATA_URL = (
    "https://github.com/fedeclerici-oss/ide-pergamino-api/"
    "releases/download/v1.0.0/ide_normalizado.json"
)

datos = []


@app.on_event("startup")
def cargar_datos():
    global datos
    print("⬇️ Descargando JSON desde GitHub Releases...")

    r = requests.get(DATA_URL, timeout=60)
    r.raise_for_status()

    try:
        data = r.json()
    except Exception:
        primeros = r.content[:200]
        raise RuntimeError(
            "❌ El archivo descargado NO es JSON.\n"
            f"Primeros bytes:\n{primeros}"
        )

    if not isinstance(data, list):
        raise RuntimeError("❌ El JSON no es una lista")

    datos = data
    print(f"✅ JSON cargado: {len(datos)} registros")


@app.get("/health")
def health():
    return {
        "status": "ok",
        "registros": len(datos)
    }


@app.get("/buscar")
def buscar(q: str = Query(..., min_length=2)):
    q = q.lower()

    resultados = [
        d for d in datos
        if q in (d.get("nombre") or "").lower()
        or q in (d.get("descripcion") or "").lower()
    ]

    return {
        "query": q,
        "cantidad": len(resultados),
        "resultados": resultados[:20]
    }




