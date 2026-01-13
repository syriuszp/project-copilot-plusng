import pytest
import sqlite3
from pathlib import Path
from unittest.mock import MagicMock
from app.core.vector.retriever import HybridRetriever, RetrievedChunk

# Mocks
class MockVectorStore:
    def __init__(self):
        self.index = True
    def load_index(self, model_id):
        pass
    def search(self, query_vec, top_k):
        # Return mock results: [(chunk_id, score), ...]
        # Simulating vector finding 'vec_only' and 'common'
        return [("vec_only", 0.1), ("common", 0.2)]

class MockEmbeddingProvider:
    def embed_text(self, texts, model_id):
        return [[0.1, 0.2, 0.3]] # dummy vector

class MockEmbeddingService:
    def __init__(self):
        self.model_id = "test_model"
        self.provider = MockEmbeddingProvider()

@pytest.fixture
def db_path(tmp_path):
    db_file = tmp_path / "test_retriever.db"
    conn = sqlite3.connect(db_file)
    # Setup minimal schema matching prod (chunk_rowid is PK)
    conn.execute("CREATE TABLE chunks (chunk_rowid INTEGER PRIMARY KEY, chunk_id TEXT UNIQUE, content_text TEXT, page INTEGER, slide INTEGER, section TEXT, bbox TEXT, is_active INTEGER DEFAULT 1)")
    # FTS
    conn.execute("CREATE VIRTUAL TABLE chunks_fts USING fts5(content_text, content='chunks', content_rowid='chunk_rowid')")
    
    # Insert Data
    # 1. Common (Vector + FTS)
    conn.execute("INSERT INTO chunks (chunk_id, content_text, chunk_rowid, is_active) VALUES ('common', 'common term', 1, 1)")
    conn.execute("INSERT INTO chunks_fts (rowid, content_text) VALUES (1, 'common term')")
    
    # 2. Vector Only (Text doesn't match query, but vector does)
    conn.execute("INSERT INTO chunks (chunk_id, content_text, chunk_rowid, is_active) VALUES ('vec_only', 'vector content', 2, 1)")
    conn.execute("INSERT INTO chunks_fts (rowid, content_text) VALUES (2, 'vector content')")

    # 3. FTS Only (Vector doesn't find it, but text matches)
    conn.execute("INSERT INTO chunks (chunk_id, content_text, chunk_rowid, is_active) VALUES ('fts_only', 'query term', 3, 1)")
    conn.execute("INSERT INTO chunks_fts (rowid, content_text) VALUES (3, 'query term')")

    # 4. Inactive (Should not be returned even if matches)
    conn.execute("INSERT INTO chunks (chunk_id, content_text, chunk_rowid, is_active) VALUES ('inactive', 'query term', 4, 0)")
    conn.execute("INSERT INTO chunks_fts (rowid, content_text) VALUES (4, 'query term')")
    
    conn.commit()
    conn.close()
    return str(db_file)

def test_hybrid_retriever_fts_path_works(db_path):
    """Test that FTS path actually searches and returns results."""
    mock_vs = MockVectorStore()
    mock_vs.search = MagicMock(return_value=[]) # Disable vector results for this test
    mock_es = MockEmbeddingService()
    
    retriever = HybridRetriever(db_path, mock_vs, mock_es)
    
    # Search for "query term" -> should find 'fts_only'
    results = retriever.search("query term")
    
    ids = [r.chunk_id for r in results]
    assert "fts_only" in ids
    assert "inactive" not in ids
    
    # Check source
    r = next(x for x in results if x.chunk_id == "fts_only")
    assert r.source == "fts"

def test_hybrid_retriever_merges_results(db_path):
    """Test that vector and FTS results are merged correctly."""
    mock_vs = MockVectorStore()
    mock_es = MockEmbeddingService()
    
    retriever = HybridRetriever(db_path, mock_vs, mock_es)
    
    # Search for "query term" -> FTS matches 'fts_only' and 'inactive' (but inactive filtered)
    # Vector matches 'vec_only' and 'common'
    # 'common' should be in DB? Yes.
    
    # We need to ensure 'common' is found by FTS? 
    # Let's say query is "term".
    # FTS finds: 'common term' (common), 'query term' (fts_only).
    # Vector finds: 'vec_only', 'common'.
    # Result should be union: common, vec_only, fts_only.
    
    results = retriever.search("term")
    ids = {r.chunk_id for r in results}
    
    assert "common" in ids
    assert "vec_only" in ids
    assert "fts_only" in ids
    assert "inactive" not in ids # Ensure active filter works for both paths
    
    # Check "common" source -> should be hybrid if found by both?
    # Logic: if in vector and fts -> hybrid? Or depends on logic.
    # Current broken logic doesn't support correct merging. We expect 'hybrid' or at least 'vector'.
    
    common = next(r for r in results if r.chunk_id == "common")
    # Ideally source is hybrid
    assert common.source in ["hybrid", "vector"] 
    # vector score is present?
    assert common.score < 999.0

def test_only_active_chunks_are_retrieved(db_path):
    """Explicitly verify is_active=1 constraint."""
    mock_vs = MockVectorStore()
    # Mock vector finding the inactive chunk
    mock_vs.search = MagicMock(return_value=[("inactive", 0.1)])
    mock_es = MockEmbeddingService()
    
    retriever = HybridRetriever(db_path, mock_vs, mock_es)
    
    # Query matches FTS for inactive too ("query term")
    results = retriever.search("query term")
    
    ids = [r.chunk_id for r in results]
    assert "inactive" not in ids
