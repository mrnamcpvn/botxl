"""Fix: set claimed=1 for all completed achievements to prevent double-claim."""
import sqlite3
conn = sqlite3.connect("data/botxl.db")
c = conn.cursor()
c.execute("UPDATE player_achievements SET claimed=1 WHERE completed=1 AND claimed=0")
fixed = c.rowcount
conn.commit()
conn.close()
print(f"Fixed {fixed} rows: set claimed=1 for completed achievements.")
