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
    match_type: str = "unknown" # 'fts', 'vector', 'hybrid'
    is_literal: bool = False
    
    # Counters
    keyword_hits_in_chunk: int = 0
    keyword_hits_in_file: int = 0
    keyword_chunks_in_file: int = 0
    total_file_matches: int = 0 # Deprecated, kept for compat temporarily or alias
