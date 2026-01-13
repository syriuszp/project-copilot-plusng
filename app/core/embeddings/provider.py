from typing import List, Protocol

class EmbeddingProvider(Protocol):
    def embed_text(self, texts: List[str], model_id: str) -> List[List[float]]:
        """
        Embeds a list of texts.
        Returns a list of vectors (floats).
        """
        ...
    
    @property
    def dimension(self) -> int:
        """Returns the dimension of the vectors produced by this provider."""
        ...
