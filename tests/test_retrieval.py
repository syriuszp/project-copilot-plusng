import pytest
import sqlite3
import os
import shutil
import json
import numpy as np
from pathlib import Path
from unittest.mock import MagicMock

from app.core.vector.faiss_index import VectorStore
from app.core.vector.retriever import HybridRetriever
from app.core.chunking.models import Chunk
from app.core.chunking.service import ChunkingService
from app.core.chunking.repository import ChunkingRepository
from app.core.embeddings.service import EmbeddingService
from app.core.embeddings.repository import EmbeddingRepository

# Helpers
REPO_ROOT = Path(__file__).parent.parent
DB_MIGRATIONS_DIR = REPO_ROOT / "db" / "migrations"
TEST_DB_PATH = REPO_ROOT / "test_retrieval.db"
TEST_INDEX_DIR = REPO_ROOT / "test_indices"

def apply_migrations(conn):
    cursor = conn.cursor()
    migration_files = sorted(list(DB_MIGRATIONS_DIR.glob("*.sql")))
    for sql_file in migration_files:
        script = sql_file.read_text(encoding="utf-8").split("-- Down")[0]
        cursor.executescript(script)
    conn.commit()

@pytest.fixture
def env(tmp_path):
    # Use Pytest tmp_path for isolation instead of fixed root paths
    db_path = tmp_path / "test_retrieval.db"
    index_dir = tmp_path / "test_indices"
    
    # Initialize Schema
    conn = sqlite3.connect(str(db_path))
    apply_migrations(conn)
    conn.close()
    
    yield {
        "db": str(db_path),
        "index": str(index_dir)
    }

def setup_data(env_paths, chunks_data, embeddings_data, model_id="m1"):
    """Populates DB with chunks and embeddings."""
    repo = ChunkingRepository(env_paths["db"])
    emb_repo = EmbeddingRepository(env_paths["db"])
    
    # 1. Chunks
    for c in chunks_data:
        rid = repo.upsert_chunk(c)
        c.chunk_rowid = rid
        repo.sync_fts_for_chunk(rid, c.content_text, c.is_active)
        
    # 2. Embeddings
    upsert = []
    for i, c in enumerate(chunks_data):
        if c.chunk_id in embeddings_data:
            upsert.append({
                "chunk_id": c.chunk_id,
                "model_id": model_id,
                "dim": len(embeddings_data[c.chunk_id]),
                "vector": embeddings_data[c.chunk_id]
            })
    emb_repo.upsert_embeddings(upsert)
    
    return repo, emb_repo

def test_faiss_index_isolated_by_model_id(env):
    """Test that indices are saved separately for different model_ids."""
    store = VectorStore(env["index"])
    
    # Mock data directly into DB not needed for unit test of _get_paths logic, 
    # but needed for rebuild_from_db.
    
    # Let's populate DB
    c1 = Chunk("c1", "a1", "r1", "text", "text", "h1", 0, is_active=1)
    e1 = [0.1, 0.1]
    setup_data(env, [c1], {"c1": e1}, "model_A")
    setup_data(env, [], {}, "model_B") # No data for model B
    
    # Rebuild A
    store.rebuild_from_db(env["db"], "model_A")
    assert (Path(env["index"]) / "faiss_model_A.index").exists()
    assert (Path(env["index"]) / "faiss_model_A.mapping.json").exists()
    
    # Rebuild B (empty)
    store.rebuild_from_db(env["db"], "model_B")
    # Should create empty artifacts or nothing? Implementation checks for rows.
    # Logic: if not rows: self.index=None, _save_index.
    # _save_index checks if self.index. So nothing created if empty.
    assert not (Path(env["index"]) / "faiss_model_B.index").exists() 

def test_only_active_chunks_are_retrieved(env):
    """Test Hybrid Retriever respects is_active=1."""
    # Data:
    # c1: Active, matches "Apple", vector near query
    # c2: Inactive, matches "Apple", vector near query
    
    c1 = Chunk("c1", "a1", "r1", "Apple Pie", "text", "h1", 0, is_active=1)
    c2 = Chunk("c2", "a1", "r0", "Apple Tart", "text", "h2", 0, is_active=0)
    
    # Vectors (2D)
    # Query: [1, 0]
    # c1: [0.9, 0.1] (Close)
    # c2: [0.9, 0.1] (Close)
    vectors = {"c1": [0.9, 0.1], "c2": [0.9, 0.1]}
    
    setup_data(env, [c1, c2], vectors, "m1")
    
    # Setup Components
    vstore = VectorStore(env["index"])
    vstore.rebuild_from_db(env["db"], "m1")
    
    # Mock Embedding Service to return Query Vector
    emb_svc = MagicMock()
    emb_svc.model_id = "m1"
    emb_svc.provider.embed_text.return_value = [[1.0, 0.0]] 
    emb_svc.embed_query.return_value = [1.0, 0.0]
    
    retriever = HybridRetriever(env["db"], vstore, emb_svc)
    
    # Search
    results = retriever.search("Apple", top_k=5)
    
    ids = [r.chunk_id for r in results]
    assert "c1" in ids
    assert "c2" not in ids

def test_retrieval_returns_locator_fields(env):
    """Test response objects contain page/slide info."""
    c1 = Chunk("c1", "a1", "r1", "Content", "text", "h1", 0, page=5, slide=10, is_active=1)
    vectors = {"c1": [0.1]}
    setup_data(env, [c1], vectors, "m1")
    
    vstore = VectorStore(env["index"])
    vstore.rebuild_from_db(env["db"], "m1")
    
    emb_svc = MagicMock()
    emb_svc.model_id = "m1"
    emb_svc.provider.embed_text.return_value = [[0.1]]
    
    retriever = HybridRetriever(env["db"], vstore, emb_svc)
    results = retriever.search("Content", top_k=1)
    
    assert len(results) == 1
    loc = results[0].locator
    assert loc['page'] == 5
    assert loc['slide'] == 10
