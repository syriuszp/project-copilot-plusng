
import sqlite3
import pytest
from pathlib import Path
import os

def test_all_migrations_apply_on_clean_db(tmp_path):
    """
    Audit P0 Requirement: ensure strict migration determinism.
    Verify that all .sql files in db/migrations apply successfully in order
    on a completely empty database.
    """
    db_path = tmp_path / "test.db"
    
    # Connect
    conn = sqlite3.connect(db_path)
    try:
        # Minimal bootstrap: schema_migrations if not created by first migration
        # But actually 001 usually creates tables? 
        # app.db.migrator expects schema_migrations to exist or creates it.
        # Here we simulate the migrator logic simply or just apply scripts.
        # The auditor snippet creates schema_migrations manually.
        conn.execute("CREATE TABLE IF NOT EXISTS schema_migrations (version TEXT PRIMARY KEY, applied_at TEXT DEFAULT (datetime('now')));")
        conn.commit()

        # Locate migrations
        # Assuming we run from repo root
        repo_root = Path(os.getcwd())
        migrations_dir = repo_root / "db" / "migrations"
        
        if not migrations_dir.exists():
             # Fallback for running test from inside tests/
             migrations_dir = Path("../db/migrations").resolve()
             
        assert migrations_dir.exists(), f"Migrations dir not found at {migrations_dir}"

        files = sorted(migrations_dir.glob("*.sql"))
        assert files, "No migration files found"
        
        # Verify no temp files
        for f in files:
            assert "_temp_" not in f.name, f"Found temporary migration file: {f.name}"

        # Apply in order
        for f in files:
            print(f"Applying {f.name}...")
            sql = f.read_text(encoding="utf-8").strip()
            assert sql, f"Empty migration file: {f.name}"
            
            # Execute
            conn.executescript(sql)
            
            # Record
            # Auditor's snippet used 'filename', but schema in 001/migrator might use 'version'
            # Let's check what app/db/migrator uses.
            # migrator.py: "CREATE TABLE IF NOT EXISTS schema_migrations (version TEXT PRIMARY KEY..."
            conn.execute("INSERT OR IGNORE INTO schema_migrations(version) VALUES (?)", (f.stem,))
            conn.commit()
            
    finally:
        conn.close()
