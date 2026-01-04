
import pytest
import sqlite3
from pathlib import Path
from app.db.migrator import init_or_upgrade_db, ensure_schema

@pytest.fixture
def db_path(tmp_path):
    return tmp_path / "test_hardening.db"

@pytest.fixture
def migrations_dir():
    # Helper to point to real migrations or mock them
    return Path("db/migrations")

def test_fresh_db_initialization(db_path, migrations_dir):
    """
    Verifies that a fresh DB is initialized with all tables and columns.
    """
    init_or_upgrade_db(db_path, migrations_dir)
    
    with sqlite3.connect(str(db_path)) as conn:
        cursor = conn.cursor()
        
        # Check tables
        tables = [r[0] for r in cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")]
        assert "artifacts" in tables
        assert "artifact_text" in tables
        assert "index_runs" in tables
        assert "schema_migrations" in tables
        
        # Check columns in artifacts
        cols = {r[1] for r in cursor.execute("PRAGMA table_info(artifacts)")}
        assert "ingest_status" in cols
        assert "sha256" in cols
        
        # Check columns in index_runs
        cols = {r[1] for r in cursor.execute("PRAGMA table_info(index_runs)")}
        assert "files_not_extractable" in cols
        assert "env" in cols

def test_idempotent_upgrade(db_path, migrations_dir):
    """
    Verifies that ensure_schema adds missing columns to an existing DB.
    """
    # 1. Create a partial DB manually (simulating old state)
    with sqlite3.connect(str(db_path)) as conn:
        conn.execute("CREATE TABLE artifacts (id INTEGER PRIMARY KEY, path TEXT)")
        conn.execute("CREATE TABLE artifact_text (artifact_id INTEGER PRIMARY KEY, text TEXT)")
        # index_runs missing completely
    
    # 2. Run upgrade
    # Note: apply_sql_migrations might fail if we manually created tables that SQL tries to create without IF NOT EXISTS?
    # But our SQL uses CREATE TABLE IF NOT EXISTS.
    # However, SQL 003 expects to run if not in schema_migrations.
    # If we are simulating "clean state" but old schema, we might have issues if 003 runs.
    # But ensure_schema is the key.
    
    # Let's mock migrations_dir to be empty or just pretend 003 is applied?
    # If we run init_or_upgrade_db with real migrations, 001/002/003 will run.
    # 003 uses IF NOT EXISTS, so it shouldn't fail on table existence.
    # But it won't add columns if table exists! (SQLite CREATE TABLE IF NOT EXISTS doesn't alter).
    # ensure_schema is what adds columns.
    
    init_or_upgrade_db(db_path, migrations_dir)
    
    with sqlite3.connect(str(db_path)) as conn:
        # Check if ensure_schema added columns
        cols = {r[1] for r in conn.execute("PRAGMA table_info(artifacts)")}
        assert "ingest_status" in cols # Added by ensure_schema
        assert "sha256" in cols
        
        # Check index_runs created (by SQL or ensure_schema? ensure_schema logs warning if missing)
        # SQL 003 should have created it because it didn't exist.
        tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")]
        assert "index_runs" in tables

def test_schema_contract_index_runs(db_path, migrations_dir):
    """
    Verifies that code can insert into index_runs (contract test).
    """
    init_or_upgrade_db(db_path, migrations_dir)
    
    with sqlite3.connect(str(db_path)) as conn:
        conn.execute("""
            INSERT INTO index_runs (
                run_id, started_at, ended_at, env, ingest_dir, 
                files_seen, files_indexed, files_failed, files_not_extractable, fts_enabled
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            "test-run", "now", "later", "TEST", "/tmp", 
            1, 1, 0, 0, 1
        ))
        conn.commit()
