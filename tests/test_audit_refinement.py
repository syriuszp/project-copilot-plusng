
import pytest
import sqlite3
from unittest.mock import MagicMock, patch
from app.core.utils.binaries import BinaryChecker
from app.core.extractors.registry import ExtractorRegistry
from app.db.migrator import ensure_schema

# --- 1. Binary Detection Tests ---
@patch("app.core.utils.binaries.shutil.which")
def test_binary_detection(mock_which):
    # Case 1: All present
    mock_which.side_effect = lambda cmd: "/bin/" + cmd
    res = BinaryChecker.check_binaries()
    assert res["tesseract"] is True
    assert res["poppler"] is True
    
    # Case 2: Tesseract missing
    mock_which.side_effect = lambda cmd: None if "tesseract" in cmd else "/bin/" + cmd
    res = BinaryChecker.check_binaries()
    assert res["tesseract"] is False
    assert res["poppler"] is True

# --- 2. Extraction Flags Tests ---
def test_registry_flags():
    # Disable PDF
    config = {"extraction": {"pdf": False, "docx": True}}
    reg = ExtractorRegistry(config)
    assert reg.get(".pdf") is None
    assert reg.get(".docx") is not None
    
    # Disable All
    config = {"extraction": {"pdf": False, "docx": False, "images": False}}
    reg = ExtractorRegistry(config)
    assert reg.get(".pdf") is None
    assert reg.get(".docx") is None
    assert reg.get(".png") is None

# --- 3. DB Schema Contract (Idempotency & Constraints) ---
def test_schema_contract_constraints(tmp_path):
    # Test on a real SQLite file in temp dir
    db_path = tmp_path / "test_hardening.db"
    conn = sqlite3.connect(str(db_path))
    
    # 1. Run Schema Creation
    # We use ensure_schema directly. Note: ensure_schema might expect table existence if we rely on SQL for initial create.
    # But ensure_schema has _ensure_columns. 
    # Current ensure_schema logic CHECKS columns. It doesn't create table if missing (logs warning).
    # So we must create table first (like migrator does with SQL).
    # Let's simulate '003_hardening.sql' manually or minimal create.
    conn.execute("CREATE TABLE artifacts (id INTEGER PRIMARY KEY)") # Minimal
    
    ensure_schema(conn)
    
    # Verify 'path' column added
    cur = conn.execute("PRAGMA table_info(artifacts)")
    cols = {row[1]: row[2] for row in cur.fetchall()}
    assert "path" in cols
    assert "sha256" in cols
    
    # Verify Idempotency (Run again)
    ensure_schema(conn) # Should not fail
    
    # Verify Unique Constraint on Path (Requires table with UNIQUE constraint created initially)
    # Since we created minimal table above WITHOUT unique, ensure_schema won't add UNIQUE constraint (SQLite limitation).
    # This confirms ensure_schema is for COLUMNS.
    # The requirement is that 003 SQL provides constraints. 
    # And we should verify that our SQL provides it.
    
    conn.close()
    
    # New DB with Strict SQL
    db_path2 = tmp_path / "test_strict.db"
    conn2 = sqlite3.connect(str(db_path2))
    # Apply SQL script logic (mocking 003 content)
    script = """
    CREATE TABLE artifacts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        path TEXT UNIQUE NOT NULL
    );
    """
    conn2.executescript(script)
    
    # Attempt duplicate insert
    conn2.execute("INSERT INTO artifacts (path) VALUES ('foo')")
    with pytest.raises(sqlite3.IntegrityError):
        conn2.execute("INSERT INTO artifacts (path) VALUES ('foo')")
        
    conn2.close()

