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
        print("⬇️ Descargando GeoJSON...")
        r = requests.get(DATA_URL, timeout=60)
        r.raise_for_status()
        with open(DATA_PATH, "wb") as f:
            f.write(r.content)

    with open(DATA_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    lugares = data if isinstance(data, list) else data.get("features", [])
    print(f"✅ {len(lugares)} lugares cargados")


# =========================
# INTERPRETAR PREGUNTA
# =========================

@app.get("/interpretar_pregunta")
def interpretar_pregunta(pregunta: str):
    p = pregunta.lower()

    categorias = {
        "escuela": ["escuela", "colegio", "primaria", "secundaria"],
        "hospital": ["hospital", "clinica", "caps", "salita"],
        "plaza": ["plaza", "parque"],
        "calle": ["calle", "avenida", "av", "ruta"]
    }

    categoria_detectada = None
    for cat, palabras in categorias.items():
        if any(palabra in p for palabra in palabras):
            categoria_detectada = cat
            break

    usa_cercania = any(x in p for x in ["cerca", "cercano", "por acá", "alrededor"])
    pregunta_ubicacion = any(x in p for x in ["donde", "hay", "queda"])

    return {
        "intencion": "buscar_lugar" if categoria_detectada else "desconocida",
        "categoria": categoria_detectada,
        "usa_cercania": usa_cercania,
        "usa_ubicacion": pregunta_ubicacion
    }


# =========================
# BOT CONVERSACIONAL
# =========================

@app.get("/bot")
def bot(
    pregunta: str,
    lat: float | None = None,
    lon: float | None = None,
):
    interpretacion = interpretar_pregunta(pregunta)

    if interpretacion["intencion"] != "buscar_lugar":
        return {
            "respuesta": "No estoy seguro de qué estás buscando. Probá preguntarme por lugares de la ciudad.",
            "datos": []
        }

    q = interpretacion["categoria"]

    candidatos = [l for l in lugares if texto_match(l, q)]

    if not candidatos:
        return {
            "respuesta": f"No encontré {q}, pero puedo intentar con otra cosa si querés.",
            "datos": []
        }

    if lat is None or lon is None:
        return {
            "respuesta": f"Encontré {len(candidatos)} {q}. Si me pasás tu ubicación te digo cuál te queda más cerca.",
            "datos": candidatos[:5]
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

    cercanos = enriquecidos[:3]

    if not cercanos:
        return {
            "respuesta": f"Hay {q}, pero no tengo datos de distancia confiables.",
            "datos": candidatos[:3]
        }

    texto = f"Encontré {len(cercanos)} {q} cerca tuyo. El más próximo está a {cercanos[0]['distancia_m']} metros."

    return {
        "respuesta": texto,
        "datos": cercanos
    }


# =========================
# HEALTH
# =========================

@app.get("/")
def health():
    return {
        "status": "ok",
        "lugares": len(lugares)
    }

