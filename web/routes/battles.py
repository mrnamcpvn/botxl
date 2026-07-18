from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from web.templates import templates
import sqlite3
import json
import os

router = APIRouter()
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data")
DB_PATH = os.path.join(DATA_DIR, "botxl.db")

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

@router.get("/battle/{bid}", response_class=HTMLResponse)
async def battle_detail(request: Request, bid: int):
    conn = get_db()
    battle = conn.execute("SELECT * FROM battle_history WHERE id=?", (bid,)).fetchone()
    conn.close()
    if not battle:
        return HTMLResponse("Battle not found", status_code=404)
    rounds = json.loads(battle["rounds"])
    is_admin = request.session.get("admin", False)
    return templates.TemplateResponse(request, "battle_replay.html", {
        "request": request, "is_admin": is_admin, "battle": battle, "rounds": rounds})
