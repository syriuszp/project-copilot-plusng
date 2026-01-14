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
    
    # Epic 5: Identity & Lifecycle
    insight_key: Optional[str] = None
    detection_rule_id: Optional[str] = None
    detection_pattern: Optional[str] = None
    
    status_origin: str = 'system' # 'system', 'manual'
    status_updated_at: Optional[datetime] = None
    previous_status: Optional[str] = None
    superseded_by_insight_id: Optional[str] = None
    status_comment: Optional[str] = None
    
    first_detected_at: Optional[datetime] = None
    last_confirmed_at: Optional[datetime] = None
    section_hint: Optional[str] = None

@dataclass
class Explainability:
    insight_id: str
    rationale: str # Why this was flagged
    related_sections: List[str] # e.g. ["Scope", "Timeline"]
    key_evidence_snippets: List[str]
    confidence_justification: str
    
    # Validation P0: Timeline & Logic
    first_detected_at: Optional[datetime]
    last_confirmed_at: Optional[datetime]
    status_updated_at: Optional[datetime]
    status: str
    status_origin: str
    status_logic: str # Deterministic explanation of status state
