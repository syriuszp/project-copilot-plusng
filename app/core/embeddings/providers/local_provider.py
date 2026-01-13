import random
from typing import List
from app.core.embeddings.provider import EmbeddingProvider

class LocalEmbeddingProvider(EmbeddingProvider):
    def __init__(self, dim: int = 384):
        self._dim = dim

    def embed_text(self, texts: List[str], model_id: str) -> List[List[float]]:
        # Return random vectors for stub purposes
        return [[random.random() for _ in range(self._dim)] for _ in texts]

    @property
    def dimension(self) -> int:
        return self._dim
