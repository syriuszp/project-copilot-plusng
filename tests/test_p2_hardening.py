import pytest
import sqlite3
import os
from pathlib import Path
from unittest.mock import MagicMock, patch

from app.core.embeddings.service import EmbeddingService
from app.core.embeddings.repository import EmbeddingRepository
from app.core.chunking.models import Chunk

REPO_ROOT = Path(__file__).parent.parent
DB_MIGRATIONS_DIR = REPO_ROOT / "db" / "migrations"
TEST_DB_PATH = REPO_ROOT / "test_p2.db"

def apply_migrations(conn):
    cursor = conn.cursor()
    migration_files = sorted(list(DB_MIGRATIONS_DIR.glob("*.sql")))
    for sql_file in migration_files:
        script = sql_file.read_text(encoding="utf-8").split("-- Down")[0]
        cursor.executescript(script)
    conn.commit()

@pytest.fixture
def repo():
    if TEST_DB_PATH.exists():
        os.remove(TEST_DB_PATH)
    
    conn = sqlite3.connect(str(TEST_DB_PATH))
    apply_migrations(conn)
    conn.close()
    
    yield EmbeddingRepository(str(TEST_DB_PATH))
    
    if TEST_DB_PATH.exists():
        os.remove(TEST_DB_PATH)

def test_embeddings_skipped_when_existing_for_model_id(repo):
    """Test that chunks are not re-embedded if they exist for the model."""
    config = {"embeddings": {"provider": "local", "model_id": "test_model_v1"}}
    service = EmbeddingService(repo, config)
    
    # Spy on provider
    service.provider.embed_text = MagicMock(wraps=service.provider.embed_text)
    
    chunk = Chunk(
        chunk_id="chunk_1", artifact_id="a1", index_run_id="r1", 
        content_text="hello world", chunk_type="text", hash="hash_1", position_index=0
    )
    
    # Run 1: Should embed
    service.embed_chunks([chunk])
    assert service.provider.embed_text.call_count == 1
    assert repo.get_embedding_vector("chunk_1", "test_model_v1") is not None
    
    # Run 2: Should skip
    service.embed_chunks([chunk])
    assert service.provider.embed_text.call_count == 1 # Still 1
    
    # Run 3: Different chunk
    chunk2 = Chunk(
        chunk_id="chunk_2", artifact_id="a1", index_run_id="r1", 
        content_text="hello world 2", chunk_type="text", hash="hash_2", position_index=1
    )
    service.embed_chunks([chunk, chunk2])
    # Should only embed chunk 2
    assert service.provider.embed_text.call_count == 2
    
def test_embeddings_recomputed_if_model_changes(repo):
    """Test that changing model_id triggers re-embedding."""
    config = {"embeddings": {"provider": "local", "model_id": "model_A"}}
    service = EmbeddingService(repo, config)
    service.provider.embed_text = MagicMock(wraps=service.provider.embed_text)
    
    chunk = Chunk(
        chunk_id="chunk_1", artifact_id="a1", index_run_id="r1", 
        content_text="hello world", chunk_type="text", hash="hash_1", position_index=0
    )
    
    service.embed_chunks([chunk])
    assert service.provider.embed_text.call_count == 1
    
    # New Service with new model
    config_b = {"embeddings": {"provider": "local", "model_id": "model_B"}}
    service_b = EmbeddingService(repo, config_b)
    service_b.provider.embed_text = MagicMock(wraps=service_b.provider.embed_text)
    
    service_b.embed_chunks([chunk])
    assert service_b.provider.embed_text.call_count == 1 # Called for model B
    
    
    # Verify DB has both
    assert repo.get_embedding_vector("chunk_1", "model_A") is not None
    assert repo.get_embedding_vector("chunk_1", "model_B") is not None

from app.core.vector.faiss_index import VectorStore

def test_faiss_rebuild_fingerprint_logic(tmp_path):
    """Test smart rebuild logic."""
    store = VectorStore(str(tmp_path))
    store.rebuild_from_db = MagicMock()
    
    # Run 1: First time (no fingerprint) -> Rebuild
    store.upsert_or_rebuild("dummy.db", "m1", "fp_1")
    assert store.rebuild_from_db.call_count == 1
    
    # Verify fingerprint file created
    fp_path = tmp_path / "faiss_m1.fingerprint.json"
    assert fp_path.exists()
    import json
    with open(fp_path, 'r') as f:
        data = json.load(f)
        assert data['fingerprint'] == "fp_1"
        
    store.index = MagicMock() # Simulate loaded index (or just valid state)
    store.current_model_id = "m1" 
    
    # Run 2: Same fingerprint -> Skip
    store.upsert_or_rebuild("dummy.db", "m1", "fp_1")
    assert store.rebuild_from_db.call_count == 1 # Still 1
    
    # Run 3: Different fingerprint -> Rebuild
    store.upsert_or_rebuild("dummy.db", "m1", "fp_2")
    assert store.rebuild_from_db.call_count == 2
    
    with open(fp_path, 'r') as f:
        data = json.load(f)
        assert data['fingerprint'] == "fp_2"

from app.core.indexing_service import IndexingService
import logging
import json

def test_indexing_logs_have_pipeline_metrics(caplog):
    """Test that IndexingService logs metrics."""
    caplog.set_level(logging.INFO)
    
    # Mock dependencies
    config = {"paths": {"db": ":memory:", "index": "dummy"}, "indexing": {}}
    mock_artifacts_repo = MagicMock()
    mock_artifacts_repo.upsert_artifact.return_value = "art_1"
    
    # We can rely on mocked internal services if we init IndexingService mostly mocked
    # But IndexingService __init__ creates them.
    # It's better to patch the class attributes AFTER init or patch classes during init.
    
    with patch("app.core.indexing_service.ChunkingRepository"), \
         patch("app.core.indexing_service.ChunkingService"), \
         patch("app.core.indexing_service.EmbeddingRepository"), \
         patch("app.core.indexing_service.EmbeddingService"), \
         patch("app.core.indexing_service.VectorStore"), \
         patch("app.core.indexing_service.InsightRepository"), \
         patch("app.core.indexing_service.InsightEngine"):
         
         service = IndexingService(mock_artifacts_repo, config)
    
    # Mock extract
    mock_extractor = MagicMock()
    mock_extractor.extract.return_value = MagicMock(text="content")
    service.registry.get = MagicMock(return_value=mock_extractor)
    
    # Mock chunk
    service.chunk_service.process_artifact = MagicMock(return_value=[MagicMock(chunk_id="c1")])
    
    # Mock embed (returns 1 missing, 0 skipped)
    service.emb_service.embed_chunks = MagicMock(return_value=(1, 0))
    
    # Mock file existence
    with patch("os.path.exists", return_value=True), \
         patch("pathlib.Path.stat", return_value=MagicMock(st_size=100, st_mtime=123)):
         
         service.index_file("dummy.txt", "run_1")
         
    # Check logs
    assert "index_file" in caplog.text
    found_metrics = False
    for record in caplog.records:
        try:
            if "op" in record.message and "index_file" in record.message:
                data = json.loads(record.message)
                assert data["index_run_id"] == "run_1"
                assert "time_extract" in data
                assert data["embeddings_created"] == 1
                found_metrics = True
                break
        except:
            pass
            
    assert found_metrics

from app.core.vector.retriever import HybridRetriever, RetrievedChunk

def test_hybrid_ranking_is_deterministic(tmp_path):
    mock_vs = MagicMock()
    mock_es = MagicMock()
    mock_es.model_id = "m1"
    
    # DB Setup for hydration
    db_path = tmp_path / "test_rank.db"
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE chunks (chunk_rowid INTEGER PRIMARY KEY, chunk_id TEXT UNIQUE, content_text TEXT, page INTEGER, slide INTEGER, section TEXT, bbox TEXT, is_active INTEGER DEFAULT 1)")
    # Insert chunks A, B, C
    conn.execute("INSERT INTO chunks (chunk_id, content_text, is_active) VALUES ('A', 'textA', 1)")
    conn.execute("INSERT INTO chunks (chunk_id, content_text, is_active) VALUES ('B', 'textB', 1)")
    conn.execute("INSERT INTO chunks (chunk_id, content_text, is_active) VALUES ('C', 'textC', 1)")
    conn.commit()
    conn.close()
    
    retriever = HybridRetriever(str(db_path), mock_vs, mock_es)
    
    # Mock Vector Search returns A (0.1009.. to get ~0.9), C (0.1009)
    # L2 distance 0.111... -> sim = 1/(1+0.111) = 0.9. 
    # Let's just use 0.0. Sim = 1.0.
    # Use 0.25. Sim = 1/1.25 = 0.8.
    mock_es.provider.embed_text.return_value = [[0.1]]
    mock_vs.search.return_value = [("A", 0.25), ("C", 0.25)]
    mock_vs.index = True
    
    # Mock FTS Search returns B, C
    # We can mock _search_fts directly
    retriever._search_fts = MagicMock(return_value=[
        RetrievedChunk(chunk_id="B", score=999, snippet="", locator={}, source="fts"),
        RetrievedChunk(chunk_id="C", score=999, snippet="", locator={}, source="fts")
    ])
    
    results = retriever.search("q", top_k=10)
    
    # Expected scores:
    # A: Vector only. sim=0.8. Source=vector.
    # B: FTS only. sim=0.6. Source=fts.
    # C: Hybrid. max(0.8, 0.6) + 0.05 = 0.85. Source=hybrid.
    
    # Updated Expectations for Epic 4 (FTS Priority):
    # w_fts=0.7, w_vec=0.3
    # B (FTS): 0.7 * 1.0 = 0.7
    # A (Vec): 0.3 * 1.0 = 0.3
    # C (Hybrid): 0.7 + 0.3 = 1.0
    # Order: C, B, A
    
    assert len(results) == 3
    assert results[0].chunk_id == "C"
    assert results[0].source == "hybrid"
    
    assert results[1].chunk_id == "B"
    assert results[1].source == "fts"
    assert results[1].score > results[2].score
    
    assert results[2].chunk_id == "A"
    assert results[2].source == "vector"
    assert results[2].score == 0.6

from scripts.db_housekeeping import list_legacy_tables, drop_legacy_tables

def test_housekeeping_lists_legacy_tables(tmp_path):
    db_path = tmp_path / "legacy.db"
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE foo (id INT)")
    conn.execute("CREATE TABLE foo_legacy_backup (id INT)")
    conn.execute("CREATE TABLE bar_legacy_backup (id INT)")
    conn.commit()
    conn.close()
    
    tables = list_legacy_tables(str(db_path))
    assert len(tables) == 2
    assert "foo_legacy_backup" in tables
    assert "bar_legacy_backup" in tables
    assert "foo" not in tables
    
    # Test Drop Dry Run
    with patch("scripts.db_housekeeping.logger") as mock_logger:
        drop_legacy_tables(str(db_path), dry_run=True)
        # Should not drop
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        all_tables = [r[0] for r in cursor.fetchall()]
        conn.close()
        assert "foo_legacy_backup" in all_tables
        
    # Test Drop Real
    drop_legacy_tables(str(db_path), dry_run=False)
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    all_tables = [r[0] for r in cursor.fetchall()]
    conn.close()
    assert "foo_legacy_backup" not in all_tables
    assert "foo" in all_tables
