from dataclasses import dataclass
from typing import Optional, List
from datetime import datetime

@dataclass
class Insight:
    insight_id: str
    index_run_id: str
    type: str  # 'unknown', 'decision', 'dependency'
    statement: str
    status: str = 'open'
    confidence: float = 0.0
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    evidence_chunk_ids: Optional[List[str]] = None
    insight_fingerprint: Optional[str] = None
