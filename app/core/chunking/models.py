from dataclasses import dataclass
from typing import Optional
from datetime import datetime

@dataclass
class Chunk:
    chunk_id: str
    artifact_id: str
    index_run_id: str
    content_text: str
    chunk_type: str  # 'text', 'table', 'image'
    hash: str
    position_index: int
    
    # Optional locators
    page: Optional[int] = None
    slide: Optional[int] = None
    section: Optional[str] = None
    bbox: Optional[str] = None
    
    is_active: int = 1
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    chunk_rowid: Optional[int] = None # Populated after DB insert for FTS sync
