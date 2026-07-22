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
        items.append({"id": eid, "name": f"{stars} {e['name']} ({slot})", "star": e["star"]})
    return items

def get_skill_list():
    from bot.data.skills import SKILLS_DB
    return [{"id": sid, "name": f"{s['icon']} {s['name']} ({s['rarity']})"} for sid, s in SKILLS_DB.items()]

def get_gem_list():
    from bot.config import GEM_TYPES
    return [{"type": gtype, "name": info["name"]} for gtype, info in GEM_TYPES.items()]

@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse(request, "login.html", {"request": request, "is_admin": False})

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
    gems = get_gem_list()
    return templates.TemplateResponse(request, "admin.html", {
        "request": request, "is_admin": True, "players": players, "equips": equips, "skills": skills, "gems": gems, "msg": msg, "error": error
    })

@router.post("/admin/coins", response_class=HTMLResponse)
async def admin_coins(request: Request, player_id: str = Form(...), amount: int = Form(...)):
    if not request.session.get("admin"):
        return RedirectResponse(url="/login")
    conn = get_db()
    msg = ""
    try:
        conn.execute("UPDATE players SET coins=coins+? WHERE id=?", (amount, player_id))
        conn.commit()
        msg = f"✅ Tặng **{amount}**🪙 cho <@{player_id}>"
    except Exception as e:
        msg = f"❌ Lỗi: {e}"
    finally:
        conn.close()
    players = get_players(); equips = get_equip_list(); skills = get_skill_list(); gems = get_gem_list(); gems = get_gem_list()
    return templates.TemplateResponse(request, "admin.html", {
        "request": request, "is_admin": True,
        "players": players, "equips": equips, "skills": skills, "gems": gems, "gems": gems, "msg": msg
    })

@router.post("/admin/dungeon", response_class=HTMLResponse)
async def admin_dungeon(request: Request, player_id: str = Form(...), entries: int = Form(...)):
    if not request.session.get("admin"):
        return RedirectResponse(url="/login")
    conn = get_db()
    msg = ""
    try:
        conn.execute(
            "INSERT OR IGNORE INTO dungeon_progress (player_id, checkpoint, daily_entries, daily_tickets_bought, last_entry_date, last_week_reset) VALUES (?, 0, 0, 0, '', '')",
            (player_id,)
        )
        # Giảm daily_entries để player có thêm lượt (tặng thêm lượt = giảm số đã dùng)
        conn.execute(
            "UPDATE dungeon_progress SET daily_entries=MAX(0, daily_entries-?), daily_tickets_bought=MAX(0, daily_tickets_bought-?) WHERE player_id=?",
            (entries, entries, player_id)
        )
        conn.commit()
        msg = f"✅ Tặng **{entries}** lượt bí cảnh cho <@{player_id}>"
    except Exception as e:
        msg = f"❌ Lỗi: {e}"
    finally:
        conn.close()
    players = get_players(); equips = get_equip_list(); skills = get_skill_list(); gems = get_gem_list()
    return templates.TemplateResponse(request, "admin.html", {
        "request": request, "is_admin": True,
        "players": players, "equips": equips, "skills": skills, "gems": gems, "msg": msg
    })

@router.post("/admin/equip", response_class=HTMLResponse)
async def admin_equip(request: Request, player_id: str = Form(...), equip_id: int = Form(...)):
    if not request.session.get("admin"):
        return RedirectResponse(url="/login")
    conn = get_db()
    msg = ""
    try:
        conn.execute(
            "INSERT INTO player_equipment (player_id, item_id, enhance, equipped) VALUES (?, ?, 0, 0)",
            (player_id, equip_id)
        )
        conn.commit()
        from bot.data.equipment import EQUIPMENT, STAR_LABELS
        eq = EQUIPMENT.get(equip_id, {})
        eq_name = f"{STAR_LABELS.get(eq.get('star', 1), '⭐')} {eq.get('name', f'Item {equip_id}')}"
        msg = f"✅ Tặng **{eq_name}** cho <@{player_id}>"
    except Exception as e:
        msg = f"❌ Lỗi: {e}"
    finally:
        conn.close()
    players = get_players(); equips = get_equip_list(); skills = get_skill_list(); gems = get_gem_list()
    return templates.TemplateResponse(request, "admin.html", {
        "request": request, "is_admin": True,
        "players": players, "equips": equips, "skills": skills, "gems": gems, "msg": msg
    })

@router.post("/admin/stones", response_class=HTMLResponse)
async def admin_stones(request: Request, player_id: str = Form(...), stone_type: str = Form(...), amount: int = Form(...)):
    if not request.session.get("admin"):
        return RedirectResponse(url="/login")
    conn = get_db()
    labels = {
        "stone_basic": "Đá Sơ Cấp",
        "stone_medium": "Đá Trung Cấp",
        "stone_advanced": "Đá Cao Cấp",
        "artifact": "Đá Thần Khí",
    }
    msg = ""
    try:
        if stone_type == "artifact":
            # Tặng đá thần khí — giữ nguyên star, cộng thêm đá
            row = conn.execute(
                "SELECT star, stone_count FROM player_artifact WHERE player_id=?",
                (player_id,)
            ).fetchone()
            if row:
                conn.execute(
                    "UPDATE player_artifact SET stone_count=stone_count+? WHERE player_id=?",
                    (amount, player_id)
                )
            else:
                # Chưa kích hoạt: tặng đá nhưng star=0 (vẫn cần 100k xu để mở)
                conn.execute(
                    "INSERT INTO player_artifact (player_id, star, stone_count) VALUES (?, 0, ?)",
                    (player_id, amount)
                )

        elif stone_type in ("stone_basic", "stone_medium", "stone_advanced"):
            # Tặng đá cường hóa — dùng UPSERT an toàn
            existing = conn.execute(
                "SELECT stone_basic, stone_medium, stone_advanced FROM player_enhance_stones WHERE player_id=?",
                (player_id,)
            ).fetchone()
            if existing:
                conn.execute(
                    f"UPDATE player_enhance_stones SET {stone_type}={stone_type}+? WHERE player_id=?",
                    (amount, player_id)
                )
            else:
                # Row chưa tồn tại — tạo mới với đúng cột
                vals = {
                    "stone_basic": 0, "stone_medium": 0, "stone_advanced": 0
                }
                vals[stone_type] = amount
                conn.execute(
                    "INSERT INTO player_enhance_stones (player_id, stone_basic, stone_medium, stone_advanced) VALUES (?, ?, ?, ?)",
                    (player_id, vals["stone_basic"], vals["stone_medium"], vals["stone_advanced"])
                )
        else:
            msg = f"❌ Loại đá không hợp lệ: {stone_type}"

        if not msg:
            conn.commit()
            msg = f"✅ Tặng **{amount}x {labels.get(stone_type, stone_type)}** cho <@{player_id}>"

    except Exception as e:
        msg = f"❌ Lỗi: {e}"
    finally:
        conn.close()
    players = get_players(); equips = get_equip_list(); skills = get_skill_list(); gems = get_gem_list()
    return templates.TemplateResponse(request, "admin.html", {
        "request": request, "is_admin": True,
        "players": players, "equips": equips, "skills": skills, "gems": gems, "msg": msg
    })

@router.post("/admin/gem", response_class=HTMLResponse)
async def admin_gem(request: Request, player_id: str = Form(...), gem_type: str = Form(...), gem_level: int = Form(...), quantity: int = Form(1)):
    if not request.session.get("admin"):
        return RedirectResponse(url="/login")
    conn = get_db()
    msg = ""
    try:
        from bot.config import GEM_TYPES
        info = GEM_TYPES.get(gem_type, {})
        gem_name = info.get("name", gem_type) if info else gem_type
        conn.execute(
            "INSERT INTO player_gems (player_id, gem_type, gem_level, quantity) VALUES (?, ?, ?, ?) "
            "ON CONFLICT(player_id, gem_type, gem_level) DO UPDATE SET quantity=quantity+?",
            (player_id, gem_type, gem_level, quantity, quantity))
        conn.commit()
        msg = f"✅ Tặng **{quantity}x {gem_name} C{gem_level}** cho <@{player_id}>"
    except Exception as e:
        msg = f"❌ Lỗi: {e}"
    finally:
        conn.close()
    players = get_players(); equips = get_equip_list(); skills = get_skill_list(); gems = get_gem_list()
    return templates.TemplateResponse(request, "admin.html", {
        "request": request, "is_admin": True,
        "players": players, "equips": equips, "skills": skills, "gems": gems, "msg": msg
    })

@router.post("/admin/skill", response_class=HTMLResponse)
async def admin_skill(request: Request, player_id: str = Form(...), skill_id: int = Form(...)):
    if not request.session.get("admin"):
        return RedirectResponse(url="/login")
    conn = get_db()
    msg = ""
    try:
        conn.execute("INSERT OR IGNORE INTO player_skills (player_id, skill_id) VALUES (?, ?)", (player_id, skill_id))
        conn.commit()
        from bot.data.skills import SKILLS_DB
        sk = SKILLS_DB.get(skill_id, {})
        sn = f"{sk.get('icon', '')} {sk.get('name', f'Skill {skill_id}')}"
        msg = f"✅ Tặng **{sn}** cho <@{player_id}>"
    except Exception as e:
        msg = f"❌ Lỗi: {e}"
    finally:
        conn.close()
    players = get_players(); equips = get_equip_list(); skills = get_skill_list(); gems = get_gem_list()
    return templates.TemplateResponse(request, "admin.html", {
        "request": request, "is_admin": True,
        "players": players, "equips": equips, "skills": skills, "gems": gems, "msg": msg
    })

@router.post("/admin/artifact", response_class=HTMLResponse)
async def admin_artifact(request: Request, player_id: str = Form(...), star: int = Form(...)):
    if not request.session.get("admin"):
        return RedirectResponse(url="/login")
    conn = get_db()
    try:
        # Đảm bảo star hợp lệ
        star = max(1, min(10, star))

        # Lấy stone_count hiện tại (nếu có), giữ nguyên
        row = conn.execute(
            "SELECT stone_count FROM player_artifact WHERE player_id=?", (player_id,)
        ).fetchone()
        current_stones = row["stone_count"] if row else 0

        # INSERT OR REPLACE — tạo mới hoặc cập nhật, luôn set star đúng
        # Khi player chưa kích hoạt: tạo row mới với star được tặng
        # Khi đã có: cập nhật star, giữ stone_count
        conn.execute(
            "INSERT OR REPLACE INTO player_artifact (player_id, star, stone_count) VALUES (?, ?, ?)",
            (player_id, star, current_stones)
        )
        conn.commit()

        from bot.data.artifacts import ARTIFACTS
        artifact_name = ARTIFACTS.get(star, {}).get("name", f"★{star}")
        msg = f"✅ Tặng Thần Khí **{artifact_name}** (★{star}) cho <@{player_id}>"
    except Exception as e:
        msg = f"❌ Lỗi: {e}"
    finally:
        conn.close()
    players = get_players(); equips = get_equip_list(); skills = get_skill_list(); gems = get_gem_list()
    return templates.TemplateResponse(request, "admin.html", {
        "request": request, "is_admin": True,
        "players": players, "equips": equips, "skills": skills, "gems": gems, "msg": msg
    })

@router.post("/admin/resetcd", response_class=HTMLResponse)
async def admin_resetcd(request: Request, player_id: str = Form(...)):
    if not request.session.get("admin"):
        return RedirectResponse(url="/login")
    conn = get_db()
    msg = ""
    try:
        conn.execute(
            "UPDATE players SET attack_cd=0, special_cd=0, defense_cd=0 WHERE id=?",
            (player_id,)
        )
        conn.commit()
        msg = f"✅ Reset cooldown cho <@{player_id}>"
    except Exception as e:
        msg = f"❌ Lỗi: {e}"
    finally:
        conn.close()
    players = get_players(); equips = get_equip_list(); skills = get_skill_list(); gems = get_gem_list()
    return templates.TemplateResponse(request, "admin.html", {
        "request": request, "is_admin": True,
        "players": players, "equips": equips, "skills": skills, "gems": gems, "msg": msg
    })
