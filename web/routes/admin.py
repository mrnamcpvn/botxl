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

@router.post("/admin/level", response_class=HTMLResponse)
async def admin_level(request: Request, player_id: str = Form(...), level: int = Form(...)):
    if not request.session.get("admin"):
        return RedirectResponse(url="/login")
    conn = get_db()
    msg = ""
    try:
        level = max(1, min(1000, level))
        from bot.config import LEVEL_XP_BASE, STAT_POINTS_PER_LEVEL
        xp = LEVEL_XP_BASE * level * (level - 1) // 2
        current = conn.execute("SELECT level, upgrade_hp, upgrade_atk, upgrade_def FROM players WHERE id=?", (player_id,)).fetchone()
        if not current:
            msg = f"❌ Không tìm thấy người chơi!"
            return
        old_level = current["level"]
        total_earned = (level - 1) * STAT_POINTS_PER_LEVEL
        spent = current["upgrade_hp"] + current["upgrade_atk"] + current["upgrade_def"]
        new_stat_points = max(0, total_earned - spent)
        conn.execute(
            "UPDATE players SET level=?, xp=?, stat_points=? WHERE id=?",
            (level, xp, new_stat_points, player_id))
        conn.commit()
        diff = level - old_level
        msg = f"✅ Set level **{old_level} → {level}** cho <@{player_id}> (stat_points: {new_stat_points})"
    except Exception as e:
        msg = f"❌ Lỗi: {e}"
    finally:
        conn.close()
    players = get_players(); equips = get_equip_list(); skills = get_skill_list(); gems = get_gem_list()
    return templates.TemplateResponse(request, "admin.html", {
        "request": request, "is_admin": True,
        "players": players, "equips": equips, "skills": skills, "gems": gems, "msg": msg
    })


@router.post("/admin/inspect", response_class=HTMLResponse)
async def admin_inspect(request: Request, player_id: str = Form(...)):
    if not request.session.get("admin"):
        return RedirectResponse(url="/login")
    conn = get_db()
    inv = {}
    msg = ""
    try:
        p = conn.execute("SELECT id, name, level, coins, wins, losses, elo, class_id, stat_points, upgrade_hp, upgrade_atk, upgrade_def FROM players WHERE id=?", (player_id,)).fetchone()
        if p:
            inv["player"] = {"id": p["id"], "name": p["name"], "level": p["level"], "coins": p["coins"],
                             "wins": p["wins"], "losses": p["losses"], "elo": p["elo"], "class_id": p["class_id"],
                             "stat_points": p["stat_points"], "upgrade_hp": p["upgrade_hp"],
                             "upgrade_atk": p["upgrade_atk"], "upgrade_def": p["upgrade_def"]}
        stones = conn.execute("SELECT stone_basic, stone_medium, stone_advanced FROM player_enhance_stones WHERE player_id=?", (player_id,)).fetchone()
        inv["stones"] = {"basic": stones[0] if stones else 0, "medium": stones[1] if stones else 0, "advanced": stones[2] if stones else 0}
        equip_rows = conn.execute("SELECT id, item_id, enhance, equipped FROM player_equipment WHERE player_id=?", (player_id,)).fetchall()
        from bot.data.equipment import EQUIPMENT, STAR_LABELS
        inv["equipment"] = []
        for r in equip_rows:
            e = EQUIPMENT.get(r["item_id"], {})
            star = STAR_LABELS.get(e.get("star", 1), "⭐")
            eq_name = f"{star} {e.get('name', '#' + str(r['item_id']))}"
            inv["equipment"].append({"id": r["id"], "item_id": r["item_id"], "enhance": r["enhance"], "equipped": r["equipped"], "name": eq_name})
        inv["equip_count"] = len(inv["equipment"])
        gem_rows = conn.execute("SELECT gem_type, gem_level, quantity FROM player_gems WHERE player_id=? AND quantity>0", (player_id,)).fetchall()
        from bot.config import GEM_TYPES
        inv["gems"] = [{"type": g["gem_type"], "level": g["gem_level"], "qty": g["quantity"],
                        "name": GEM_TYPES.get(g["gem_type"], {}).get("name", g["gem_type"])} for g in gem_rows]
        inv_consume = conn.execute("SELECT item_id, quantity FROM inventory WHERE player_id=?", (player_id,)).fetchall()
        from bot.data.shop_items import SHOP_ITEMS
        inv["consumables"] = [{"id": r["item_id"], "qty": r["quantity"],
                               "name": SHOP_ITEMS.get(r["item_id"], {}).get("name", f"#{r['item_id']}")} for r in inv_consume]
        ach_rows = conn.execute("SELECT ach_id, completed, claimed FROM player_achievements WHERE player_id=? AND completed=1", (player_id,)).fetchall()
        from bot.config import ACHIEVEMENTS
        inv["achievements"] = [{"id": r["ach_id"], "name": ACHIEVEMENTS.get(r["ach_id"], {}).get("name", f"#{r['ach_id']}"),
                                "claimed": r["claimed"], "coins": ACHIEVEMENTS.get(r["ach_id"], {}).get("reward_coins", 0),
                                "stones": ACHIEVEMENTS.get(r["ach_id"], {}).get("reward_stones", {})} for r in ach_rows]
    except Exception as e:
        msg = f"❌ Lỗi: {e}"
    finally:
        conn.close()
    players = get_players(); equips = get_equip_list(); skills = get_skill_list(); gems = get_gem_list()
    return templates.TemplateResponse(request, "admin.html", {
        "request": request, "is_admin": True, "players": players,
        "equips": equips, "skills": skills, "gems": gems,
        "inv": inv, "msg": msg, "inspect_id": player_id
    })


@router.post("/admin/revoke", response_class=HTMLResponse)
async def admin_revoke(request: Request,
                       player_id: str = Form(...),
                       revoke_type: str = Form(...),
                       revoke_id: str = Form(""),
                       amount: int = Form(0)):
    if not request.session.get("admin"):
        return RedirectResponse(url="/login")
    conn = get_db()
    msg = ""
    try:
        if revoke_type == "coins":
            conn.execute("UPDATE players SET coins=MAX(0, coins-?) WHERE id=?", (amount, player_id))
            msg = f"✅ Thu hồi **{amount}**🪙 từ <@{player_id}>"
        elif revoke_type == "stone_basic":
            conn.execute("UPDATE player_enhance_stones SET stone_basic=MAX(0, stone_basic-?) WHERE player_id=?", (amount, player_id))
            msg = f"✅ Thu hồi **{amount}** đá sơ cấp từ <@{player_id}>"
        elif revoke_type == "stone_medium":
            conn.execute("UPDATE player_enhance_stones SET stone_medium=MAX(0, stone_medium-?) WHERE player_id=?", (amount, player_id))
            msg = f"✅ Thu hồi **{amount}** đá trung cấp từ <@{player_id}>"
        elif revoke_type == "stone_advanced":
            conn.execute("UPDATE player_enhance_stones SET stone_advanced=MAX(0, stone_advanced-?) WHERE player_id=?", (amount, player_id))
            msg = f"✅ Thu hồi **{amount}** đá cao cấp từ <@{player_id}>"
        elif revoke_type == "stat_points":
            conn.execute("UPDATE players SET stat_points=MAX(0, stat_points-?) WHERE id=?", (amount, player_id))
            msg = f"✅ Thu hồi **{amount}** stat points từ <@{player_id}>"
        elif revoke_type == "equip":
            conn.execute("DELETE FROM player_equipment WHERE id=? AND player_id=?", (revoke_id, player_id))
            msg = f"✅ Đã xóa trang bị ID **{revoke_id}**"
        elif revoke_type == "gem":
            conn.execute("UPDATE player_gems SET quantity=MAX(0, quantity-?) WHERE player_id=? AND gem_type=? AND gem_level=?", (amount, player_id, revoke_id.split("_")[0], int(revoke_id.split("_")[1])))
            msg = f"✅ Thu hồi **{amount}** đá {revoke_id}"
        elif revoke_type == "consumable":
            conn.execute("UPDATE inventory SET quantity=MAX(0, quantity-?) WHERE player_id=? AND item_id=?", (amount, player_id, int(revoke_id)))
            msg = f"✅ Thu hồi **{amount}** item ID {revoke_id}"
        elif revoke_type == "reset_ach":
            ach_id = int(revoke_id)
            conn.execute("UPDATE player_achievements SET completed=0, claimed=0 WHERE player_id=? AND ach_id=?", (player_id, ach_id))
            from bot.config import ACHIEVEMENTS
            ach_name = ACHIEVEMENTS.get(ach_id, {}).get("name", f"#{ach_id}")
            msg = f"✅ Reset thành tựu **{ach_name}** (có thể claim lại)"
        conn.commit()
    except Exception as e:
        msg = f"❌ Lỗi: {e}"
    finally:
        conn.close()
    players = get_players(); equips = get_equip_list(); skills = get_skill_list(); gems = get_gem_list()
    return templates.TemplateResponse(request, "admin.html", {
        "request": request, "is_admin": True,
        "players": players, "equips": equips, "skills": skills, "gems": gems, "msg": msg
    })
