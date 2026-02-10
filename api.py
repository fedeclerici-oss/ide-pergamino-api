from fastapi import FastAPI, Query, Request
from fastapi.middleware.cors import CORSMiddleware
import json, math, os, requests, time
from typing import Optional

# =========================
# APP
# =========================

app = FastAPI(title="IDE Pergamino BOT API")

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

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
TELEGRAM_API = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"

lugares = []

# memoria simple por sesión
memoria = {}
MEMORIA_TTL = 300  # segundos

# =========================
# UTILIDADES
# =========================

def distancia_metros(lat1, lon1, lat2, lon2):
    R = 6371000
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlambda / 2)**2
    return 2 * R * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def texto_match(lugar, q):
    q = q.lower()
    for campo in ["nombre", "tipo", "subtipo", "descripcion", "capa_origen"]:
        valor = lugar.get(campo)
        if valor and q in str(valor).lower():
            return True
    return False


def limpiar_memoria():
    ahora = time.time()
    for k in list(memoria.keys()):
        if ahora - memoria[k]["ts"] > MEMORIA_TTL:
            del memoria[k]


def send_telegram(chat_id: int, text: str):
    if not TELEGRAM_TOKEN:
        return
    requests.post(
        f"{TELEGRAM_API}/sendMessage",
        json={"chat_id": chat_id, "text": text},
        timeout=10
    )

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
# INTERPRETAR PREGUNTA
# =========================

def interpretar(pregunta: str):
    p = pregunta.lower()

    categorias = {
        "escuela": ["escuela", "colegio", "primaria", "secundaria"],
        "hospital": ["hospital", "clinica", "caps", "salita"],
        "plaza": ["plaza", "parque"],
        "calle": ["calle", "avenida", "av"]
    }

    categoria = None
    for c, palabras in categorias.items():
        if any(w in p for w in palabras):
            categoria = c
            break

    usa_cercania = any(x in p for x in ["cerca", "cercano", "por acá", "alrededor"])
    return categoria, usa_cercania

# =========================
# BOT (CORE)
# =========================

def responder_bot(session_id: str, pregunta: str, lat=None, lon=None):
    limpiar_memoria()

    categoria, usa_cercania = interpretar(pregunta)
    mem = memoria.get(session_id, {})

    if categoria is None:
        categoria = mem.get("categoria")

    if lat is None or lon is None:
        lat = mem.get("lat")
        lon = mem.get("lon")

    if categoria is None:
        return "¿Qué tipo de lugar estás buscando?"

    memoria[session_id] = {
        "categoria": categoria,
        "lat": lat,
        "lon": lon,
        "ts": time.time()
    }

    candidatos = [l for l in lugares if texto_match(l, categoria)]

    if not candidatos:
        return f"No encontré {categoria}. Probá con otro tipo de lugar."

    if lat is None or lon is None:
        return f"Encontré {len(candidatos)} {categoria}. Si me decís dónde estás, te digo el más cercano."

    enriquecidos = []
    for l in candidatos:
        if l.get("lat") is None or l.get("lon") is None:
            continue
        d = distancia_metros(lat, lon, l["lat"], l["lon"])
        enriquecidos.append((d, l))

    if not enriquecidos:
        return "No tengo coordenadas para calcular cercanía."

    enriquecidos.sort(key=lambda x: x[0])
    d, lugar = enriquecidos[0]

    nombre = lugar.get("nombre", "El lugar")
    return f"{nombre} está a {round(d)} metros de donde estás."

# =========================
# ENDPOINT BOT API
# =========================

@app.get("/bot")
def bot(
    session_id: str,
    pregunta: str,
    lat: Optional[float] = None,
    lon: Optional[float] = None
):
    respuesta = responder_bot(session_id, pregunta, lat, lon)
    return {"respuesta": respuesta}

# =========================
# TELEGRAM WEBHOOK
# =========================

@app.post("/telegram")
async def telegram_webhook(req: Request):
    data = await req.json()

    if "message" not in data:
        return {"ok": True}

    msg = data["message"]
    chat_id = msg["chat"]["id"]
    text = msg.get("text", "")

    respuesta = responder_bot(str(chat_id), text)
    send_telegram(chat_id, respuesta)

    return {"ok": True}

# =========================
# SET WEBHOOK
# =========================

@app.get("/set-webhook")
def set_webhook(url: str = Query(...)):
    r = requests.get(
        f"{TELEGRAM_API}/setWebhook",
        params={"url": url},
        timeout=10
    )
    return r.json()

# =========================
# HEALTH
# =========================

@app.get("/")
def health():
    return {
        "status": "ok",
        "lugares": len(lugares),
        "sesiones_activas": len(memoria)
    }



