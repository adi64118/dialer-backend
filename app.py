from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import os, json, requests
from datetime import date
import gspread
from google.oauth2.service_account import Credentials

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json"
}

# ---- GOOGLE SHEET ----
google_creds = json.loads(os.getenv("GOOGLE_CREDENTIALS"))
scope = ["https://www.googleapis.com/auth/spreadsheets"]
creds = Credentials.from_service_account_info(google_creds, scopes=scope)
client = gspread.authorize(creds)

SHEET_NAME = "DialerData"  # apni sheet ka exact naam

app = FastAPI()

class LoginData(BaseModel):
    username: str
    password: str

class ProgressData(BaseModel):
    user_id: int
    progress: int

@app.get("/")
def root():
    return {"status": "server running"}

@app.post("/login")
def login(data: LoginData):
    url = f"{SUPABASE_URL}/rest/v1/users?username=eq.{data.username}&password=eq.{data.password}"
    r = requests.get(url, headers=HEADERS)

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

@app.get("/sheet")
def read_sheet():
    sheet = client.open(SHEET_NAME).sheet1
    rows = sheet.get_all_records()
    return {"rows": rows}

@app.post("/save_progress")
def save_progress(data: ProgressData):
    url = f"{SUPABASE_URL}/rest/v1/users?id=eq.{data.user_id}"
    payload = {"progress": data.progress}
    r = requests.patch(url, headers=HEADERS, json=payload)

    if r.status_code not in (200, 204):
        raise HTTPException(status_code=400, detail="Progress not saved")

    return {"status": "saved"}
