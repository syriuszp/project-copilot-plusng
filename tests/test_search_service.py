
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
    
    from app.db.migrator import ensure_schema
    ensure_schema(str(db))
        
    return str(db)

def test_search_service_contract(db_path, tmp_path):
    repo = ArtifactsRepo(db_path)
    config = {"features": {"semantic_search": False}} # Minimal mock config, disable semantic to avoid API calls
    service = SearchService(repo, config)
    
    # 1. Insert directly for speed
    meta = {"path": "/tmp/a.txt", "filename": "contract.txt", "ext": ".txt"}
    aid = repo.upsert_artifact(meta)
    
    # Populate Chunks (Required for SearchService/HybridRetriever)
    conn = sqlite3.connect(db_path)
    conn.execute("INSERT INTO chunks (chunk_id, artifact_id, index_run_id, content_text, chunk_type, hash, position_index, is_active) VALUES (?, ?, ?, ?, ?, ?, ?, ?)", 
                 ("c1", str(aid), "r1", "Contract content here.", "text", "h1", 0, 1))
    # Sync FTS (External Content Table needs manual sync if NO triggers, but triggers might exist?)
    # App defines triggers? No, Repository does it manually.
    conn.execute("INSERT INTO chunks_fts (rowid, content_text) VALUES ((SELECT chunk_rowid FROM chunks WHERE chunk_id='c1'), 'Contract content here.')")
    conn.commit()
    conn.close()
    
    # 2. Search
    results = service.search("Contract")
    
    # 3. Verify Return Type (List[SearchEvidence])
    assert isinstance(results, list)
    assert len(results) == 1
    assert isinstance(results[0], SearchEvidence)
    
    # 4. Verify Fields
    ev = results[0]
    # In SearchEvidence, we use 'artifact_id' as field name, but it comes from DB 'id'
    # Wait, check SearchEvidence model.
    assert ev.artifact_id == aid
    assert ev.source_path == "/tmp/a.txt"
    assert "Contract" in ev.snippet
    assert ev.search_mode in ["FTS", "LIKE"]

# test_fts_fallback_simulation removed: SearchService no longer falls back to repo.search_artifacts logic.

