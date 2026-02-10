from fastapi import FastAPI, Query
import json
import requests
import unicodedata
from pathlib import Path

app = FastAPI(title="IDE Pergamino API")

DATA_URL = "https://github.com/fedeclerici-oss/ide-pergamino-api/releases/download/v1.0.0/ide_normalizado.json"
DATA_PATH = Path("data.json")

DATA = []
INDEX = []

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
        })

    print(f"✅ Cargados {len(INDEX)} registros")


@app.get("/buscar")
def buscar(q: str = Query(...), limit: int = 10):
    qn = normalizar(q)
    intencion = detectar_intencion(qn)

    resultados = []

    for item in INDEX:
        score = 0

        if qn in item["texto"]:
            score += 3

        if intencion and intencion in item["texto"]:
            score += 2

        if score > 0:
            resultados.append((score, item["raw"]))

    resultados.sort(key=lambda x: x[0], reverse=True)

    if not resultados:
        return {
            "query": q,
            "mensaje": "No hubo match exacto, se devuelven resultados generales",
            "resultados": DATA[:limit]
        }

    return {
        "query": q,
        "intencion": intencion,
        "total": len(resultados),
        "resultados": [r[1] for r in resultados[:limit]]
    }




