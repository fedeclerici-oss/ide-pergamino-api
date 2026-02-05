import json
import os
import requests
from fastapi import FastAPI

app = FastAPI()

DATA_URL = "https://github.com/fedeclerici-oss/ide-pergamino-api/releases/download/v1-data/ide_normalizado.json"
LOCAL_FILE = "ide_normalizado.json"


def cargar_data():
    if not os.path.exists(LOCAL_FILE):
        print("Descargando datos IDE desde GitHub Releases...")
        r = requests.get(DATA_URL)
        r.raise_for_status()
        with open(LOCAL_FILE, "wb") as f:
            f.write(r.content)

    with open(LOCAL_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


DATA = cargar_data()


@app.get("/")
def home():
    return {"status": "ok", "items": len(DATA)}
