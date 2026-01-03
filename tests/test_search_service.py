
import pytest
import sqlite3
from pathlib import Path
from app.core.search.service import SearchService
from app.core.artifacts_repo import ArtifactsRepo
from app.core.search.models import SearchEvidence

@pytest.fixture
def db_path(tmp_path):
    # Setup a temp DB
    db = tmp_path / "service_test.db"
    # Basic schema
    with sqlite3.connect(db) as conn:
        with open("db/migrations/002_create_artifacts_tables.sql", "r") as f:
            script = f.read()
            conn.executescript(script)
    return str(db)

def test_search_service_contract(db_path, tmp_path):
    repo = ArtifactsRepo(db_path)
    service = SearchService(repo)
    
    # 1. Insert directly for speed
    meta = {"path": "/tmp/a.txt", "filename": "contract.txt", "ext": ".txt"}
    aid = repo.upsert_artifact(meta)
    repo.save_extracted_text(aid, "Contract content here.", "Plain", 20, "contract.txt", "/tmp/a.txt")
    
    # 2. Search
    results = service.search("Contract")
    
    # 3. Verify Return Type (List[SearchEvidence])
    assert isinstance(results, list)
    assert len(results) == 1
    assert isinstance(results[0], SearchEvidence)
    
    # 4. Verify Fields
    ev = results[0]
    assert ev.artifact_id == aid
    assert ev.source_path == "/tmp/a.txt"
    assert "Contract" in ev.snippet
    assert ev.search_mode in ["FTS", "LIKE"]

def test_fts_fallback_simulation(db_path, monkeypatch):
    """
    Simulate FTS failure/unavailability and ensure LIKE works via Service.
    """
    # Force disable FTS on repo
    def mock_init_no_fts(self):
        self._fts_enabled = False
    
    monkeypatch.setattr(ArtifactsRepo, '_check_and_init_fts', mock_init_no_fts)
    
    repo = ArtifactsRepo(db_path)
    assert not repo.fts_enabled # Fallback active
    
    service = SearchService(repo)
    
    # Insert data
    meta = {"path": "/tmp/fallback.txt", "filename": "fallback.txt", "ext": ".txt"}
    aid = repo.upsert_artifact(meta)
    repo.save_extracted_text(aid, "Some fallback content.", "Plain", 20, "fallback.txt", "/tmp/fallback.txt")
    
    # Search
    results = service.search("content") # Should match via LIKE
    
    assert len(results) == 1
    ev = results[0]
    assert ev.search_mode == "LIKE"
    # Model doesn't have filename, checking path
    assert "fallback.txt" in ev.source_path
    assert ev.source_path == "/tmp/fallback.txt"

