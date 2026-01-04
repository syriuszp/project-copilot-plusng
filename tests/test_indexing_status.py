
import pytest
import time
from unittest.mock import MagicMock
from app.core.indexing_service import IndexingService

def test_scan_workspace_status_logic(tmp_path):
    # Setup FS
    f1 = tmp_path / "doc1.txt"
    f1.write_text("content1")
    
    f2 = tmp_path / "doc2.txt"
    f2.write_text("content2")
    
    # Mock Repo
    mock_repo = MagicMock()
    # Mock search_artifacts to return state
    # Case 1: doc1 is NEW (not in DB)
    # Case 2: doc2 is INDEXED (in DB, matches size/time)
    
    stat2 = f2.stat()
    db_record_f2 = {
        "path": str(f2),
        "filename": "doc2.txt",
        "size_bytes": stat2.st_size,
        "modified_at": stat2.st_mtime, # exact match
        "ingest_status": "indexed",
        "id": 100
    }
    
    mock_repo.search_artifacts.return_value = [db_record_f2]

    service = IndexingService(mock_repo, {})
    results = service.scan_workspace(str(tmp_path))
    
    res_map = {r["filename"]: r for r in results}
    
    assert res_map["doc1.txt"]["status"] == "NEW"
    assert res_map["doc2.txt"]["status"] == "INDEXED"

    # Case 3: Dirty (Modify f2)
    # Sleep to ensure mtime change if FS is fast, or explicit touch
    import os
    # Update mtime
    new_mtime = stat2.st_mtime + 500
    os.utime(str(f2), (new_mtime, new_mtime))
    
    results_dirty = service.scan_workspace(str(tmp_path))
    res_map_dirty = {r["filename"]: r for r in results_dirty}
    
    assert res_map_dirty["doc2.txt"]["status"] == "DIRTY"
    
def test_scan_workspace_failed_record(tmp_path):
    f1 = tmp_path / "fail.txt"
    f1.write_text("fail")
    
    stat = f1.stat()
    db_rec = {
        "path": str(f1),
        "filename": "fail.txt",
        "size_bytes": stat.st_size,
        "modified_at": stat.st_mtime,
        "ingest_status": "failed",
        "id": 101
    }
    
    mock_repo = MagicMock()
    mock_repo.search_artifacts.return_value = [db_rec]
    
    service = IndexingService(mock_repo, {})
    results = service.scan_workspace(str(tmp_path))
    
    assert results[0]["status"] == "FAILED"
