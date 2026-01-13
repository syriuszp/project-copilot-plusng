import pytest
import sqlite3
import os
import json
from pathlib import Path
from unittest.mock import patch, MagicMock

from app.core.embeddings.service import EmbeddingService
from app.core.embeddings.repository import EmbeddingRepository
from app.core.embeddings.providers.gemini_provider import GeminiEmbeddingProvider
from app.core.chunking.models import Chunk

REPO_ROOT = Path(__file__).parent.parent
DB_MIGRATIONS_DIR = REPO_ROOT / "db" / "migrations"
TEST_DB_PATH = REPO_ROOT / "test_embeddings.db"

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

def test_gemini_provider_requires_api_key():
    """Test that Gemini provider raises Error without env var or secret file."""
    # Ensure no ENV
    with patch.dict(os.environ, {}, clear=True):
        # Ensure no secrets file (mock open)
        with patch("pathlib.Path.exists", return_value=False):
            with pytest.raises(ValueError, match="Missing GEMINI_API_KEY"):
                GeminiEmbeddingProvider()

def test_provider_selection_defaults_to_gemini():
    """Test Service config logic."""
    repo_mock = MagicMock()
    
    # 1. Default config -> tries Gemini -> Fails if no key (fail_closed=True default)
    with patch.dict(os.environ, {}, clear=True), \
         patch("app.core.embeddings.providers.gemini_provider.GeminiEmbeddingProvider._load_api_key", side_effect=ValueError("No Key")):
         
         config = {"embeddings": {"provider": "gemini", "fail_closed": True}}
         with pytest.raises(RuntimeError, match="Gemini Provider failed to init"):
             EmbeddingService(repo_mock, config)

    # 2. Config Local -> LocalProvider
    config = {"embeddings": {"provider": "local"}}
    service = EmbeddingService(repo_mock, config)
    assert service.provider.__class__.__name__ == "LocalEmbeddingProvider"

def test_embeddings_recomputed_if_model_id_changes(repo):
    """Test idempotency vs model ID change."""
    # Setup Service with Local Provider
    config = {"embeddings": {"provider": "local", "model_id": "model_v1"}}
    service = EmbeddingService(repo, config)
    
    chunk = Chunk(
        chunk_id="hash_123", artifact_id="a1", index_run_id="r1", 
        content_text="text", chunk_type="text", hash="hash_123", position_index=0
    )
    
    # Run 1: Embed with model_v1
    service.embed_chunks([chunk])
    
    # Verify DB has model_v1
    assert repo.get_embedding_vector("hash_123", "model_v1") is not None
    assert repo.get_embedding_vector("hash_123", "model_v2") is None
    
    # Run 2: Same chunk, New Model ID
    config_v2 = {"embeddings": {"provider": "local", "model_id": "model_v2"}}
    service_v2 = EmbeddingService(repo, config_v2)
    
    service_v2.embed_chunks([chunk])
    
    # Verify DB has BOTH (or just verify v2 present)
    assert repo.get_embedding_vector("hash_123", "model_v1") is not None
    assert repo.get_embedding_vector("hash_123", "model_v2") is not None
