
import os
import hashlib
from pathlib import Path
from typing import List, Optional
from app.models.artifacts import Artifact, ArtifactDetails, PreviewResult

# Constants
PREVIEW_TEXT_LIMIT = 5000  # Characters
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".bmp"}
TEXT_EXTENSIONS = {".txt", ".md", ".json", ".log", ".yaml", ".yml", ".py", ".csv"}
PDF_EXTENSIONS = {".pdf"}

def list_artifacts(ingest_dir: str, filter_ext: Optional[str] = None, search_term: Optional[str] = None) -> List[Artifact]:
    """
    Lists artifacts in the ingestion directory with optional filtering and search.
    """
    artifacts = []
    
    if not ingest_dir or not os.path.exists(ingest_dir):
        return []

    try:
        # Non-recursive scan as per requirements
        for entry in os.scandir(ingest_dir):
            if entry.is_file():
                name = entry.name
                ext = Path(name).suffix.lower()
                
                # Apply filters
                if filter_ext and filter_ext != "all" and ext != filter_ext:
                    continue
                
                if search_term and search_term.lower() not in name.lower():
                    continue

                stats = entry.stat()
                artifacts.append(Artifact(
                    name=name,
                    path=entry.path,
                    size=stats.st_size,
                    mtime=stats.st_mtime,
                    type=ext
                ))
    except Exception as e:
        # Log error in a real app
        print(f"Error listing artifacts: {e}")
        return []

    # Default sort: mtime desc, name asc
    artifacts.sort(key=lambda x: (-x.mtime, x.name))
    return artifacts

def get_artifact_details(path: str, compute_hash: bool = False) -> ArtifactDetails:
    """
    Retrieves detailed metadata for an artifact.
    Hash calculation is optional/lazy via compute_hash=True.
    """
    try:
        path_obj = Path(path)
        stats = path_obj.stat()
        
        file_hash = None
        if compute_hash:
            # Lazy hash calculation
            sha256_hash = hashlib.sha256()
            with open(path, "rb") as f:
                for byte_block in iter(lambda: f.read(4096), b""):
                    sha256_hash.update(byte_block)
            file_hash = sha256_hash.hexdigest()
        
        return ArtifactDetails(
            name=path_obj.name,
            path=str(path_obj),
            size=stats.st_size,
            mtime=stats.st_mtime,
            type=path_obj.suffix.lower(),
            hash=file_hash
        )
    except Exception as e:
        # Fallback if file vanishes or perm error
        return ArtifactDetails(
            name=Path(path).name,
            path=path,
            size=0,
            mtime=0.0,
            type="",
            hash=None
        )

def preview_artifact(path: str) -> PreviewResult:
    """
    Generates a safe preview of the artifact.
    """
    if not os.path.exists(path):
        return PreviewResult(type="error", error_message="File not found")

    ext = Path(path).suffix.lower()

    try:
        if ext in IMAGE_EXTENSIONS:
            return PreviewResult(content=path, type="image")
        
        elif ext in PDF_EXTENSIONS:
            return PreviewResult(type="pdf_placeholder")
        
        elif ext in TEXT_EXTENSIONS:
            # Safe read with limit
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read(PREVIEW_TEXT_LIMIT)
                if len(f.read(1)) > 0: # Check if there's more
                    content += "\n... (truncated)"
            return PreviewResult(content=content, type="text")
        
        else:
            return PreviewResult(type="error", error_message=f"Preview not supported for {ext}")

    except Exception as e:
        return PreviewResult(type="error", error_message=str(e))
