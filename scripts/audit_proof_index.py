
import logging
import sys
import os
from pathlib import Path

# Setup Path
REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(REPO_ROOT))

# Setup Logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("audit_proof")

from app.core.indexing_service import IndexingService
from app.core.artifacts_repo import ArtifactsRepo
from app.ui.config_loader import load_config

def prove_indexing():
    try:
        # 1. Load Config (Dev)
        os.environ["PROJECT_COPILOT_CONFIG_FILE"] = "config/dev.yaml"
        config_status = load_config()
        
        if config_status["status"] == "ERROR":
            logger.error(f"Config Load Error: {config_status['error']}")
            sys.exit(1)
            
        config = config_status["data"]
        
        logger.info(f"Loaded Config: {config_status['env']}")
        logger.info(f"Ingest Dir: {config['paths']['ingest_dir']}")
        logger.info(f"DB Path: {config['paths']['db_path']}")
        logger.info(f"Extraction Config: {config['features']['extraction']}")
        
        # 2. Setup Service
        db_path = Path(config["paths"]["db_path"]).resolve()
        repo = ArtifactsRepo(db_path)
        indexer = IndexingService(repo, config)
        
        # 3. Index All
        ingest_dir = Path(config["paths"]["ingest_dir"]).resolve()
        logger.info(f"Scanning {ingest_dir}...")
        
        stats = indexer.index_all(str(ingest_dir))
        logger.info(f"Index Stats: {stats}")
        
        # 4. Verify DB Content
        logger.info("Verifying DB Content for Audit Proof...")
        artifacts = repo.search_artifacts("")
        for a in artifacts:
            if "audit_proof" in a["filename"]:
                logger.info(f"FOUND: {a['filename']} | Status: {a['ingest_status']} | Ext: {a['ext']} | SHA256: {a.get('sha256')} | Error: {a.get('error')}")
                
                # Check Metadata (P1 verify)
                if a['ingest_status'] == 'indexed':
                     # Check artifact_text
                     import sqlite3
                     with sqlite3.connect(str(db_path)) as conn:
                         row = conn.execute("SELECT chars, extracted_at FROM artifact_text WHERE artifact_id = ?", (a['id'],)).fetchone()
                         if row:
                             logger.info(f"   -> Metadata: chars={row[0]}, extracted_at={row[1]}")
                         else:
                             logger.error("   -> Metadata MISSING in artifact_text!")
    except Exception as e:
        logger.error(f"SCRIPT ERROR: {e}")
        import traceback
        logger.error(traceback.format_exc())
    finally:
        logger.info("Script Completed.")

if __name__ == "__main__":
    prove_indexing()
