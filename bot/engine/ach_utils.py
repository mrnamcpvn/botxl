from bot.database import get_db
from bot.config import ACHIEVEMENTS

_UPSERT = ("INSERT INTO player_achievements (player_id, ach_id, progress, completed, claimed) VALUES (?,?,?,?,0) "
           "ON CONFLICT(player_id, ach_id) DO UPDATE SET progress=excluded.progress, completed=excluded.completed")


async def ach_progress(sid: str, ach_type: str, amount: int = 1, db=None):
    close = db is None
    if close:
        db = await get_db()
    try:
        for ach_id, ach_def in ACHIEVEMENTS.items():
            if ach_def["type"] != ach_type:
                continue
            cursor = await db.execute(
                "SELECT progress, completed, claimed FROM player_achievements WHERE player_id=? AND ach_id=?",
                (sid, ach_id))
            row = await cursor.fetchone()
            if row and row[2]:
                continue
            old_p = row[0] if row else 0
            completed = row[1] if row else 0
            new_p = old_p + amount
            if new_p >= ach_def["target"] and not completed:
                completed = 1
            await db.execute(_UPSERT, (sid, ach_id, new_p, completed))
        if close:
            await db.commit()
    finally:
        if close:
            await db.close()


async def ach_check(sid: str, ach_type: str, current_value: int, db=None):
    close = db is None
    if close:
        db = await get_db()
    try:
        for ach_id, ach_def in ACHIEVEMENTS.items():
            if ach_def["type"] != ach_type:
                continue
            cursor = await db.execute(
                "SELECT progress, completed, claimed FROM player_achievements WHERE player_id=? AND ach_id=?",
                (sid, ach_id))
            row = await cursor.fetchone()
            if row and row[2]:
                continue
            completed = row[1] if row else 0
            if current_value >= ach_def["target"] and not completed:
                progress = min(current_value, ach_def["target"])
                await db.execute(_UPSERT, (sid, ach_id, progress, 1))
        if close:
            await db.commit()
    finally:
        if close:
            await db.close()
