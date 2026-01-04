
import sqlite3
import logging
from pathlib import Path
from typing import List

logger = logging.getLogger(__name__)

def apply_sql_migrations(conn: sqlite3.Connection, migrations_dir: Path):
    """
    Applies .sql files from migrations_dir.
    This manages the 'schema_migrations' table.
    """
    conn.execute("""
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version TEXT PRIMARY KEY,
            applied_at TEXT NOT NULL DEFAULT (datetime('now'))
        );
    """)
    
    # List .sql files sorted
    files = sorted([f for f in migrations_dir.glob("*.sql")])
    if not files:
        logger.warning(f"No migrations found in {migrations_dir}")
        return

    # Check applied
    applied = {row[0] for row in conn.execute("SELECT version FROM schema_migrations")}
    
    for f in files:
        version = f.stem # e.g. 001_initial
        if version not in applied:
            logger.info(f"Applying migration: {version}")
            try:
                sql_script = f.read_text(encoding='utf-8')
                conn.executescript(sql_script)
                conn.execute("INSERT INTO schema_migrations (version) VALUES (?)", (version,))
            except Exception as e:
                logger.error(f"Migration {version} failed: {e}")
                raise e
        else:
            logger.debug(f"Migration {version} already applied")

def ensure_schema(conn: sqlite3.Connection):
    """
    Idempotently ensures schema correctness (columns, indexes, FTS).
    This handles upgrades where SQLite 'ALTER TABLE IF NOT EXISTS' is insufficient.
    """
    logger.info("Verifying DB Schema constraints (Python-driven hardening)...")
    
    # 0. Handle Legacy Schema (001_initial)
    # Detect artifacts table with artifact_id (legacy PK) vs id (new PK)
    try:
        cur = conn.execute("PRAGMA table_info(artifacts)")
        cols = {row[1] for row in cur.fetchall()}
        
        if "artifact_id" in cols and "id" not in cols:
            logger.warning("Migrating Legacy artifacts table: renaming artifact_id -> id")
            conn.execute("ALTER TABLE artifacts RENAME COLUMN artifact_id TO id")
            
        if "source_uri" in cols and "path" not in cols:
            logger.warning("Migrating Legacy artifacts table: renaming source_uri -> path")
            conn.execute("ALTER TABLE artifacts RENAME COLUMN source_uri TO path")
            
        if "content_hash" in cols and "sha256" not in cols:
            logger.warning("Migrating Legacy artifacts table: renaming content_hash -> sha256")
            conn.execute("ALTER TABLE artifacts RENAME COLUMN content_hash TO sha256")
            
    except Exception as e:
        logger.error(f"Legacy migration failed (non-critical if table missing): {e}")

    # 1. artifacts columns
    _ensure_columns(conn, "artifacts", {
        "id": "INTEGER", # PK
        "path": "TEXT",  # UNIQUE NOT NULL (checked via index usually, hard to alter in sqlite)
        "filename": "TEXT",
        "ext": "TEXT", 
        "size_bytes": "INTEGER",
        "modified_at": "TEXT",
        "sha256": "TEXT",
        "ingest_status": "TEXT DEFAULT 'new'",
        "error": "TEXT",
        "updated_at": "TEXT"
    })
    
    # 1a. Backfill filename/ext if empty (from path)
    try:
        # Check if we need to backfill
        # SQLite substr/instr logic: 
        # filename = substr(path, length(path) - instr(reverse(path), '\') + 1) ? No reverse in sqlite standard?
        # Python backfill is safer.
        rows = conn.execute("SELECT id, path FROM artifacts WHERE filename IS NULL OR ext IS NULL").fetchall()
        if rows:
            logger.info(f"Backfilling filename/ext for {len(rows)} artifacts")
            updates = []
            for r in rows:
                aid, p = r[0], r[1]
                path_obj = Path(p)
                updates.append((path_obj.name, path_obj.suffix, aid))
            
            conn.executemany("UPDATE artifacts SET filename=?, ext=? WHERE id=?", updates)
    except Exception as e:
        logger.warning(f"Backfill filename/ext failed: {e}")
    
    # 2. artifact_text columns
    _ensure_columns(conn, "artifact_text", {
        "artifact_id": "INTEGER", # PK
        "text": "TEXT",
        "extracted_at": "TEXT",
        "extractor": "TEXT",
        "chars": "INTEGER"
    })
    
    # 3. index_runs columns
    _ensure_columns(conn, "index_runs", {
        "run_id": "TEXT",
        "started_at": "TEXT",
        "ended_at": "TEXT",
        "env": "TEXT",
        "ingest_dir": "TEXT",
        "files_seen": "INTEGER",
        "files_indexed": "INTEGER",
        "files_failed": "INTEGER",
        "files_not_extractable": "INTEGER",
        "fts_enabled": "INTEGER"
    })
    
    # 4. Indexes (Safe creation after columns ensured)
    _ensure_indexes(conn)

    # 5. FTS5 (Rebuild if missing)
    _ensure_fts(conn)

def _ensure_indexes(conn: sqlite3.Connection):
    """
    Ensures crucial indexes exist.
    """
    try:
        conn.execute("CREATE INDEX IF NOT EXISTS idx_artifacts_ext ON artifacts(ext)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_artifacts_status ON artifacts(ingest_status)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_artifacts_modified_at ON artifacts(modified_at)")
    except Exception as e:
        logger.warning(f"Failed to create indexes: {e}")


def _ensure_columns(conn: sqlite3.Connection, table: str, required_columns: dict):
    """
    Checks if columns exist, adds them if missing.
    """
    # Check if table exists first
    cursor = conn.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table}'")
    if not cursor.fetchone():
        # Table doesn't exist, migrations should have created it or we create it?
        # Ideally migrations created it. If not, we have a bigger issue or need 'CREATE TABLE' here.
        # Epic 3.1 policy: SQL migrations create clean state. This func handles UPGRADES.
        # So if missing, it implies clean state wasn't applied or bad state.
        logger.warning(f"Table {table} missing during ensure_schema. It should have been created by migrations.")
        return

    # Introspection
    existing_cols = {row[1]: row for row in conn.execute(f"PRAGMA table_info({table})")}
    
    for col_name, col_type in required_columns.items():
        if col_name not in existing_cols:
            logger.info(f"Adding missing column: {table}.{col_name} ({col_type})")
            try:
                # Basic ADD COLUMN. Note: SQLite doesn't support adding UNIQUE/PRIMARY KEY constraints via ALTER.
                # Complex constraints require table rebuild, which we assume established by 003 SQL for fresh, 
                # or manually patched here if critical. For now, simple columns.
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {col_name} {col_type}")
            except Exception as e:
                logger.error(f"Failed to add column {table}.{col_name}: {e}")

def _ensure_fts(conn: sqlite3.Connection):
    """
    Ensures FTS table exists.
    """
    try:
        conn.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS artifact_fts USING fts5(
                filename, 
                path, 
                text, 
                ref_id UNINDEXED
            );
        """)
    except sqlite3.OperationalError:
        logger.warning("FTS5 not supported by this SQLite build. Skipping FTS init.")

def init_or_upgrade_db(db_path: Path, migrations_dir: Path):
    """
    Main entry point for DB initialization.
    """
    db_path.parent.mkdir(parents=True, exist_ok=True)
    
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA foreign_keys=ON;")
    
    try:
        # 1. Apply strict SQL migrations (baseline)
        if migrations_dir.exists():
            apply_sql_migrations(conn, migrations_dir)
        
        # 2. Python Hardening (Idempotent Upgrades)
        ensure_schema(conn)
        
        conn.commit()
        logger.info(f"DB initialized/upgraded at {db_path}")
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()
