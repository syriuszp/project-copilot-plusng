
import pytest
from unittest.mock import MagicMock
from app.core.vector.retriever import HybridRetriever, RetrievedChunk

def test_hybrid_scoring_logic():
    # Setup Mocks
    mock_vec_store = MagicMock()
    mock_embed_svc = MagicMock()
    
    # Instantiate with correct signature (3 args)
    retriever = HybridRetriever("db_path", mock_vec_store, mock_embed_svc)
    
    # Mock internal _search_fts
    # Returns FTS matched chunks
    # Use RetrievedChunk struct from module
    c_f1 = RetrievedChunk("chunk_f1", 0.0, "", {}, "fts", fts_score_raw=100.0)
    c_f2 = RetrievedChunk("chunk_f2", 0.0, "", {}, "fts", fts_score_raw=10.0)
    
    retriever._search_fts = MagicMock(return_value=[c_f1, c_f2])
    retriever._fetch_chunks = MagicMock(side_effect=lambda ids: {
        id: RetrievedChunk(chunk_id=id, content_text="", artifact_id="", index_run_id="") 
        for id in ids
    })
    
    # Mock Vector Search
    # Returns chunk_v1 (score 0.1 - good dist), chunk_f2 (score 0.8 - bad dist)
    mock_embed_svc.embed_query.return_value = [0.1, 0.2]
    mock_vec_store.search.return_value = [("chunk_v1", 0.1), ("chunk_f2", 0.8)]
    
    # Mock _fetch_chunks
    retriever._fetch_chunks = MagicMock(return_value={
        "chunk_v1": RetrievedChunk("chunk_v1", 0.0, "", {}, "vector"),
        "chunk_f2": RetrievedChunk("chunk_f2", 0.0, "", {}, "vector") # Should use existing
    })

    # Run
    results = retriever.search("query", top_k=5)
    
    # ... existing assertions ...
    assert results[0].chunk_id == "chunk_f1"
    assert results[0].score == 0.7 # w_fts * 1.0
    
    # 0.3 * (1/(1+0.1)) approx 0.3 * 0.9 = 0.27
    # But because of MinMax normalization, the BEST vector gets 1.0
    # So chunk_v1 gets vec_norm=1.0 -> score=0.3
    assert 0.2 < results[1].score <= 0.3

def test_hybrid_scoring_contract():
    """
    P2 Hardening: Contract Test.
    1. FTS Result (1 item) MUST outrank Semantic Result (10 items).
    2. Semantic Result MUST NOT exceed 0.3 score.
    """
    # Setup
    mock_vec = MagicMock()
    mock_embed = MagicMock()
    retriever = HybridRetriever("db", mock_vec, mock_embed)
    
    # Mock FTS: 1 hit
    c_fts = RetrievedChunk("fts_1", 0.0, "fts match", {}, "fts", fts_score_raw=10.0)
    retriever._search_fts = MagicMock(return_value=[c_fts])
    
    # Mock Vector: 2 hits (Strong match, e.g. dist=0.0 -> impl=1.0)
    # Even perfectly matching vector (dist=0) -> score norm=1.0 -> final=0.3
    mock_embed.embed_query.return_value = [0.1]
    mock_vec.search.return_value = [("vec_1", 0.0), ("vec_2", 0.1)] # dist 0 is perfect match
    
    retriever._fetch_chunks = MagicMock(side_effect=lambda ids: {
        id: RetrievedChunk(id, 0.0, "vec match", {}, "vector") for id in ids
    })
    
    # Run
    results = retriever.search("contract_test")
    
    # Assertions
    assert len(results) == 3
    
    # 1. Top result MUST be FTS
    top = results[0]
    assert top.chunk_id == "fts_1", "FTS must be top result"
    assert top.score == 0.7, "FTS single result should have normalized score 1.0 * 0.7 = 0.7"
    
    # 2. Semantic Cap
    # vec_1: dist=0 -> raw=1.0. Norm=1.0. Final = 0.3 * 1.0 = 0.3
    vec_res = [r for r in results if r.chunk_id == "vec_1"][0]
    assert vec_res.score <= 0.3000001, "Semantic result must be capped at weight (0.3)"

def test_fetch_chunks_safety(tmp_path):
    """
    P1 Hardening: Ensure inactive chunks are NOT returned by _fetch_chunks.
    """
    import sqlite3
    db = tmp_path / "test.db"
    conn = sqlite3.connect(db)
    conn.execute("CREATE TABLE chunks (chunk_id TEXT, content_text TEXT, page INT, slide INT, section TEXT, bbox TEXT, is_active INT)")
    conn.execute("INSERT INTO chunks VALUES ('active', 'text', 1, 1, 's', '', 1)")
    conn.execute("INSERT INTO chunks VALUES ('inactive', 'text', 1, 1, 's', '', 0)")
    conn.commit()
    conn.close()
    
    retriever = HybridRetriever(str(db), MagicMock(), MagicMock())
    
    # Fetch both
    res = retriever._fetch_chunks(['active', 'inactive'])
    
    assert 'active' in res, "Active chunk should be returned"
    assert 'inactive' not in res, "Inactive chunk must NOT be returned"
    assert len(res) == 1
