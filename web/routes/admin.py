from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from web.templates import templates
import sqlite3, os, random
from datetime import datetime, timedelta

router = APIRouter()
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data")
DB_PATH = os.path.join(DATA_DIR, "botxl.db")
ADMIN_PASSWORD = "admin123"

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

@router.get("/admin", response_class=HTMLResponse)
async def admin_page(request: Request, msg: str = "", error: str = ""):
    return templates.TemplateResponse(request, "admin.html", {"request": request, "msg": msg, "error": error})

@router.post("/admin/coins", response_class=HTMLResponse)
async def admin_coins(request: Request, password: str = Form(...), player_id: str = Form(...), amount: int = Form(...)):
    if password != ADMIN_PASSWORD:
        return templates.TemplateResponse(request, "admin.html", {"request": request, "error": "Sai mật khẩu!"})
    conn = get_db()
    try:
        conn.execute("UPDATE players SET coins=coins+? WHERE id=?", (amount, player_id))
        conn.commit()
        msg = f"✅ Tặng {amount}🪙 cho {player_id}"
    except Exception as e:
        msg = ""
        error = str(e)
    finally:
        conn.close()
    return templates.TemplateResponse(request, "admin.html", {"request": request, "msg": msg, "error": error})

@router.post("/admin/dungeon", response_class=HTMLResponse)
async def admin_dungeon(request: Request, password: str = Form(...), player_id: str = Form(...)):
    if password != ADMIN_PASSWORD:
        return templates.TemplateResponse(request, "admin.html", {"request": request, "error": "Sai mật khẩu!"})
    conn = get_db()
    try:
        conn.execute("UPDATE dungeon_progress SET daily_entries=MAX(0, daily_entries-1), daily_tickets_bought=MAX(0, daily_tickets_bought-1) WHERE player_id=?", (player_id,))
        conn.execute("INSERT OR IGNORE INTO dungeon_progress (player_id, checkpoint, daily_entries, daily_tickets_bought, last_entry_date, last_week_reset) VALUES (?, 0, 0, 0, '', '')", (player_id,))
        conn.commit()
        msg = f"✅ Reset lượt bí cảnh cho {player_id}"
    except Exception as e:
        msg = ""
        error = str(e)
    finally:
        conn.close()
    return templates.TemplateResponse(request, "admin.html", {"request": request, "msg": msg, "error": error})

@router.post("/admin/equip", response_class=HTMLResponse)
async def admin_equip(request: Request, password: str = Form(...), player_id: str = Form(...), equip_id: int = Form(...)):
    if password != ADMIN_PASSWORD:
        return templates.TemplateResponse(request, "admin.html", {"request": request, "error": "Sai mật khẩu!"})
    conn = get_db()
    try:
        conn.execute("INSERT INTO player_equipment (player_id, item_id, enhance, equipped) VALUES (?, ?, 0, 0)", (player_id, equip_id))
        conn.commit()
        msg = f"✅ Tặng trang bị ID {equip_id} cho {player_id}"
    except Exception as e:
        msg = ""
        error = str(e)
    finally:
        conn.close()
    return templates.TemplateResponse(request, "admin.html", {"request": request, "msg": msg, "error": error})

@router.post("/admin/stones", response_class=HTMLResponse)
async def admin_stones(request: Request, password: str = Form(...), player_id: str = Form(...), stone_type: str = Form(...), amount: int = Form(...)):
    if password != ADMIN_PASSWORD:
        return templates.TemplateResponse(request, "admin.html", {"request": request, "error": "Sai mật khẩu!"})
    conn = get_db()
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
        labels = {"stone_basic": "Đá sơ cấp", "stone_medium": "Đá trung cấp", "stone_advanced": "Đá cao cấp", "artifact": "Đá thần khí"}
        msg = f"✅ Tặng {amount} {labels.get(stone_type, stone_type)} cho {player_id}"
    except Exception as e:
        msg = ""
        error = str(e)
    finally:
        conn.close()
    return templates.TemplateResponse(request, "admin.html", {"request": request, "msg": msg, "error": error})

@router.post("/admin/resetcd", response_class=HTMLResponse)
async def admin_resetcd(request: Request, password: str = Form(...), player_id: str = Form(...)):
    if password != ADMIN_PASSWORD:
        return templates.TemplateResponse(request, "admin.html", {"request": request, "error": "Sai mật khẩu!"})
    conn = get_db()
    try:
        conn.execute("UPDATE players SET attack_cd=0, special_cd=0, defense_cd=0 WHERE id=?", (player_id,))
        conn.commit()
        msg = f"✅ Reset cooldown cho {player_id}"
    except Exception as e:
        msg = ""
        error = str(e)
    finally:
        conn.close()
    return templates.TemplateResponse(request, "admin.html", {"request": request, "msg": msg, "error": error})

@router.post("/admin/artifact", response_class=HTMLResponse)
async def admin_artifact(request: Request, password: str = Form(...), player_id: str = Form(...), star: int = Form(...)):
    if password != ADMIN_PASSWORD:
        return templates.TemplateResponse(request, "admin.html", {"request": request, "error": "Sai mật khẩu!"})
    conn = get_db()
    try:
        conn.execute("INSERT OR REPLACE INTO player_artifact (player_id, star, stone_count) VALUES (?, ?, COALESCE((SELECT stone_count FROM player_artifact WHERE player_id=?), 0))",
                     (player_id, star, player_id))
        conn.commit()
        msg = f"✅ Set thần khí ★{star} cho {player_id}"
    except Exception as e:
        msg = ""
        error = str(e)
    finally:
        conn.close()
    return templates.TemplateResponse(request, "admin.html", {"request": request, "msg": msg, "error": error})

@router.post("/admin/skill", response_class=HTMLResponse)
async def admin_skill(request: Request, password: str = Form(...), player_id: str = Form(...), skill_id: int = Form(...)):
    if password != ADMIN_PASSWORD:
        return templates.TemplateResponse(request, "admin.html", {"request": request, "error": "Sai mật khẩu!"})
    conn = get_db()
    try:
        conn.execute("INSERT OR IGNORE INTO player_skills (player_id, skill_id) VALUES (?, ?)", (player_id, skill_id))
        conn.commit()
        from bot.data.skills import SKILLS_DB
        skill_name = SKILLS_DB.get(skill_id, {}).get("name", f"Skill {skill_id}")
        msg = f"✅ Tặng {skill_name} cho {player_id}"
    except Exception as e:
        msg = ""
        error = str(e)
    finally:
        conn.close()
    return templates.TemplateResponse(request, "admin.html", {"request": request, "msg": msg, "error": error})
