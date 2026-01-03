
import pytest
import os
import sqlite3
from pathlib import Path
from app.core.artifacts_repo import ArtifactsRepo
from app.core.indexing_service import IndexingService

@pytest.fixture
def db_path(tmp_path):
    # Setup a temp DB
    db = tmp_path / "test.db"
    # Create tables via SQL script execution or Repo init if logic is there?
    # Repo init creates FTS, but regular tables come from migration.
    # We must init tables. 
    # Can we import SQL? Or hardcode minimal schema here?
    # Better to read the migration file.
    migration_path = Path("db/migrations/002_create_artifacts_tables.sql")
    if not migration_path.exists():
        pytest.fail("Migration file not found")
        
    with sqlite3.connect(db) as conn:
        with open(migration_path, "r") as f:
            script = f.read()
            conn.executescript(script)
            
    return str(db)

@pytest.fixture
def repo(db_path):
    return ArtifactsRepo(db_path)

@pytest.fixture
def indexer(repo):
    return IndexingService(repo)

def test_index_plain_text(indexer, repo, tmp_path):
    # Create dummy file
    f = tmp_path / "hello.txt"
    f.write_text("Hello World Content", encoding="utf-8")
    
    status = indexer.index_file(str(f))
    assert status == "indexed"
    
    # Verify DB
    res = repo.search_artifacts("Hello")
    assert len(res) == 1
    assert res[0]['filename'] == "hello.txt"
    # Snippet might have markup e.g. **Hello**
    snippet = res[0].get('snippet', '')
    assert "Hello" in snippet and "Content" in snippet
    
    # Check text content in artifact_text
    with repo._get_conn() as conn:
        row = conn.execute("SELECT text FROM artifact_text").fetchone()
        assert row[0] == "Hello World Content"

def test_index_all_counts(indexer, tmp_path):
    (tmp_path / "1.txt").write_text("A")
    (tmp_path / "2.txt").write_text("B")
    
    stats = indexer.index_all(str(tmp_path))
    assert stats['indexed'] == 2

