
import pytest
from unittest.mock import MagicMock
from pathlib import Path
import time
from app.core.indexing_service import IndexingService

def test_scan_files_statuses(tmp_path):
    # Setup
    repo_mock = MagicMock()
    service = IndexingService(repo_mock)
    
    # Create 3 files
    f_new = tmp_path / "new.txt"
    f_new.write_text("new")
    
    f_dirty = tmp_path / "dirty.txt"
    f_dirty.write_text("dirty content")
    
    f_clean = tmp_path / "clean.txt"
    f_clean.write_text("clean content")
    
    # Mock DB state
    # clean.txt is in DB and matches
    # dirty.txt is in DB but size/time differs
    k_dirty = str(f_dirty)
    k_clean = str(f_clean)
    
    clean_stat = f_clean.stat()
    
    db_data = [
        {
            "artifact_id": 1,
            "path": k_clean,
            "modified_at": clean_stat.st_mtime,
            "size_bytes": clean_stat.st_size,
            "ingest_status": "indexed"
        },
        {
            "artifact_id": 2,
            "path": k_dirty,
            "modified_at": 1000.0, # Old time
            "size_bytes": 5, # Old size (content is len 13)
            "ingest_status": "indexed"
        }
    ]
    
    # Mock search_artifacts to return these
    # Note: repo.search_artifacts currently returns dictionaries
    repo_mock.search_artifacts.return_value = db_data
    
    # Run scan
    results = service.scan_files(str(tmp_path))
    res_map = {r["path"]: r for r in results}
    
    # Assertions
    # 1. NEW
    assert str(f_new) in res_map
    assert res_map[str(f_new)]["status"] == "NEW"
    
    # 2. DIRTY
    assert k_dirty in res_map
    assert res_map[k_dirty]["status"] == "DIRTY"
    
    # 3. INDEXED (Clean)
    assert k_clean in res_map
    assert res_map[k_clean]["status"] == "INDEXED"

def test_index_needed_filter(tmp_path):
    repo_mock = MagicMock()
    service = IndexingService(repo_mock)
    
    # Create NEW file
    f = tmp_path / "foo.txt"
    f.touch()
    
    repo_mock.search_artifacts.return_value = []
    
    needed = service.index_needed(str(tmp_path))
    assert len(needed) == 1
    assert needed[0]["path"] == str(f)
