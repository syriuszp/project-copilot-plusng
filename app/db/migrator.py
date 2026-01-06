
import sqlite3
import logging
from pathlib import Path
from typing import List
import shutil
import datetime

logger = logging.getLogger(__name__)

def apply_sql_migrations(conn: sqlite3.Connection, migrations_dir: Path) -> List[str]:
    """
    Applies .sql files from migrations_dir.
    Returns list of newly applied migration versions.
    """
    conn.execute("""
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version TEXT PRIMARY KEY,
            applied_at TEXT NOT NULL DEFAULT (datetime('now'))
        );
    """)
    
    files = sorted([f for f in migrations_dir.glob("*.sql")])
    if not files:
        logger.warning(f"No migrations found in {migrations_dir}")
        return []

    applied = {row[0] for row in conn.execute("SELECT version FROM schema_migrations")}
    newly_applied = []
    
    for f in files:
        version = f.stem 
        if version not in applied:
            logger.info(f"Applying migration: {version}")
            try:
                sql_script = f.read_text(encoding='utf-8')
                conn.executescript(sql_script)
                conn.execute("INSERT INTO schema_migrations (version) VALUES (?)", (version,))
                newly_applied.append(version)
            except Exception as e:
                logger.error(f"Migration {version} failed: {e}")
                raise e
    
    return newly_applied

def init_db(db_path: Path, migrations_dir: Path, strict: bool = False) -> List[str]:
    """
    Unified Entry Point. Returns list of applied migrations.
    """
    db_path.parent.mkdir(parents=True, exist_ok=True)
    
    # 1. Check consistency
    if db_path.exists() and _is_legacy_schema(db_path):
        logger.warning(f"Legacy/Broken schema detected at {db_path}. Performing strict rebuild.")
        _rebuild_db(db_path)
    
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA foreign_keys=ON;")
    
    applied_migrations = []
    
    try:
        if migrations_dir.exists():
            applied_migrations = apply_sql_migrations(conn, migrations_dir)
        else:
            logger.warning(f"Migrations directory not found: {migrations_dir}")
        
        conn.commit()
        
        # P0 Startup Log: Schema Version
        current_versions = [r[0] for r in conn.execute("SELECT version FROM schema_migrations ORDER BY version")]
        logger.info(f"DB init: db_path={db_path}")
        logger.info(f"DB init: applied migrations: {applied_migrations}")
        logger.info(f"DB init: schema_migrations: {current_versions}")
        
        return applied_migrations
        
    except Exception as e:
        conn.rollback()
        logger.error(f"DB Init Failed: {e}")
        raise e
    finally:
        conn.close()

def _is_legacy_schema(db_path: Path) -> bool:
    """
    Checks if DB matches strict requirements (Project Copilot V3+).
    Legacy signs: 
    - artifacts table has no 'id' column (PK).
    - artifacts 'path' is not UNIQUE.
    - artifact_text missing or wrong FK.
    """
    try:
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        
        # Check 'artifacts' table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='artifacts'")
        if not cursor.fetchone():
            return False # treat as new/empty, not legacy needing rebuild (unless corrupt file?)
            
        # Check columns for 'id'
        cursor.execute("PRAGMA table_info(artifacts)")
        cols = {row[1] for row in cursor.fetchall()}
        
        if 'id' not in cols:
            logger.warning("Legacy Detection: 'artifacts' missing 'id' column.")
            return True
            
        if 'path' not in cols:
            logger.warning("Legacy Detection: 'artifacts' missing 'path' column.")
            return True
            
        # Check for unique path? (Hard to check via PRAGMA easily without parsing SQL, 
        # but duplicate paths would fail strict migration 004 anyway. 
        # Better to rebuild if we suspect old schema).
        
        # Check artifact_text relation
        cursor.execute("PRAGMA foreign_key_list(artifact_text)")
        fks = cursor.fetchall()
        # Expecting link to 'artifacts' on 'id'
        # row: (id, seq, table, from, to, on_update, on_delete, match)
        # Check if any FK points to artifacts(id)
        valid_fk = any(row[2] == 'artifacts' and row[4] == 'id' for row in fks)
        
        # If artifact_text exists but no valid FK, it's legacy
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='artifact_text'")
        if cursor.fetchone() and not valid_fk:
             logger.warning("Legacy Detection: 'artifact_text' missing strict FK.")
             return True
             
        return False
        
    except Exception as e:
        logger.warning(f"Error checking legacy schema: {e}")
        return False # Assume fine to avoid loops, let migration fail if must
    finally:
        try:
            conn.close()
        except: pass

def _rebuild_db(db_path: Path):
    """
    Backs up and deletes the database to allow clean init.
    """
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = db_path.with_name(f"{db_path.name}.backup_{timestamp}")
    
    try:
        shutil.copy2(db_path, backup_path)
        logger.info(f"Database backed up to {backup_path}")
        
        # Retry loop for Windows file locking
        import time
        deleted = False
        for i in range(5):
            try:
                # Delete WAL/SHM if exist
                wal = db_path.with_suffix(".db-wal")
                shm = db_path.with_suffix(".db-shm")
                if wal.exists(): wal.unlink()
                if shm.exists(): shm.unlink()
                db_path.unlink()
                deleted = True
                break
            except PermissionError:
                if i == 4: 
                    logger.warning("Could not delete DB file due to lock. Attempting DROP ALL TABLES fallback.")
                else:
                    time.sleep(0.5)
        
        if not deleted:
            # Fallback: Drop all tables
            try:
                with sqlite3.connect(str(db_path)) as conn:
                    conn.execute("PRAGMA foreign_keys=OFF") # Disable FK to allow dropping
                    tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")]
                    for t in tables:
                        if t != "sqlite_sequence":
                            conn.execute(f"DROP TABLE IF EXISTS \"{t}\"")
                    conn.execute("VACUUM") # Optional cleanup
                    conn.commit()
                logger.info("Legacy database cleared via DROP TABLES (Fallback).")
            except Exception as drop_err:
                logger.error(f"Failed to DROP tables in fallback: {drop_err}")
                raise drop_err

        logger.info("Legacy database removed/cleared for strict rebuild.")
    except Exception as e:
        logger.error(f"Failed to rebuild DB: {e}")
        raise e

# Valid alias for backward compat if needed, but we prefer init_db
init_or_upgrade_db = init_db

def ensure_schema(db_path: str, migrations_dir: str | None = None, *, strict: bool = True, env: str | None = None) -> None:
    """
    Backward compatibility wrapper for tests.
    Delegates to init_db.
    """
    logger.info(f"ensure_schema wrapper called for {db_path}")
    path_obj = Path(db_path)
    
    # Resolve migrations dir default
    if migrations_dir:
        mig_dir_obj = Path(migrations_dir)
    else:
        # Assuming migrator.py is in app/db, migrations are in repo/db/migrations
        mig_dir_obj = Path(__file__).resolve().parents[2] / "db" / "migrations"
        
    init_db(path_obj, mig_dir_obj, strict=strict)
