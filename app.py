from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import os, json, requests
from datetime import date
from google.oauth2.service_account import Credentials
import gspread

# ================== ENV ==================
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
GOOGLE_CREDENTIALS = os.getenv("GOOGLE_CREDENTIALS")
SHEET_ID = os.getenv("SHEET_ID")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise RuntimeError("SUPABASE env not set")

if not GOOGLE_CREDENTIALS or not SHEET_ID:
    raise RuntimeError("GOOGLE env not set")

HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json"
}

# ================== GOOGLE SHEET ==================
google_creds = json.loads(GOOGLE_CREDENTIALS)
scope = ["https://www.googleapis.com/auth/spreadsheets"]
creds = Credentials.from_service_account_info(google_creds, scopes=scope)
gc = gspread.authorize(creds)
sheet = gc.open_by_key(SHEET_ID).sheet1

# ================== FASTAPI ==================
app = FastAPI(title="Dialer Backend")

class LoginData(BaseModel):
    username: str
    password: str

class ProgressData(BaseModel):
    user_id: int
    progress: int

# ================== ROUTES ==================

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

    if user.get("banned"):
        raise HTTPException(status_code=403, detail="User banned")

    if user.get("expiry"):
        if date.fromisoformat(user["expiry"]) < date.today():
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

# ================== GOOGLE SHEET DIALER ==================

@app.get("/next_number")
def next_number(row: int):
    try:
        number = sheet.cell(row, 1).value
        return {"number": number}
    except:
        raise HTTPException(status_code=404, detail="Row not found")

@app.post("/mark_called")
def mark_called(row: int):
    try:
        sheet.update_cell(row, 2, "CALLED")
        return {"status": "updated"}
    except:
        raise HTTPException(status_code=400, detail="Sheet update failed")
