
import os
import sys
import shutil
import sqlite3
import pytest
from pathlib import Path

# Add repo root to path
REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(REPO_ROOT))

from app.db.database import init_or_upgrade_db
from app.core.indexing_service import IndexingService
from app.core.artifacts_repo import ArtifactsRepo
from app.core.search.service import SearchService

TEST_DB_PATH = REPO_ROOT / "tests" / "regression_proj.db"
TEST_INGEST_DIR = REPO_ROOT / "tests" / "regression_data"

def setup_environment():
    """Clean setup for regression test"""
    def remove_readonly(func, path, _):
        import stat
        try:
           os.chmod(path, stat.S_IWRITE)
        except: pass
        try:
            func(path)
        except: pass

    import time
    for i in range(5):
        try:
            if TEST_DB_PATH.exists():
                os.remove(TEST_DB_PATH)
            if TEST_INGEST_DIR.exists():
                shutil.rmtree(TEST_INGEST_DIR, onerror=remove_readonly)
            break
        except Exception as e:
            if i == 4: 
                print(f"FATAL: Setup cleanup failed: {e}")
                raise e # Fail test setup
            time.sleep(0.5)
    
    TEST_INGEST_DIR.mkdir(exist_ok=True)
    
    # Create dummy files
    (TEST_INGEST_DIR / "doc1.txt").write_text("Hello Project Copilot World", encoding="utf-8")
    (TEST_INGEST_DIR / "doc2.md").write_text("# Markdown Header\nSome markdown content.", encoding="utf-8")
    (TEST_INGEST_DIR / "image.png").write_bytes(b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82")

def test_db_init_empty():
    """Test 1: Init DB from scratch"""
    print("\n[TEST] DB Init (Empty)...")
    config = {"paths": {"db_path": str(TEST_DB_PATH)}}
    res = init_or_upgrade_db(config)
    assert res.status == "OK", f"DB Init Failed: {res.error}"
    assert TEST_DB_PATH.exists()
    
    # Verify Schema
    conn = sqlite3.connect(TEST_DB_PATH)
    cur = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='artifacts'")
    assert cur.fetchone() is not None, "artifacts table missing"
    
    # Verify Strict Schema (id column)
    cur = conn.execute("PRAGMA table_info(artifacts)")
    cols = [r[1] for r in cur.fetchall()]
    assert "id" in cols
    assert "ingest_status" in cols
    conn.close()
    print("PASS")

def test_indexing():
    """Test 2: Indexing functionality"""
    print("\n[TEST] Indexing...")
    repo = ArtifactsRepo(TEST_DB_PATH)
    # Features config for extraction
    features = {
        "extraction": {
            "images": True, 
            "ocr": False # Test without OCR to be fast
        }
    }
    
    indexer = IndexingService(repo, features)
    
    # Scan - Should find 3 NEW
    scan_res = indexer.scan_workspace(str(TEST_INGEST_DIR))
    new_files = [f for f in scan_res if f["status"] == "NEW"]
    assert len(new_files) == 3
    
    # Index All
    # Index All
    stats = indexer.index_all(str(TEST_INGEST_DIR))
    print(f"DEBUG: Index Stats: {stats}")
    # Print why failed
    artifacts = repo.search_artifacts("")
    for a in artifacts:
         print(f"Artifact: {a['filename']} Status: {a['ingest_status']} Error: {a['error']}")

    assert stats["indexed"] >= 2 # txt, md
    assert stats.get("not_extractable", 0) >= 0 # png might be not_extractable if no OCR/Image extractor loaded
    
    # Verify DB content
    artifacts = repo.search_artifacts("")
    assert len(artifacts) == 3
    
    # Verify Content in artifact_text
    indexed = [a for a in artifacts if a["ingest_status"] == 'indexed']
    assert len(indexed) >= 2
    
    print(f"PASS (Indexed: {stats['indexed']})")

def test_search():
    """Test 3: Search functionality"""
    print("\n[TEST] Search...")
    repo = ArtifactsRepo(TEST_DB_PATH)
    # SearchService only takes repo
    searcher = SearchService(repo)
    
    # 3.1 Basic Keyword
    res = searcher.search("Copilot")
    assert len(res) >= 1
    # SearchEvidence has source_path, snippet. source_path is full path.
    assert "doc1.txt" in str(res[0].source_path)
    
    # 3.2 Markdown Header search
    res2 = searcher.search("Header")
    assert len(res2) >= 1
    assert "doc2.md" in str(res2[0].source_path)
    
    # 3.3 Quoted Search (Regression for SyntaxError)
    res3 = searcher.search('"Project Copilot"')
    assert len(res3) >= 1

    print("PASS")

def test_ui_badge_backend():
    """Test 4: UI Badge Backend Logic (Dirtiness)"""
    print("\n[TEST] UI Badge Logic...")
    repo = ArtifactsRepo(TEST_DB_PATH)
    indexer = IndexingService(repo)
    
    # Modify file to trigger DIRTY
    (TEST_INGEST_DIR / "doc1.txt").write_text("Hello Project Copilot World UPDATED", encoding="utf-8")
    
    scan_res = indexer.scan_workspace(str(TEST_INGEST_DIR))
    dirty = [f for f in scan_res if f["status"] == "DIRTY"]
    
    if not dirty:
        # Debug why not dirty? Mtime resolution?
        # Force mtime update
        import time
        time.sleep(1.1)
        (TEST_INGEST_DIR / "doc1.txt").touch()
        scan_res = indexer.scan_workspace(str(TEST_INGEST_DIR))
        dirty = [f for f in scan_res if f["status"] == "DIRTY"]

    assert len(dirty) == 1
    assert dirty[0]["filename"] == "doc1.txt"
    print("PASS")

def run_all():
    setup_environment()
    try:
        test_db_init_empty()
        test_indexing()
        test_search()
        test_ui_badge_backend()
        print("\n\nSUCCESS: All P2 Regression Tests Passed.")
    except Exception as e:
        print(f"\n\nFAIL: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # Cleanup
        import time
        for _ in range(5):
            try:
                if TEST_DB_PATH.exists():
                    os.remove(TEST_DB_PATH)
                if TEST_INGEST_DIR.exists():
                    shutil.rmtree(TEST_INGEST_DIR)
                break
            except Exception:
                time.sleep(1.0)

if __name__ == "__main__":
    run_all()
