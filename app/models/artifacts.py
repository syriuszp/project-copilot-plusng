
from dataclasses import dataclass
from typing import Optional, Union

@dataclass
class Artifact:
    name: str
    path: str
    size: int
    mtime: float
    type: str  # extension, e.g. ".txt"

@dataclass
class ArtifactDetails(Artifact):
    hash: Optional[str] = None
    # Add other metadata fields here if needed

@dataclass
class PreviewResult:
    content: Optional[Union[str, bytes]] = None
    type: str = "text" # "text", "image", "pdf_placeholder", "error"
    error_message: Optional[str] = None
