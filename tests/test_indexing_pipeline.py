import pytest
from unittest.mock import MagicMock, ANY, patch
from app.core.indexing_service import IndexingService
from app.core.chunking.service import ChunkingService
from app.core.embeddings.service import EmbeddingService
from app.core.vector.faiss_index import VectorStore
from app.core.insights.engine import InsightEngine

@pytest.fixture
def mock_indexing_service():
    repo = MagicMock()
    config = {"paths": {"db": ":memory:", "index": "test_idx"}}
    
    # Patch dependencies
    with patch("app.core.indexing_service.ChunkingRepository"), \
         patch("app.core.indexing_service.ChunkingService") as MockChunkSvc, \
         patch("app.core.indexing_service.EmbeddingRepository"), \
         patch("app.core.indexing_service.EmbeddingService") as MockEmbSvc, \
         patch("app.core.indexing_service.VectorStore") as MockVecStore, \
         patch("app.core.indexing_service.InsightRepository"), \
         patch("app.core.indexing_service.InsightEngine") as MockInsightEng, \
         patch("app.core.indexing_service.ExtractorRegistry") as MockRegistry:
         
        service = IndexingService(repo, config)
        
        # Attach mocks for access
        service.mock_chunk_service = MockChunkSvc.return_value
        service.mock_emb_service = MockEmbSvc.return_value
        service.mock_vector_store = MockVecStore.return_value
        service.mock_insight_engine = MockInsightEng.return_value
        service.registry = MockRegistry.return_value # Replace real registry with mock instance
        
        yield service 

def test_indexing_service_triggers_full_semantic_pipeline(mock_indexing_service):
    """Test that index_file trigger Chunk->Embed and finalize triggers Vector->Insight."""
    
    # Mock Extraction
    mock_extractor = MagicMock()
    mock_extractor.extract.return_value.text = "Sample content"
    mock_indexing_service.registry.get.return_value = mock_extractor
    
    # Mock FS
    with patch("os.path.exists", return_value=True), \
         patch("pathlib.Path.stat", return_value=MagicMock(st_size=10, st_mtime=100)), \
         patch("app.core.indexing_service.IndexingService._calculate_sha256", return_value="sha"):
         
        # Action: Index One File
        mock_indexing_service.index_file("test.pdf", run_id="run_1")
        
        # Verify Chunking
        mock_indexing_service.mock_chunk_service.process_artifact.assert_called_with(
            ANY, "run_1", "Sample content", metadata=ANY
        )
        # Verify Embedding
        mock_indexing_service.mock_emb_service.embed_chunks.assert_called()
        
        # Action: Finalize (via private method or integrated workflow simulation)
        mock_indexing_service._finalize_run("run_1")
        
        # Verify Vector Build
        mock_indexing_service.mock_vector_store.rebuild_from_db.assert_called()
        # Verify Insights
        mock_indexing_service.mock_insight_engine.run.assert_called_with("run_1")
