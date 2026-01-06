
from dataclasses import dataclass, field
from typing import Optional, Dict, Any

@dataclass
class ExtractResult:
    text: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    status: str = "ok"
    extractor_name: str = "unknown"
    
    # Legacy support
    content: Optional[str] = None

    def __post_init__(self):
        # Normalize text/content
        if self.text is None and self.content is not None:
             self.text = self.content
        if self.content is None and self.text is not None:
             self.content = self.text
             
    @property
    def chars(self) -> int:
        return len(self.text) if self.text else 0
    
    @property
    def meta(self) -> Dict[str, Any]:
        return self.metadata
