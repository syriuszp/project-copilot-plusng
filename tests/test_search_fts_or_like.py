
import pytest
import sqlite3
from pathlib import Path
from app.core.artifacts_repo import ArtifactsRepo

@pytest.fixture
def db_path(tmp_path):
    db = tmp_path / "test_search.db"
    # Init schema
    from app.db.migrator import ensure_schema
    with sqlite3.connect(db) as conn:
        ensure_schema(conn)
    return str(db)

def test_search_fts_default(db_path):
    # Repo init -> should enable FTS if sqlite supports it (github actions usually does)
    repo = ArtifactsRepo(db_path)
    
    # Insert data via repo internal or raw
    # Need to simulate indexing (populating artifacts + artifact_text + fts)
    meta = {"path": "/tmp/a.txt", "filename": "a.txt", "ext": ".txt"}
    aid = repo.upsert_artifact(meta)
    repo.save_extracted_text(aid, "UniqueKeyword in text", "Plain", 20, "a.txt", "/tmp/a.txt")
    
    # Search
    results = repo.search_artifacts("UniqueKeyword")
    assert len(results) == 1
    assert results[0]['filename'] == "a.txt"
    # If FTS is on, snippet might be returned.
    
def test_search_like_fallback(db_path, monkeypatch):
    # Force disable FTS
    def mock_init(self):
        self._fts_enabled = False
        
    monkeypatch.setattr(ArtifactsRepo, '_check_and_init_fts', mock_init)
    
    repo = ArtifactsRepo(db_path)
    assert not repo.fts_enabled
    
    # Insert data
    meta = {"path": "/tmp/b.txt", "filename": "fallback.txt", "ext": ".txt"}
    aid = repo.upsert_artifact(meta)
    repo.save_extracted_text(aid, "Some content for like", "Plain", 20, "fallback.txt", "/tmp/b.txt")
    
    # Search LIKE
    results = repo.search_artifacts("content")
    assert len(results) == 1
    assert results[0]['filename'] == "fallback.txt"
