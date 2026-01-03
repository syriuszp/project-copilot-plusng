
import os
import logging
from pathlib import Path
from typing import Dict, Any, List

from app.core.artifacts_repo import ArtifactsRepo
from app.core.extractors.plain import PlainTextExtractor
from app.core.extractors.pdf import PdfExtractor
from app.core.extractors.docx import DocxExtractor

logger = logging.getLogger(__name__)

class IndexingService:
    def __init__(self, repo: ArtifactsRepo):
        self.repo = repo
        self.extractors = {
            ".txt": PlainTextExtractor(),
            ".md": PlainTextExtractor(),
            ".json": PlainTextExtractor(),
            ".yaml": PlainTextExtractor(),
            ".yml": PlainTextExtractor(),
            ".py": PlainTextExtractor(),
            ".pdf": PdfExtractor(),
            ".docx": DocxExtractor()
        }

    def index_file(self, path: str) -> str:
        """
        Indexes a single file. Returns status (indexed/failed/not_extractable/skipped).
        """
        if not os.path.exists(path):
            return "failed" # File removed during index
            
        try:
            p = Path(path)
            stats = p.stat()
            
            # 1. Upsert Artifact
            meta = {
                "path": str(p),
                "filename": p.name,
                "ext": p.suffix.lower(),
                "size_bytes": stats.st_size,
                "modified_at": stats.st_mtime, # Float timestamp
                "sha256": None # Optional P2
            }
            
            # Check if updated (optimization: skip extraction if size/mtime match?)
            # Repo upsert handles conflict, but we might want to check DB first to save extraction?
            # For P0 idempotent: always extract or check inside upsert logic logic.
            # artifacts_repo.upsert updates timestamp.
            
            artifact_id = self.repo.upsert_artifact(meta)
            
            # 2. Extract Text
            ext = meta["ext"]
            extractor = self.extractors.get(ext)
            
            if not extractor:
                self.repo.set_index_status(artifact_id, "not_extractable")
                return "not_extractable"
                
            try:
                text = extractor.extract(str(p))
                if text:
                    self.repo.save_extracted_text(
                        artifact_id, 
                        text, 
                        extractor.__class__.__name__, 
                        len(text),
                        meta["filename"],
                        meta["path"]
                    )
                    return "indexed"
                else:
                    self.repo.set_index_status(artifact_id, "not_extractable")
                    return "not_extractable"
            except Exception as e:
                logger.error(f"Extraction failed for {path}: {e}")
                self.repo.set_index_status(artifact_id, "failed", str(e))
                return "failed"
                
        except Exception as e:
            logger.error(f"Indexing error for {path}: {e}")
            # If we have artifact_id we can set status, else just log
            return "failed"

    def index_all(self, ingest_dir: str) -> Dict[str, int]:
        """
        Indexes all files in ingest_dir.
        Returns counts: {'indexed': N, 'failed': M, ...}
        Records run telemetry.
        """
        import uuid
        import datetime
        
        run_id = str(uuid.uuid4())
        started_at = datetime.datetime.now().isoformat()
        results = {"indexed": 0, "failed": 0, "not_extractable": 0, "skipped": 0}
        
        if not os.path.exists(ingest_dir):
            return results
            
        files_count = 0
        for entry in os.scandir(ingest_dir):
            if entry.is_file():
                status = self.index_file(entry.path)
                results[status] = results.get(status, 0) + 1
                files_count += 1
                
        ended_at = datetime.datetime.now().isoformat()
        
        # Record Run
        try:
            self.repo.record_index_run({
                "run_id": run_id,
                "started_at": started_at,
                "ended_at": ended_at,
                "env": os.environ.get("PROJECT_COPILOT_ENV", "UNKNOWN"),
                "ingest_dir": ingest_dir,
                "files_seen": files_count,
                "files_indexed": results.get("indexed", 0),
                "files_failed": results.get("failed", 0),
                "files_not_extractable": results.get("not_extractable", 0)
            })
        except Exception as e:
            logger.error(f"Failed to record index run: {e}")
                
        return results
