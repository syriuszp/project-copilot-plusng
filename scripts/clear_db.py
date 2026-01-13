import sqlite3
import os
import sys

# Ensure app module is visible (scripts are run from root)
sys.path.append(os.getcwd())

from app.ui.config_loader import load_config

def clear_database():
    cfg = load_config()
    db_path = cfg.get("db_path")
    
    # Fallback to default if not set
    if not db_path:
        db_path = "data/project_copilot.db"
        
    print(f"Resolving DB Path... ENV={cfg.get('env')}")
    print(f"Target DB: {db_path}")

    if not os.path.exists(db_path):
        print(f"Database not found at {db_path}")
        return

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Disable FK constraints to allow deletion in any order
    cursor.execute("PRAGMA foreign_keys = OFF;")
    
    # Get all tables
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';")
    tables = [r[0] for r in cursor.fetchall()]
    
    print(f"Found {len(tables)} tables: {tables}")
    
    for table in tables:
        if table == "schema_migrations":
            print(f"Skipping metadata table: {table}")
            continue
            
        print(f"Clearing table: {table}")
        try:
            cursor.execute(f"DELETE FROM {table};")
        except Exception as e:
            print(f"Error clearing {table}: {e}")
            
    # Verify
    print("\nVerifying counts:")
    for table in tables:
        count = cursor.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        print(f"{table}: {count}")
    
    # Vacuum to reset auto-increments and reclaim space
    conn.commit() # Commit deletions first
    print("\nVacuuming...")
    
    # VACUUM cannot be in transaction. Set isolation level to autocommit for this op.
    old_iso = conn.isolation_level
    conn.isolation_level = None
    cursor.execute("VACUUM;")
    conn.isolation_level = old_iso
    
    print("\nDatabase cleared successfully.")

if __name__ == "__main__":
    clear_database()
