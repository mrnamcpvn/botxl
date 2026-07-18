from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from web.templates import templates
import sqlite3, os

router = APIRouter()
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data")
DB_PATH = os.path.join(DATA_DIR, "botxl.db")

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

@router.get("/leaderboard", response_class=HTMLResponse)
async def leaderboard(request: Request):
    conn = get_db()
    rows = conn.execute("SELECT * FROM players ORDER BY elo DESC LIMIT 50").fetchall()
    conn.close()
    is_admin = request.session.get("admin", False)
    return templates.TemplateResponse(request, "leaderboard.html", {"request": request, "is_admin": is_admin, "players": rows})

@router.get("/player/{pid}", response_class=HTMLResponse)
async def player_detail(request: Request, pid: str):
    conn = get_db()
    player = conn.execute("SELECT * FROM players WHERE id=?", (pid,)).fetchone()
    if not player:
        return HTMLResponse("Player not found", status_code=404)
    history = conn.execute(
        "SELECT * FROM battle_history WHERE player1_id=? OR player2_id=? ORDER BY fought_at DESC LIMIT 20",
        (pid, pid)).fetchall()
    conn.close()
    from bot.data.classes import CLASSES
    cls = CLASSES.get(player["class_id"], CLASSES["banxabong"])
    is_admin = request.session.get("admin", False)
    return templates.TemplateResponse(request, "player.html", {
        "request": request, "is_admin": is_admin, "player": player, "cls": cls, "history": history})
