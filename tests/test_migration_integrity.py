import pytest
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
DB_MIGRATIONS_DIR = REPO_ROOT / "db" / "migrations"

def test_migration_files_have_no_placeholders():
    """
    Scans all .sql files in db/migrations/ and fails if any line
    is exactly '...' or contains '...' as a placeholder.
    """
    migration_files = sorted(list(DB_MIGRATIONS_DIR.glob("*.sql")))
    
    for sql_file in migration_files:
        content = sql_file.read_text(encoding="utf-8")
        lines = content.splitlines()
        
        for i, line in enumerate(lines):
            stripped = line.strip()
            # Auditor requirement: strictly fail on "..."
            if stripped == "..." or " ..." in line or "... " in line:
                # Allow comments? Maybe, but usually placeholders in SQL are visible.
                # The auditor said: "failuje jeśli znajdzie linię równą ... albo zawierającą ... jako placeholder"
                # We'll be strict.
                pytest.fail(f"Found placeholder '...' in {sql_file.name} at line {i+1}: {line}")
