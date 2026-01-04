
from dataclasses import dataclass, field
from typing import Optional, Dict, Any

@dataclass
class ExtractResult:
    content: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
