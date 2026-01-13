import hashlib
from typing import List
from app.core.chunking.repository import ChunkingRepository
from app.core.chunking.models import Chunk

class ChunkingService:
    def __init__(self, repository: ChunkingRepository):
        self.repository = repository

    def _calculate_hash(self, artifact_id: str, chunk_type: str, content: str, position: int) -> str:
        # Minimal hashing for structural uniqueness
        raw = f"{artifact_id}|{chunk_type}|{position}|{content}"
        return hashlib.sha256(raw.encode('utf-8')).hexdigest()

    def process_artifact(self, artifact_id: str, index_run_id: str, content: str, metadata: dict = None) -> List[Chunk]:
        """
        Splits content into chunks, persists them, handles zombie cleanup, and syncs FTS.
        Returns a list of ACTIVE chunks for this run.
        """
        # MVP Splitter Logic (just one big chunk for text + maybe placeholder for images if we had them)
        # Real logic would use splitters.py
        chunks_data = []
        
        # Simple splitting by paragraphs for MVP
        parts = content.split("\n\n")
        current_pos = 0
        
        for part in parts:
            part = part.strip()
            if not part:
                continue
                
            chunk_hash = self._calculate_hash(artifact_id, 'text', part, current_pos)
            
            # Create Chunk Domain Object
            chunk = Chunk(
                chunk_id=chunk_hash, # Using hash as ID for strong idempotency
                artifact_id=artifact_id,
                index_run_id=index_run_id,
                content_text=part,
                chunk_type='text',
                hash=chunk_hash,
                position_index=current_pos,
                is_active=1
                # Page/Slide locators would come from extraction metadata if available
            )
            chunks_data.append(chunk)
            current_pos += 1

        active_chunks = []

        # 1. Upsert Chunks
        for chunk in chunks_data:
            chunk_rowid = self.repository.upsert_chunk(chunk)
            chunk.chunk_rowid = chunk_rowid
            
            # Sync FTS
            self.repository.sync_fts_for_chunk(chunk_rowid, chunk.content_text, 1)
            active_chunks.append(chunk)

        # 2. Handle Zombies (Chunks from old runs for this artifact)
        stale_rowids = self.repository.deactivate_stale_chunks(artifact_id, index_run_id)
        
        # Sync FTS for zombies (Remove them)
        for rowid in stale_rowids:
             self.repository.sync_fts_for_chunk(rowid, "", 0)

        return active_chunks
