from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import os, json, requests
from datetime import date
from google.oauth2.service_account import Credentials
import gspread

# ----------------- ENV -----------------
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
SHEET_ID = os.getenv("SHEET_ID")
GOOGLE_CREDENTIALS_JSON = os.getenv("GOOGLE_CREDENTIALS")

HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json"
}

# ----------------- APP -----------------
app = FastAPI(title="Dialer Backend")

# ----------------- GOOGLE SHEET -----------------
gc = gspread.service_account_from_dict(json.loads(GOOGLE_CREDENTIALS_JSON))
sheet = gc.open_by_key(SHEET_ID).sheet1  # first sheet

# ----------------- MODELS -----------------
class LoginData(BaseModel):
    username: str
    password: str

class ProgressData(BaseModel):
    user_id: int
    progress: int

# ----------------- ROUTES -----------------
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

    if user.get("expiry") and date.fromisoformat(user["expiry"]) < date.today():
        raise HTTPException(status_code=403, detail="Account expired")

    # Get user's row in Google Sheet
    try:
        cell = sheet.find(str(user["id"]))
        row_index = cell.row
    except:
        row_index = None

    return {
        "status": "success",
        "user_id": user["id"],
        "sheet_row": row_index,
        "progress": user.get("progress", 0)
    }

@app.post("/save_progress")
def save_progress(data: ProgressData):
    url = f"{SUPABASE_URL}/rest/v1/users?id=eq.{data.user_id}"
    payload = {"progress": data.progress}
    r = requests.patch(url, headers=HEADERS, json=payload)

    if r.status_code not in (200, 204):
        raise HTTPException(status_code=400, detail="Progress not saved")

    # Update Google Sheet progress
    if sheet:
        try:
            cell = sheet.find(str(data.user_id))
            sheet.update_cell(cell.row, 4, data.progress)  # 4th column = progress
        except:
            pass

    return {"status": "saved"}

@app.get("/get_progress")
def get_progress(user_id: int):
    url = f"{SUPABASE_URL}/rest/v1/users?id=eq.{user_id}&select=progress"
    r = requests.get(url, headers=HEADERS)

    if r.status_code != 200 or not r.json():
        raise HTTPException(status_code=404, detail="User not found")

    return {"progress": r.json()[0].get("progress", 0)}
