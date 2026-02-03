from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import os, json, requests
from datetime import date
import gspread
from google.oauth2.service_account import Credentials

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
GOOGLE_SHEET_ID = os.getenv("GOOGLE_SHEET_ID")
GOOGLE_CREDENTIALS = os.getenv("GOOGLE_CREDENTIALS")

HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json"
}

app = FastAPI(title="Dialer Backend")

# ---------- GOOGLE AUTH ----------
creds_dict = json.loads(GOOGLE_CREDENTIALS)
scopes = ["https://www.googleapis.com/auth/spreadsheets"]
creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
gc = gspread.authorize(creds)
sheet = gc.open_by_key(GOOGLE_SHEET_ID).sheet1

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
    url = f"{SUPABASE_URL}/rest/v1/users?username=eq.{data.username}&password=eq.{data.password}"
    r = requests.get(url, headers=HEADERS)

    if r.status_code != 200 or not r.json():
        raise HTTPException(status_code=401, detail="Invalid login")

    user = r.json()[0]
    return {"status": "success", "user_id": user["id"], "progress": user.get("progress", 0)}

@app.get("/get_numbers")
def get_numbers(start: int = 0, limit: int = 10):
    data = sheet.get_all_values()[1:]  # skip header
    sliced = data[start:start+limit]
    return {"numbers": sliced}

@app.post("/save_progress")
def save_progress(data: ProgressData):
    url = f"{SUPABASE_URL}/rest/v1/users?id=eq.{data.user_id}"
    payload = {"progress": data.progress}
    r = requests.patch(url, headers=HEADERS, json=payload)
    return {"status": "saved"}
