
import sqlite3
import os

DB_PATH = "data/project_copilot.db"

def check_migrations():
    if not os.path.exists(DB_PATH):
        print("No DB.")
        return

    conn = sqlite3.connect(DB_PATH)
    try:
        cur = conn.execute("SELECT version FROM schema_migrations ORDER BY version")
        applied = [r[0] for r in cur.fetchall()]
        print(f"Applied migrations: {applied}")
    except Exception as e:
        print(f"Error reading migrations: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    check_migrations()
