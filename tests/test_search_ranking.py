
import pytest
from unittest.mock import MagicMock
from app.core.vector.retriever import HybridRetriever, RetrievedChunk

def test_fts_always_ranks_above_vector():
    # Setup Mocks
    mock_vs = MagicMock()
    mock_es = MagicMock()
    
    # Mock Embedding Service to return a vector
    mock_es.embed_query.return_value = [0.1, 0.2]
    
    # Mock Vector Store to return a high-similarity match (Chunk V)
    # dist=0.0 -> score=1.0!
    mock_vs.search.return_value = [("chunk_v", 0.0)] 
    
    # Create Retriever instance
    # We strip out DB dependency by mocking internal methods if possible, 
    # but _search_fts calls DB. We should mock _search_fts.
    
    retriever = HybridRetriever("dummy.db", mock_vs, mock_es)
    
    # Mock _search_fts directly
    # Chunk F: FTS match. Raw score doesn't matter for normalization if it's the only one (returns 1.0).
    chunk_f = RetrievedChunk(
        chunk_id="chunk_f", 
        score=0.0, 
        snippet="fts match", 
        locator={}, 
        source="fts",
        fts_score_raw=10.0
    )
    retriever._search_fts = MagicMock(return_value=[chunk_f])
    
    # Mock _fetch_chunks for vector results
    chunk_v = RetrievedChunk(
        chunk_id="chunk_v", 
        score=0.0, 
        snippet="vector match", 
        locator={}, 
        source="vector"
    )
    retriever._fetch_chunks = MagicMock(return_value={"chunk_v": chunk_v})
    
    # Act
    results = retriever.search("query", top_k=5)
    
    # Assert
    assert len(results) == 2
    
    # Rank 1: FTS
    assert results[0].chunk_id == "chunk_f"
    assert results[0].source == "fts"
    # With new weighting (0.7 FTS + 0.3 Vec), FTS score might be 0.7 + 0 = 0.7 if only FTS used.
    # Current implementation ensures FTS > semantic threshold (0.3).
    # so > 0.3 is strict requirement.
    assert results[0].score >= 0.7
    
    # Rank 2: Vector
    assert results[1].chunk_id == "chunk_v"
    assert results[1].source == "semantic"
    # Max possible vector score is 0.3 * 1.0 = 0.3
    assert results[1].score <= 0.35 

    # Verify logic: Even worst FTS > Best Vector
    # If FTS raw is huge list, and this item is the WORST (norm=0)
    # score = 1.0 + 0 = 1.0.
    # Vector max = 0.3.
    # 1.0 > 0.3. Always.
