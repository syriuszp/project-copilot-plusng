
import os
import logging
from pathlib import Path
from typing import Dict, Any, List

from app.core.artifacts_repo import ArtifactsRepo
from app.core.extractors.registry import ExtractorRegistry

logger = logging.getLogger(__name__)

class IndexingService:
    def __init__(self, repo: ArtifactsRepo, config: Dict[str, Any] = None):
        self.repo = repo
        self.config = config or {}
        self.registry = ExtractorRegistry(config)

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
            extractor = self.registry.get(ext)
            
            if not extractor:
                self.repo.set_index_status(artifact_id, "not_extractable")
                return "not_extractable"
                
            try:
                result = extractor.extract(str(p))
                
                if result.content:
                    self.repo.save_extracted_text(
                        artifact_id, 
                        result.content, 
                        extractor.__class__.__name__, 
                        len(result.content),
                        meta["filename"],
                        meta["path"]
                    )
                    return "indexed"
                else:
                    # If content is None, it might be failed or not_extractable
                    # Check error
                    if result.error:
                        self.repo.set_index_status(artifact_id, "failed", result.error)
                        return "failed"
                    else:
                        self.repo.set_index_status(artifact_id, "not_extractable")
                        return "not_extractable"
            except Exception as e:
                logger.error(f"Extraction exception for {path}: {e}")
                self.repo.set_index_status(artifact_id, "failed", str(e))
                return "failed"
            except Exception as e:
                logger.error(f"Extraction failed for {path}: {e}")
                self.repo.set_index_status(artifact_id, "failed", str(e))
                return "failed"
                
        except Exception as e:
            logger.error(f"Indexing error for {path}: {e}")
            # If we have artifact_id we can set status, else just log
            return "failed"


    def scan_workspace(self, ingest_dir: str) -> List[Dict[str, Any]]:
        """
        Scans directory and compares with DB to determine status.
        Returns list of file metadata including calculated 'status'.
        Statuses: NEW, DIRTY, INDEXED, FAILED, NOT_EXTRACTABLE
        Strict Logic: 
        - NEW: Not in DB.
        - DIRTY: mtime/size mismatch.
        - INDEXED/FAILED: From DB.
        """
        results = []
        if not os.path.exists(ingest_dir):
            return results

        # 1. Get DB State
        # Fetch all paths and timestamps/sizes in chunks
        chunk_size = self.config.get("indexing", {}).get("db_path_chunk_size", 500)
        # Safeguard: max(50, min(chunk_size, 1000))
        if not isinstance(chunk_size, int): chunk_size = 500
        chunk_size = max(50, min(chunk_size, 1000))
        
        db_artifacts = {}
        offset = 0
        total_fetched = 0
        
        logger.debug(f"Starting Index scan with chunk_size={chunk_size}")

        while True:
            batch = self.repo.search_artifacts("", limit=chunk_size, offset=offset)
            if not batch:
                break
            
            for a in batch:
                db_artifacts[a['path']] = a
            
            count = len(batch)
            total_fetched += count
            offset += count
            
            if count < chunk_size: # End of records
                break

        logger.debug(f"Index scan: DB fetch complete. {total_fetched} records loaded.")

        # 2. Walk FS
        for entry in os.scandir(ingest_dir):
            if entry.is_file():
                p = Path(entry.path)
                try:
                    stat = p.stat()
                    fs_meta = {
                        "path": str(p),
                        "filename": p.name,
                        "ext": p.suffix.lower(),
                        "size_bytes": stat.st_size,
                        "modified_at": stat.st_mtime
                    }
                    
                    if str(p) not in db_artifacts:
                        fs_meta["status"] = "NEW"
                        results.append(fs_meta)
                    else:
                        db_rec = db_artifacts[str(p)]
                        
                        # Compare time/size
                        # Provide default 0.0 for None to ensure comparison works
                        db_mtime = float(db_rec.get('modified_at') or 0.0)
                        db_size = int(db_rec.get('size_bytes') or 0)
                        
                        # Mtime tolerance (0.1s for filesystem jitter)
                        is_dirty = (abs(db_mtime - fs_meta['modified_at']) > 0.1) or (db_size != fs_meta['size_bytes'])
                        
                        if is_dirty:
                             fs_meta["status"] = "DIRTY"
                             fs_meta["id"] = db_rec.get('id')
                             results.append(fs_meta)
                        else:
                             # Use DB status. 
                             # If DB status is missing for some reason, default to UNKNOWN?
                             # Or if 'new' in DB (upserted but not indexed), treat as NEW for UI?
                             # In Strict mode, DB 'new' means pending.
                             # If we handle "NEW" badge here as "FS New", maybe allow "PENDING"?
                             # Requirement says: NEW / DIRTY / INDEXED / FAILED.
                             # If DB says 'new', it technically isn't NEW (FS-only), but "Not Indexed".
                             # Let's map 'new' -> 'NEW' for UI consistency?
                             # Or strict DB status.
                             status = db_rec.get('ingest_status', 'new').lower()
                             
                             # Map to UI Badges
                             if status == 'new':
                                 fs_meta["status"] = "NEW" # Treat pending as NEW
                             elif status == 'failed':
                                 fs_meta["status"] = "FAILED"
                             elif status == 'indexed':
                                 fs_meta["status"] = "INDEXED"
                             elif status == 'not_extractable':
                                 fs_meta["status"] = "NOT_EXTRACTABLE"
                             else:
                                 fs_meta["status"] = status.upper()

                             fs_meta["id"] = db_rec.get('id')
                             results.append(fs_meta)
                             
                except Exception as e:
                    logger.warning(f"Error scanning {p}: {e}")
                    results.append({"path": str(p), "status": "ERROR", "error": str(e)})

        return results

    def index_needed(self, ingest_dir: str) -> List[Dict[str, Any]]:
        """
        Returns only files that need indexing (NEW or DIRTY).
        """
        all_files = self.scan_workspace(ingest_dir)
        return [f for f in all_files if f.get("status") in ("NEW", "DIRTY")]

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
        
        # Scan first? Or just iterate?
        # index_all usually implies re-indexing everything or just "Make it right"?
        # User goal: "Index Needed" button processes ONLY NEW/DIRTY.
        # "Index All" usually means "Index Everything".
        # But efficiently?
        # Let's keep index_all simple: iterate and index. index_file logic updates DB.
        
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
