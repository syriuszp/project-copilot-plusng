
import logging
import sys
import sqlite3
import traceback

# Setup Logging
logging.basicConfig(level=logging.INFO, stream=sys.stdout)

from app.db.migrator import ensure_schema

def inspect_dirty_state():
    db_path = "dev_data/db/project_copilot.dev.db"
    
    # 1. Inspect Schema Migrations
    print(f"--- DB Migrations: {db_path} ---")
    with sqlite3.connect(db_path) as conn:
        try:
            for row in conn.execute("SELECT * FROM schema_migrations"):
                print(row)
        except Exception as e:
            print(f"Could not read migrations: {e}")

    # 2. Inspect Schema
    print(f"\n--- DB Schema Before ---")
    with sqlite3.connect(db_path) as conn:
        try:
             for row in conn.execute("PRAGMA table_info(artifacts)"): print(row)
        except: pass
        
    # 3. Try to Force Rebuild (Manual)
    print(f"\n--- Attempting Manual Ensure Schema + FTS Rebuild ---")
    try:
        with sqlite3.connect(db_path) as conn:
            conn.execute("PRAGMA foreign_keys=ON;")
            
            # Inspect FTS schema
            print("FTS Schema Before:")
            try:
                 for row in conn.execute("PRAGMA table_info(artifact_fts)"): print(row)
            except: print("FTS missing")
            
            # DROP FTS manual intervention
            print("Dropping legacy FTS...")
            conn.execute("DROP TABLE IF EXISTS artifact_fts")
            
            ensure_schema(conn)
            conn.commit()
            print("Manual Ensure Schema SUCCESS.")
    except Exception as e:
        print(f"Manual Ensure Schema FAILED: {e}")
        traceback.print_exc()
        
    # 4. Inspect Schema After
    print(f"\n--- DB Schema After ---")
    with sqlite3.connect(db_path) as conn:
        for row in conn.execute("PRAGMA table_info(artifacts)"):
            print(row)

if __name__ == '__main__':
    inspect_dirty_state()
