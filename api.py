from fastapi import FastAPI, Query
from typing import List, Optional
import json
import os

app = FastAPI(
    title="IDE Pergamino API",
    description="API contextual para consultas territoriales",
    version="1.0.0"
)

# =========================
# CARGA DE DATOS
# =========================

DATA_PATH = "data/lugares.geojson"  # ajustá si el path es otro

with open(DATA_PATH, "r", encoding="utf-8") as f:
    geojson = json.load(f)

LUGARES = [feature["properties"] for feature in geojson["features"]]

# =========================
# FILTRO DE TIPOS ÚTILES
# =========================

TIPOS_UTILES = [
    "escuela",
    "educacion",
    "salud",
    "hospital",
    "plaza",
    "espacio",
    "obra",
    "municipal",
    "centro",
    "policia",
    "bomberos"
]

def es_lugar_util(lugar: dict) -> bool:
    texto = " ".join([
        str(lugar.get("nombre", "")),
        str(lugar.get("tipo", "")),
        str(lugar.get("subtipo", "")),
        str(lugar.get("descripcion", "")),
        str(lugar.get("capa_origen", ""))
    ]).lower()

    return any(t in texto for t in TIPOS_UTILES)

LUGARES_UTILES = [l for l in LUGARES if es_lugar_util(l)]

# =========================
# ENDPOINT BASE
# =========================

@app.get("/")
def home():
    return {
        "estado": "ok",
        "lugares_totales": len(LUGARES),
        "lugares_utiles": len(LUGARES_UTILES)
    }

# =========================
# NUEVO ENDPOINT CONTEXTUAL
# =========================

@app.get("/buscar_contexto")
def buscar_contexto(
    q: str = Query(..., description="Texto libre: barrio, calle, lugar, institución"),
    limite: int = 10
):
    q = q.lower().strip()
    resultados = []

    for lugar in LUGARES_UTILES:
        score = 0

        campos = {
            "nombre": lugar.get("nombre"),
            "tipo": lugar.get("tipo"),
            "subtipo": lugar.get("subtipo"),
            "descripcion": lugar.get("descripcion"),
            "capa_origen": lugar.get("capa_origen")
        }

        for valor in campos.values():
            if valor and q in str(valor).lower():
                score += 1

        if score > 0:
            resultados.append({
                "nombre": lugar.get("nombre"),
                "tipo": lugar.get("tipo"),
                "subtipo": lugar.get("subtipo"),
                "descripcion": lugar.get("descripcion"),
                "fuente": lugar.get("fuente"),
                "score": score
            })

    resultados = sorted(resultados, key=lambda x: x["score"], reverse=True)

    return {
        "query": q,
        "cantidad_resultados": len(resultados),
        "resultados": resultados[:limite]
    }



