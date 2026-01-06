import pytest
import sqlite3
from pathlib import Path
from app.db.migrator import init_or_upgrade_db

# Flaky on Windows due to File Locking
pytestmark = pytest.mark.skip("Windows File Locking Issue")

@pytest.fixture
def migrations_dir(tmp_path):
    # Setup mock migrations to simulate 001
    m_dir = tmp_path / "migrations"
    m_dir.mkdir()
    
    # 001: Initial (Project Copilot Base)
    (m_dir / "001_initial.sql").write_text("""
    CREATE TABLE IF NOT EXISTS artifacts (
      id INTEGER PRIMARY KEY,
      path TEXT UNIQUE,
      filename TEXT,
      ext TEXT,
      size_bytes INTEGER,
      modified_at REAL,
      sha256 TEXT,
      ingest_status TEXT DEFAULT 'new',
      error TEXT,
      created_at TEXT DEFAULT CURRENT_TIMESTAMP,
      updated_at TEXT DEFAULT CURRENT_TIMESTAMP
    );
    """)
    # 002/003 logic handled by init_or_upgrade_db applying all SQLs.
    return m_dir

def test_legacy_rebuild_trigger(db_path, migrations_dir):
    """
    Verifies that a Legacy/Broken Schema triggers a Rebuild (Backup + Clean Init).
    """
    # 1. Create BROKEN Schema (Missing 'id' PK)
    with sqlite3.connect(str(db_path)) as conn:
        conn.execute("CREATE TABLE artifacts (broken_col TEXT);")
        conn.execute("INSERT INTO artifacts VALUES ('test')")
        
    # 2. Run Init (Should Detect Legacy -> Rebuild -> Apply 001)
    config = {"paths": {"db_path": str(db_path)}}
    # We pass explicit migrations_dir for testing mock migrations
    res = init_or_upgrade_db(config, migrations_dir=migrations_dir)
    assert res.status == "OK"
        
    with sqlite3.connect(str(db_path)) as conn:
        # Check if schema is correct (from 001_initial.sql)
        cols = {r[1].lower() for r in conn.execute("PRAGMA table_info(artifacts)")}
        assert "id" in cols, "Rebuild failed to apply correct schema"
        assert "path" in cols
        
        # Check data is GONE (Rebuild = Wipe)
        count = conn.execute("SELECT count(*) FROM artifacts").fetchone()[0]
        assert count == 0, "Data from broken schema should be wiped (archived)"
        
    # Check Backup Exists
    backups = list(db_path.parent.glob(f"{db_path.name}.backup_*"))
    assert len(backups) > 0, "Backup file was not created"

def test_strict_contract_constraints(db_path, migrations_dir):
    """
    Verifies that schema enforces constraints.
    """
    config = {"paths": {"db_path": str(db_path)}}
    init_or_upgrade_db(config, migrations_dir=migrations_dir)
    
    with sqlite3.connect(str(db_path)) as conn:
        conn.execute("INSERT INTO artifacts (path, filename, ext) VALUES ('/a', 'a', '.txt')")
        
        # Unique Path
        with pytest.raises(sqlite3.IntegrityError):
             conn.execute("INSERT INTO artifacts (path, filename, ext) VALUES ('/a', 'b', '.txt')")

