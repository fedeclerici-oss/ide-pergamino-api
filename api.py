from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional
import json
import math
import os
import requests
import time
from openai import OpenAI

app = FastAPI(title="IDE Pergamino BOT API")

# =========================
# CORS
# =========================
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

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
client = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None

lugares = []
memoria = {}
MEMORIA_TTL = 600


# =========================
# UTILIDADES
# =========================
def distancia_metros(lat1, lon1, lat2, lon2):
    R = 6371000
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlambda/2)**2
    return 2 * R * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def limpiar_memoria():
    ahora = time.time()
    for k in list(memoria.keys()):
        if ahora - memoria[k]["ts"] > MEMORIA_TTL:
            del memoria[k]


def normalizar(texto):
    return texto.lower().strip().replace("á","a").replace("é","e").replace("í","i").replace("ó","o").replace("ú","u")


def responder_con_ia(pregunta):
    if not client:
        return "No tengo IA configurada."

    try:
        completion = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "Sos un asistente municipal de Pergamino. Respondé claro, breve y útil."},
                {"role": "user", "content": pregunta}
            ]
        )
        return completion.choices[0].message.content
    except:
        return "No pude procesar la consulta en este momento."


def buscar_lugares_por_texto(texto):
    texto = normalizar(texto)

    resultados = []
    for l in lugares:
        nombre = normalizar(str(l.get("nombre", "")))
        tipo = normalizar(str(l.get("tipo", "")))

        if texto in nombre or texto in tipo:
            resultados.append(l)

    return resultados


def responder_donde(pregunta, lat=None, lon=None):
    texto = normalizar(pregunta)

    # extraer palabra clave después de "donde"
    palabras = texto.split()
    if "donde" in palabras:
        idx = palabras.index("donde")
        clave = " ".join(palabras[idx+1:])
    else:
        clave = texto

    candidatos = buscar_lugares_por_texto(clave)

    if not candidatos:
        return None

    # si hay ubicación → ordenar por distancia
    if lat is not None and lon is not None:
        enriquecidos = []
        for l in candidatos:
            if l.get("lat") and l.get("lon"):
                d = distancia_metros(lat, lon, l["lat"], l["lon"])
                l2 = l.copy()
                l2["distancia_m"] = round(d, 1)
                enriquecidos.append(l2)

        enriquecidos.sort(key=lambda x: x["distancia_m"])

        if enriquecidos:
            top = enriquecidos[0]
            link = f"https://www.google.com/maps/search/?api=1&query={top['lat']},{top['lon']}"
            return f"{top.get('nombre','Sin nombre')} está a {top['distancia_m']} metros.\n{link}"

    # sin ubicación → devolver primeros 3
    texto_respuesta = ""
    for l in candidatos[:3]:
        if l.get("lat") and l.get("lon"):
            link = f"https://www.google.com/maps/search/?api=1&query={l['lat']},{l['lon']}"
            texto_respuesta += f"{l.get('nombre','Sin nombre')}\n{link}\n\n"

    return texto_respuesta.strip() if texto_respuesta else None


def resumen_zona(lat, lon, radio=300):
    resumen = {}

    for l in lugares:
        if l.get("lat") and l.get("lon"):
            d = distancia_metros(lat, lon, l["lat"], l["lon"])
            if d <= radio:
                capa = l.get("capa_origen", "otros")
                resumen[capa] = resumen.get(capa, 0) + 1

    return resumen


# =========================
# CARGA DATOS
# =========================
@app.on_event("startup")
def cargar_datos():
    global lugares

    if not os.path.exists(DATA_PATH):
        r = requests.get(DATA_URL, timeout=60)
        r.raise_for_status()
        with open(DATA_PATH, "wb") as f:
            f.write(r.content)

    with open(DATA_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    lugares = data if isinstance(data, list) else data.get("features", [])
    print(f"✅ {len(lugares)} lugares cargados")


# =========================
# BOT
# =========================
@app.get("/bot")
def bot(
    session_id: str,
    pregunta: str,
    lat: Optional[float] = None,
    lon: Optional[float] = None,
):
    limpiar_memoria()

    mem = memoria.get(session_id, {})

    if lat is None:
        lat = mem.get("lat")
    if lon is None:
        lon = mem.get("lon")

    memoria[session_id] = {
        "lat": lat,
        "lon": lon,
        "ts": time.time()
    }

    pregunta_norm = normalizar(pregunta)

    # =========================
    # CONSULTA ZONA
    # =========================
    if lat is not None and lon is not None and any(x in pregunta_norm for x in ["zona","alrededor","que hay"]):
        resumen = resumen_zona(lat, lon, radio=300)

        if not resumen:
            return {"respuesta": "No encontré infraestructura cercana en un radio de 300 metros.", "datos": []}

        texto = "En un radio de 300 metros encontré:\n\n"
        for capa, cantidad in sorted(resumen.items(), key=lambda x: x[1], reverse=True):
            texto += f"- {cantidad} registros de {capa}\n"

        return {"respuesta": texto, "datos": []}

    # =========================
    # PREGUNTAS DE UBICACIÓN
    # =========================
    if pregunta_norm.startswith("donde"):
        respuesta = responder_donde(pregunta, lat, lon)
        if respuesta:
            return {"respuesta": respuesta, "datos": []}

    # =========================
    # BUSQUEDA GENERAL
    # =========================
    candidatos = buscar_lugares_por_texto(pregunta)

    if candidatos:
        texto = ""
        for l in candidatos[:3]:
            if l.get("lat") and l.get("lon"):
                link = f"https://www.google.com/maps/search/?api=1&query={l['lat']},{l['lon']}"
                texto += f"{l.get('nombre','Sin nombre')}\n{link}\n\n"

        if texto:
            return {"respuesta": texto.strip(), "datos": candidatos[:3]}

    # =========================
    # FALLBACK A IA
    # =========================
    respuesta_ia = responder_con_ia(pregunta)
    return {"respuesta": respuesta_ia, "datos": []}


# =========================
# TELEGRAM WEBHOOK
# =========================
@app.post("/telegram")
async def telegram_webhook(request: Request):
    data = await request.json()

    if "message" in data:
        chat_id = data["message"]["chat"]["id"]

        if "location" in data["message"]:
            lat = data["message"]["location"]["latitude"]
            lon = data["message"]["location"]["longitude"]

            resultado = bot(
                session_id=str(chat_id),
                pregunta="zona",
                lat=lat,
                lon=lon
            )
            respuesta = resultado["respuesta"]

        else:
            text = data["message"].get("text", "")
            resultado = bot(
                session_id=str(chat_id),
                pregunta=text
            )
            respuesta = resultado["respuesta"]

        requests.post(
            f"https://api.telegram.org/bot{os.environ.get('TELEGRAM_TOKEN')}/sendMessage",
            json={
                "chat_id": chat_id,
                "text": respuesta,
                "disable_web_page_preview": True
            }
        )

    return {"ok": True}
