
import sqlite3
import pytest
from pathlib import Path
from app.db.migrator import ensure_schema

@pytest.fixture
def legacy_db_path(tmp_path):
    """
    Creates a 'legacy' database that violates the new contract.
    - artifacts table without UNIQUE(path)
    - Missing sha256
    - Missing index_runs
    """
    db = tmp_path / "legacy_schema.db"
    
    with sqlite3.connect(str(db)) as conn:
        # Old artifacts (no unique path, simple schema)
        conn.execute("""
            CREATE TABLE artifacts (
                id INTEGER PRIMARY KEY,
                path TEXT NOT NULL,
                filename TEXT,
                ext TEXT,
                size_bytes INTEGER,
                modified_at REAL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        # Insert duplicate paths to simulate legacy data issue
        conn.execute("INSERT INTO artifacts (path, filename) VALUES ('/dup', 'f1')")
        conn.execute("INSERT INTO artifacts (path, filename) VALUES ('/dup', 'f2')")
        
        # Old artifact_text (maybe missing FK action)
        conn.execute("""
            CREATE TABLE artifact_text (
                artifact_id INTEGER,
                text TEXT
            )
        """)
        
    return str(db)

def test_upgrade_enforces_contract(legacy_db_path):
    """
    Verifies that running ensure_schema/init_db on a legacy DB
    results in a strict schema compliant with the contract.
    """
    db_path = legacy_db_path
    
    # 1. Run Upgrade (which might rebuild DB in current implementation)
    ensure_schema(db_path)
    
    # 2. Verify Contract
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        
        # A. Unique Path
        # Check via PRAGMA index_list or just try to insert duplicate
        try:
            conn.execute("INSERT INTO artifacts (path) VALUES ('/unique_test')")
            conn.execute("INSERT INTO artifacts (path) VALUES ('/unique_test')")
            pytest.fail("Should raise IntegrityError for duplicate persistence")
        except sqlite3.IntegrityError:
            pass # Expected
            
        # B. Columns Existence
        cols = {r[1] for r in conn.execute("PRAGMA table_info(artifacts)")}
        assert "sha256" in cols, "Missing sha256 in artifacts"
        
        # C. artifact_text PK/FK
        at_info = conn.execute("PRAGMA table_info(artifact_text)").fetchall()
        pk_col = next((r for r in at_info if r[1] == 'artifact_id'), None)
        assert pk_col and pk_col[5] == 1, "artifact_id should be PK in artifact_text"
        
        fks = conn.execute("PRAGMA foreign_key_list(artifact_text)").fetchall()
        # Look for ON DELETE CASCADE
        has_cascade = any(fk[2] == 'artifacts' and fk[6] == 'CASCADE' for fk in fks)
        assert has_cascade, "artifact_text missing ON DELETE CASCADE FK"
        
        # D. index_runs existence
        ir_tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='index_runs'").fetchall()
        assert len(ir_tables) == 1, "index_runs table missing"
        
        ir_cols = {r[1] for r in conn.execute("PRAGMA table_info(index_runs)")}
        expected_cols = {
            "run_id", "started_at", "ended_at", "env", "ingest_dir",
            "files_seen", "files_indexed", "files_failed", "fts_enabled"
        }
        assert expected_cols.issubset(ir_cols), f"Missing cols in index_runs: {expected_cols - ir_cols}"

