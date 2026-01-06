
import sqlite3
import os
from pathlib import Path
from app.db.database import init_or_upgrade_db
import logging

# Setup Logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("B1_Verifier")

def verify_b1():
    db_path = Path("project_copilot_b1_test.db")
    migrations_dir = Path("db/migrations")
    
    # 1. Clean Start
    if db_path.exists():
        db_path.unlink()
        
    logger.info("--- Step 1: Fresh Init ---")
    res = init_or_upgrade_db({"paths": {"db_path": str(db_path)}}, migrations_dir)
    assert res.status == "OK", f"Init failed: {res.error}"
    
    # 2. Idempotency (Second Run)
    logger.info("--- Step 2: Idempotency Check ---")
    res = init_or_upgrade_db({"paths": {"db_path": str(db_path)}}, migrations_dir)
    assert res.status == "OK", f"Second Run failed: {res.error}"
    
    # 3. Schema Inspection
    logger.info("--- Step 3: Schema Inspection ---")
    with sqlite3.connect(str(db_path)) as conn:
        conn.row_factory = sqlite3.Row
        
        # Check schema_migrations
        rows = conn.execute("SELECT version FROM schema_migrations").fetchall()
        versions = [r["version"] for r in rows]
        logger.info(f"Migrations found: {versions}")
        # Note: Depending on file naming, just checking containment of known migration
        assert any("003" in v for v in versions), "Missing 003 migration"
        
        # Check artifact_text
        # artifact_id PK
        at_info = conn.execute("PRAGMA table_info(artifact_text)").fetchall()
        pk_col = next((r for r in at_info if r[1] == 'artifact_id'), None)
        assert pk_col, "artifact_text missing artifact_id"
        assert pk_col[5] == 1, "artifact_id is not PK"
        
        # FK -> artifacts(id) ON DELETE CASCADE
        fks = conn.execute("PRAGMA foreign_key_list(artifact_text)").fetchall()
        # (id, seq, table, from, to, on_update, on_delete, match)
        # Verify: table='artifacts', from='artifact_id', to='id', on_delete='CASCADE'
        valid_fk = False
        for fk in fks:
            if fk[2] == 'artifacts' and fk[3] == 'artifact_id' and fk[4] == 'id' and fk[6] == 'CASCADE':
                valid_fk = True
                break
        assert valid_fk, f"artifact_text missing FK to artifacts(id) ON DELETE CASCADE. Found: {fks}"
        
        # Check index_runs columns
        # run_id, started_at, ended_at, env, ingest_dir, files_seen, files_indexed, files_failed, fts_enabled
        ir_info = conn.execute("PRAGMA table_info(index_runs)").fetchall()
        ir_cols = {r[1] for r in ir_info}
        required = {
            "run_id", "started_at", "ended_at", "env", "ingest_dir",
            "files_seen", "files_indexed", "files_failed", "files_not_extractable", "fts_enabled"
        }
        # Note: user listed files_failed, check if files_not_extractable is required by user?
        # User list: run_id, started_at, ended_at, env, ingest_dir, files_seen, files_indexed, files_failed, fts_enabled
        # My schema (001_initial.sql) had 'files_not_extractable' too. 
        # I'll check strict subset of what user asked + what I know exists.
        missing = required - ir_cols
        # If 'files_not_extractable' is missing from user list but present in DB, that's fine.
        # If user ONLY listed expected columns, I should check those.
        user_expected = {
            "run_id", "started_at", "ended_at", "env", "ingest_dir",
            "files_seen", "files_indexed", "files_failed", "fts_enabled"
        }
        assert user_expected.issubset(ir_cols), f"index_runs missing columns: {user_expected - ir_cols}"
        
    logger.info("✅ B1 passed successfully.")
    
    # Clean up
    try:
        if db_path.exists():
            db_path.unlink() # Cleanup verified manual check
            pass # Or just leave it
    except Exception as e:
        logger.warning(f"Cleanup failed (Windows Lock): {e}")

if __name__ == "__main__":
    verify_b1()
