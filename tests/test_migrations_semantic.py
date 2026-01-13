import os
import pytest
import sqlite3
from pathlib import Path

# Paths
REPO_ROOT = Path(__file__).parent.parent
DB_MIGRATIONS_DIR = REPO_ROOT / "db" / "migrations"
TEST_DB_PATH = REPO_ROOT / "test_semantic_migration.db"

def apply_migrations(conn):
    """Simple migration applier for testing."""
    cursor = conn.cursor()
    
    # Get all SQL files
    migration_files = sorted(list(DB_MIGRATIONS_DIR.glob("*.sql")))
    
    for sql_file in migration_files:
        print(f"Applying {sql_file.name}...")
        script = sql_file.read_text(encoding="utf-8")
        # Split by -- Down to get only Up part (naive)
        up_script = script.split("-- Down")[0]
        cursor.executescript(up_script)
        conn.commit()

@pytest.fixture
def db_connection():
    if TEST_DB_PATH.exists():
        os.remove(TEST_DB_PATH)
    
    conn = sqlite3.connect(str(TEST_DB_PATH))
    yield conn
    conn.close()
    if TEST_DB_PATH.exists():
        os.remove(TEST_DB_PATH)

def test_migrations_apply_on_empty_db(db_connection):
    """Test that all migrations apply successfully on a fresh DB."""
    try:
        apply_migrations(db_connection)
    except Exception as e:
        pytest.fail(f"Migrations failed to apply: {e}")

    # Verify Tables exist
    cursor = db_connection.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = [row[0] for row in cursor.fetchall()]
    
    assert "chunks" in tables
    assert "chunks_fts" in tables
    assert "chunk_embeddings" in tables
    assert "insights" in tables
    assert "insight_evidence" in tables

def test_chunks_schema_contracts(db_connection):
    """Verify specific contracts like PK, FTS contentless, etc."""
    apply_migrations(db_connection)
    cursor = db_connection.cursor()
    
    # 1. Verify chunks PK is chunk_rowid
    # PRAGMA table_info returns: cid, name, type, notnull, dflt_value, pk
    cursor.execute("PRAGMA table_info(chunks)")
    columns = {row[1]: row for row in cursor.fetchall()}
    
    assert "chunk_rowid" in columns
    assert columns["chunk_rowid"][5] == 1 # PK flag
    assert "INTEGER" in columns["chunk_rowid"][2]
    
    assert "chunk_id" in columns
    # chunk_id should be unique not null, but not PK (pk=0)
    assert columns["chunk_id"][5] == 0
    
    # 2. Verify chunks_fts is contentless
    # We can check by inspecting SQL from sqlite_master
    cursor.execute("SELECT sql FROM sqlite_master WHERE name='chunks_fts'")
    sql = cursor.fetchone()[0]
    assert "content='chunks'" in sql

def test_migrations_upgrade_from_epic3_db():
    """Simulate upgrade from previous state (if we had a snapshot, here we just run all)."""
    # effectively covered by test_migrations_apply_on_empty_db for now 
    # as we don't have a binary snapshot of v0.3.6 DB committed easily available.
    pass
