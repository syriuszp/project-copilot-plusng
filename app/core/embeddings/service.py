from typing import List
from app.core.chunking.models import Chunk
from app.core.embeddings.repository import EmbeddingRepository
from app.core.embeddings.provider import EmbeddingProvider
from app.core.embeddings.providers.gemini_provider import GeminiEmbeddingProvider
from app.core.embeddings.providers.local_provider import LocalEmbeddingProvider

class EmbeddingService:
    def __init__(self, repository: EmbeddingRepository, config: dict):
        self.repository = repository
        self.config = config
        self.model_id = config.get("embeddings", {}).get("model_id", "gemini-embedding-001")
        self.provider = self._init_provider()

    def _init_provider(self) -> EmbeddingProvider:
        emb_config = self.config.get("embeddings", {})
        provider_name = emb_config.get("provider", "gemini")
        fail_closed = emb_config.get("fail_closed", True)
        
        if provider_name == "gemini":
            try:
                # Need to load actual setting if passed (model name etc)
                return GeminiEmbeddingProvider(model_id=self.model_id)
            except Exception as e:
                # Fallback logic
                if fail_closed:
                    raise RuntimeError(f"Gemini Provider failed to init (fail_closed=True): {e}")
                else:
                    return LocalEmbeddingProvider()
        else:
            return LocalEmbeddingProvider()

    def embed_chunks(self, chunks: List[Chunk]):
        """
        Embeds chunks. Skips already embedded chunks (based on hash=chunk_id + model_id).
        """
        if not chunks:
            return 0, 0

        chunk_ids = [c.chunk_id for c in chunks]
        
        # 1. Identify what's missing
        missing_ids = self.repository.get_missing_chunk_ids(chunk_ids, self.model_id)
        missing_chunks = [c for c in chunks if c.chunk_id in missing_ids]

        # Log stats
        total = len(chunks)
        missing = len(missing_chunks)
        skipped = total - missing
        print(f"Embedding: total={total} missing={missing} skipped={skipped}")

        if not missing_chunks:
            return 0, skipped

        # 2. Embed missing
        texts = [c.content_text for c in missing_chunks]
        # Batching logic should be here (e.g. 16 at a time), but MVP allows full list for now if small
        vectors = self.provider.embed_text(texts, self.model_id)

        # 3. Persist
        upsert_data = []
        for chunk, vector in zip(missing_chunks, vectors):
            upsert_data.append({
                "chunk_id": chunk.chunk_id,
                "model_id": self.model_id,
                "dim": self.provider.dimension,
                "vector": vector
            })
        
        self.repository.upsert_embeddings(upsert_data)
        return missing, skipped

    def embed_query(self, text: str) -> List[float]:
        """
        Embeds a single query string.
        """
        if not text:
            return []
        vectors = self.provider.embed_text([text], self.model_id)
        if vectors:
            return vectors[0]
        return []
