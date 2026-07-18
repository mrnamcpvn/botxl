from fastapi import APIRouter, Request, Form, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from web.templates import templates
from starlette.middleware.sessions import SessionMiddleware
import sqlite3, os, json

router = APIRouter()
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data")
DB_PATH = os.path.join(DATA_DIR, "botxl.db")
ADMIN_PASSWORD = "khanhHUY@300525#"

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def get_players():
    conn = get_db()
    rows = conn.execute("SELECT id, name, level, coins FROM players ORDER BY level DESC").fetchall()
    conn.close()
    return [{"id": r["id"], "name": r["name"] or r["id"], "level": r["level"], "coins": r["coins"]} for r in rows]

def get_equip_list():
    from bot.data.equipment import EQUIPMENT, STAR_LABELS, SLOT_NAMES
    items = []
    for eid, e in sorted(EQUIPMENT.items()):
        stars = STAR_LABELS.get(e["star"], "⭐")
        slot = SLOT_NAMES.get(e["slot"], e["slot"])
        items.append({"id": eid, "name": f"{stars} {e['name']} ({slot})"})
    return items

def get_skill_list():
    from bot.data.skills import SKILLS_DB
    return [{"id": sid, "name": f"{s['icon']} {s['name']} ({s['rarity']})"} for sid, s in SKILLS_DB.items()]

@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse(request, "login.html", {"request": request})

@router.post("/login", response_class=HTMLResponse)
async def login(request: Request, password: str = Form(...)):
    if password == ADMIN_PASSWORD:
        request.session["admin"] = True
        return RedirectResponse(url="/admin", status_code=303)
    return templates.TemplateResponse(request, "login.html", {"request": request, "error": "Sai mật khẩu!"})

@router.get("/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/login")

@router.get("/admin", response_class=HTMLResponse)
async def admin_page(request: Request, msg: str = "", error: str = ""):
    if not request.session.get("admin"):
        return RedirectResponse(url="/login")
    players = get_players()
    equips = get_equip_list()
    skills = get_skill_list()
    return templates.TemplateResponse(request, "admin.html", {
        "request": request, "players": players, "equips": equips, "skills": skills, "msg": msg, "error": error
    })

@router.post("/admin/coins", response_class=HTMLResponse)
async def admin_coins(request: Request, player_id: str = Form(...), amount: int = Form(...)):
    if not request.session.get("admin"):
        return RedirectResponse(url="/login")
    conn = get_db()
    try:
        conn.execute("UPDATE players SET coins=coins+? WHERE id=?", (amount, player_id))
        conn.commit()
        msg = f"✅ Tặng {amount}🪙 cho <@{player_id}>"
    except Exception as e:
        msg, error = "", str(e)
    players = get_players(); equips = get_equip_list(); skills = get_skill_list()
    return templates.TemplateResponse(request, "admin.html", {"request": request, "players": players, "equips": equips, "skills": skills, "msg": msg})

@router.post("/admin/dungeon", response_class=HTMLResponse)
async def admin_dungeon(request: Request, player_id: str = Form(...)):
    if not request.session.get("admin"):
        return RedirectResponse(url="/login")
    conn = get_db()
    try:
        conn.execute("UPDATE dungeon_progress SET daily_entries=MAX(0, daily_entries-1), daily_tickets_bought=MAX(0, daily_tickets_bought-1) WHERE player_id=?", (player_id,))
        conn.execute("INSERT OR IGNORE INTO dungeon_progress (player_id, checkpoint, daily_entries, daily_tickets_bought, last_entry_date, last_week_reset) VALUES (?, 0, 0, 0, '', '')", (player_id,))
        conn.commit()
        msg = f"✅ Reset lượt bí cảnh cho <@{player_id}>"
    except Exception as e:
        msg, error = "", str(e)
    players = get_players(); equips = get_equip_list(); skills = get_skill_list()
    return templates.TemplateResponse(request, "admin.html", {"request": request, "players": players, "equips": equips, "skills": skills, "msg": msg})

@router.post("/admin/equip", response_class=HTMLResponse)
async def admin_equip(request: Request, player_id: str = Form(...), equip_id: int = Form(...)):
    if not request.session.get("admin"):
        return RedirectResponse(url="/login")
    conn = get_db()
    try:
        conn.execute("INSERT INTO player_equipment (player_id, item_id, enhance, equipped) VALUES (?, ?, 0, 0)", (player_id, equip_id))
        conn.commit()
        msg = f"✅ Tặng trang bị cho <@{player_id}>"
    except Exception as e:
        msg, error = "", str(e)
    players = get_players(); equips = get_equip_list(); skills = get_skill_list()
    return templates.TemplateResponse(request, "admin.html", {"request": request, "players": players, "equips": equips, "skills": skills, "msg": msg})

@router.post("/admin/stones", response_class=HTMLResponse)
async def admin_stones(request: Request, player_id: str = Form(...), stone_type: str = Form(...), amount: int = Form(...)):
    if not request.session.get("admin"):
        return RedirectResponse(url="/login")
    conn = get_db()
    labels = {"stone_basic": "Đá sơ cấp", "stone_medium": "Đá trung cấp", "stone_advanced": "Đá cao cấp", "artifact": "Đá thần khí"}
    try:
        if stone_type == "artifact":
            conn.execute("INSERT OR REPLACE INTO player_artifact (player_id, star, stone_count) VALUES (?, COALESCE((SELECT star FROM player_artifact WHERE player_id=?), 0), COALESCE((SELECT stone_count FROM player_artifact WHERE player_id=?), 0) + ?)",
                         (player_id, player_id, player_id, amount))
        else:
            conn.execute(f"INSERT OR REPLACE INTO player_enhance_stones (player_id, {stone_type}, stone_basic, stone_medium, stone_advanced) VALUES (?, ?, COALESCE((SELECT stone_basic FROM player_enhance_stones WHERE player_id=?), 0), COALESCE((SELECT stone_medium FROM player_enhance_stones WHERE player_id=?), 0), COALESCE((SELECT stone_advanced FROM player_enhance_stones WHERE player_id=?), 0))",
                         (player_id, amount, player_id, player_id, player_id))
            conn.execute(f"UPDATE player_enhance_stones SET {stone_type}=COALESCE((SELECT {stone_type} FROM player_enhance_stones WHERE player_id=?), 0) WHERE player_id=? AND ({stone_type} IS NULL OR {stone_type}=0)",
                         (player_id, player_id))
        conn.commit()
        msg = f"✅ Tặng {amount} {labels[stone_type]} cho <@{player_id}>"
    except Exception as e:
        msg, error = "", str(e)
    players = get_players(); equips = get_equip_list(); skills = get_skill_list()
    return templates.TemplateResponse(request, "admin.html", {"request": request, "players": players, "equips": equips, "skills": skills, "msg": msg})

@router.post("/admin/skill", response_class=HTMLResponse)
async def admin_skill(request: Request, player_id: str = Form(...), skill_id: int = Form(...)):
    if not request.session.get("admin"):
        return RedirectResponse(url="/login")
    conn = get_db()
    try:
        conn.execute("INSERT OR IGNORE INTO player_skills (player_id, skill_id) VALUES (?, ?)", (player_id, skill_id))
        conn.commit()
        from bot.data.skills import SKILLS_DB
        sn = SKILLS_DB.get(skill_id, {}).get("name", f"Skill {skill_id}")
        msg = f"✅ Tặng {sn} cho <@{player_id}>"
    except Exception as e:
        msg, error = "", str(e)
    players = get_players(); equips = get_equip_list(); skills = get_skill_list()
    return templates.TemplateResponse(request, "admin.html", {"request": request, "players": players, "equips": equips, "skills": skills, "msg": msg})

@router.post("/admin/artifact", response_class=HTMLResponse)
async def admin_artifact(request: Request, player_id: str = Form(...), star: int = Form(...)):
    if not request.session.get("admin"):
        return RedirectResponse(url="/login")
    conn = get_db()
    try:
        conn.execute("INSERT OR REPLACE INTO player_artifact (player_id, star, stone_count) VALUES (?, ?, COALESCE((SELECT stone_count FROM player_artifact WHERE player_id=?), 0))",
                     (player_id, star, player_id))
        conn.commit()
        msg = f"✅ Set thần khí ★{star} cho <@{player_id}>"
    except Exception as e:
        msg, error = "", str(e)
    players = get_players(); equips = get_equip_list(); skills = get_skill_list()
    return templates.TemplateResponse(request, "admin.html", {"request": request, "players": players, "equips": equips, "skills": skills, "msg": msg})

@router.post("/admin/resetcd", response_class=HTMLResponse)
async def admin_resetcd(request: Request, player_id: str = Form(...)):
    if not request.session.get("admin"):
        return RedirectResponse(url="/login")
    conn = get_db()
    try:
        conn.execute("UPDATE players SET attack_cd=0, special_cd=0, defense_cd=0 WHERE id=?", (player_id,))
        conn.commit()
        msg = f"✅ Reset CD cho <@{player_id}>"
    except Exception as e:
        msg, error = "", str(e)
    players = get_players(); equips = get_equip_list(); skills = get_skill_list()
    return templates.TemplateResponse(request, "admin.html", {"request": request, "players": players, "equips": equips, "skills": skills, "msg": msg})
