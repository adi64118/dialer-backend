from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import os
import requests
from datetime import date

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise RuntimeError("SUPABASE_URL or SUPABASE_KEY not set")

HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json"
}

app = FastAPI(title="Dialer Backend")

# ---------- CORS FIX ----------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # allow all
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------- MODELS ----------
class LoginData(BaseModel):
    username: str
    password: str

class ProgressData(BaseModel):
    user_id: int
    progress: int

# ---------- ROUTES ----------
@app.get("/")
def root():
    return {"status": "server running"}

@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/login")
def login(data: LoginData):
    print("LOGIN REQUEST:", data.username)

    url = f"{SUPABASE_URL}/rest/v1/users?username=eq.{data.username}&password=eq.{data.password}"
    r = requests.get(url, headers=HEADERS)

    print("SUPABASE STATUS:", r.status_code)
    print("SUPABASE RESPONSE:", r.text)

    if r.status_code != 200 or not r.json():
        raise HTTPException(status_code=401, detail="Invalid login")

    user = r.json()[0]

    if user.get("banned"):
        raise HTTPException(status_code=403, detail="User banned")

    if user.get("expiry") and date.fromisoformat(user["expiry"]) < date.today():
        raise HTTPException(status_code=403, detail="Account expired")

    return {
        "status": "success",
        "user_id": user["id"],
        "sheet_id": user.get("sheet_id"),
        "progress": user.get("progress", 0)
    }

@app.post("/save_progress")
def save_progress(data: ProgressData):
    url = f"{SUPABASE_URL}/rest/v1/users?id=eq.{data.user_id}"
    payload = {"progress": data.progress}

    r = requests.patch(url, headers=HEADERS, json=payload)

    if r.status_code not in (200, 204):
        raise HTTPException(status_code=400, detail="Progress not saved")

    return {"status": "saved"}

@app.get("/get_progress")
def get_progress(user_id: int):
    url = f"{SUPABASE_URL}/rest/v1/users?id=eq.{user_id}&select=progress"
    r = requests.get(url, headers=HEADERS)

    if r.status_code != 200 or not r.json():
        raise HTTPException(status_code=404, detail="User not found")

    return {"progress": r.json()[0].get("progress", 0)}

@app.get("/health")
def health():
    return {"status": "ok"}

import gspread
from oauth2client.service_account import ServiceAccountCredentials

GOOGLE_SHEET_ID = os.getenv("GOOGLE_SHEET_ID")

scope = ["https://spreadsheets.google.com/feeds","https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_name("google.json", scope)
client = gspread.authorize(creds)
sheet = client.open_by_key(GOOGLE_SHEET_ID).sheet1

@app.get("/next")
def get_next(user_id: int):
    url = f"{SUPABASE_URL}/rest/v1/users?id=eq.{user_id}"
    r = requests.get(url, headers=HEADERS)
    user = r.json()[0]

    index = user.get("progress", 0)
    rows = sheet.get_all_values()

    if index + 1 >= len(rows):
        return {"done": True}

    row = rows[index + 1]
    return {
        "index": index,
        "name": row[0],
        "phone": row[1]
    }

@app.post("/save")
def save_and_next(user_id: int, remark: str):
    url = f"{SUPABASE_URL}/rest/v1/users?id=eq.{user_id}"
    requests.patch(url, headers=HEADERS, json={"progress": user_id+1})

    rows = sheet.get_all_values()
    sheet.update_cell(user_id+2, 3, remark)

    return {"status": "saved"}
