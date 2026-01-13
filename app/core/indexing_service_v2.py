from pathlib import Path
from typing import List
from app.core.chunking.service import ChunkingService
from app.core.chunking.repository import ChunkingRepository
from app.core.embeddings.service import EmbeddingService
from app.core.embeddings.repository import EmbeddingRepository
from app.core.vector.faiss_index import VectorStore
from app.core.insights.engine import InsightEngine
from app.core.insights.repository import InsightRepository

# Placeholder for existing dependencies (Extraction, etc.)
# In real app, these might be injected or initialized in __init__

class IndexingService:
    def __init__(self, db_path: str, index_dir: str, config: dict):
        self.db_path = db_path
        self.config = config
        
        # Initialize Repos
        self.chunk_repo = ChunkingRepository(db_path)
        self.emb_repo = EmbeddingRepository(db_path)
        self.insight_repo = InsightRepository(db_path)
        
        # Initialize Services
        self.chunk_service = ChunkingService(self.chunk_repo)
        self.emb_service = EmbeddingService(self.emb_repo, config)
        self.vector_store = VectorStore(index_dir)
        self.insight_engine = InsightEngine(db_path, self.insight_repo)
        
    def process_artifact(self, artifact_id: str, index_run_id: str, content: str, metadata: dict = None):
        """
        Orchestrates the full semantic pipeline for a single artifact.
        """
        # 1. Chunk
        active_chunks = self.chunk_service.process_artifact(artifact_id, index_run_id, content, metadata)
        
        # 2. Embed (only new active chunks)
        # Note: embed_chunks implementation handles filtering already embedded ones
        self.emb_service.embed_chunks(active_chunks)
        
        # 3. Index (Vector Store)
        # In MVP plan, we said "Upsert or Rebuild".
        # Rebuilding PER ARTIFACT is too slow. 
        # Usually we batch index at end of run, or upsert here.
        # Plan said: "Index: VectorStore.upsert_or_rebuild(model_id)" in the flow.
        # But wait, IndexingService processes *Artifacts*.
        # Rebuilding the WHOLE index after every file is bad.
        # However, for "Index Needed" flow where we process a few files, we might do it once at the end?
        # OR we just update the index with these vectors?
        # VectorStore.rebuild_from_db wipes and rebuilds.
        # If we want per-file incremental, we need `add` method.
        # Phase 4 implementation only has `rebuild_from_db`.
        # So, ideally this should be called ONCE at the end of the batch.
        # But `process_artifact` is per file.
        # Let's assume for MVP correctness we rely on a `finalize_run` method, 
        # or we accept the cost if it's small corpus.
        # Or we add a `index_chunk` method to VectorStore?
        # Given "MVP Logic: Full Rebuild", we should probably move this out of the per-file loop 
        # or accept it happens elsewhere.
        # BUT, the Requirement "Pipeline Orchestration" implies it happens here.
        # Let's modify: `process_artifact` does Chunk+Embed. 
        # `finalize_run` does Index+Analyze.
        pass

    def run_batch(self, artifacts_data: List[dict], index_run_id: str):
        """
        Processes a batch of artifacts (simulating the 'Index Needed' loop).
        artifacts_data: list of {id, content, metadata}
        """
        # 1. Process Loop
        for item in artifacts_data:
            self.process_artifact(item['id'], index_run_id, item['content'], item.get('metadata'))
            
        # 2. Finalize (Global Operations)
        
        # Rebuild Index (Global)
        model_id = self.emb_service.model_id
        self.vector_store.rebuild_from_db(self.db_path, model_id)
        
        # Generate Insights (Global / Incremental for this run)
        self.insight_engine.run(index_run_id)
