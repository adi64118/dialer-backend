from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import os
import requests
from datetime import date

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise RuntimeError("SUPABASE_URL or SUPABASE_KEY missing")

HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Accept": "application/json"
}

app = FastAPI(title="Dialer Backend")

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

@app.post("/login")
def login(data: LoginData):
    # 🔹 Step 1: only fetch by username
    url = f"{SUPABASE_URL}/rest/v1/users?username=eq.{data.username}"
    r = requests.get(url, headers=HEADERS)

    if r.status_code != 200:
        raise HTTPException(status_code=500, detail="Supabase error")

    users = r.json()
    if not users:
        raise HTTPException(status_code=401, detail="Invalid login")

    user = users[0]

    # 🔹 Step 2: check password manually
    if user["password"] != data.password:
        raise HTTPException(status_code=401, detail="Invalid login")

    # 🔹 Step 3: banned check
    if user.get("banned") is True:
        raise HTTPException(status_code=403, detail="User banned")

    # 🔹 Step 4: expiry check
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

@app.get("/health")
def health():
    return {"status": "ok"}
