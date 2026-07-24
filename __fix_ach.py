import sqlite3
conn = sqlite3.connect('data/botxl.db')
c = conn.cursor()
c.execute("SELECT player_id, COUNT(*) FROM player_equipment WHERE item_id IN (701,702,703,704,705,706) GROUP BY player_id")
rows = c.fetchall()
for pid, cnt in rows:
    c.execute("UPDATE player_achievements SET progress=?, completed=1, claimed=0 WHERE player_id=? AND ach_id=?", (min(cnt, 1), pid, 19))
    print(f"Fixed ach 19 for {pid}, has {cnt} seven-star items")
    if cnt >= 5:
        c.execute("UPDATE player_achievements SET progress=?, completed=1, claimed=0 WHERE player_id=? AND ach_id=?", (min(cnt, 5), pid, 20))
        print(f"  Also fixed ach 20 for {pid}")
conn.commit()
conn.close()
print("Done!")
