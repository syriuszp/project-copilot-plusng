from dataclasses import dataclass
from typing import Optional

@dataclass
class SearchEvidence:
    """
    Represents a single search result with evidence.
    """
    artifact_id: int
    artifact_type: str
    source_path: str
    snippet: str
    score: Optional[float] = None
    search_mode: str = "unknown" # FTS or LIKE
