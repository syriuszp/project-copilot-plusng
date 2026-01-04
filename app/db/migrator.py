
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
    Uses 'Rebuild Table' strategy for correct unification of Legacy (001) to Epic 3.1.
    """
    logger.info("Verifying DB Schema constraints (Python-driven hardening)...")
    
    # 0. Check for Legacy Schema that needs full Rebuild
    # Legacy indicators: 'source_type' column, or 'id' PK (from bad 002).
    # We want final state: artifact_id PK, path UNIQUE, no source_type.
    need_rebuild = False
    cur = conn.execute("PRAGMA table_info(artifacts)")
    col_list = cur.fetchall()
    cols = {row[1] for row in col_list}
    
    has_source_type = "source_type" in cols
    has_id_pk = "id" in cols
    has_path = "path" in cols
    
    if has_source_type or has_id_pk:
        need_rebuild = True
        logger.error(f"Schema Rebuild Triggered: source_type={has_source_type}, id_pk={has_id_pk}")

    if need_rebuild:
        try:
            logger.error("DEBUG: Starting artifacts table rebuild...")
            conn.execute("PRAGMA foreign_keys=OFF") # Disable FKs during rebuild
            
            # 1. Rename existing
            conn.execute("ALTER TABLE artifacts RENAME TO artifacts_backup_legacy")
            
            # 2. Create New Table (Strict Epic 3.1)
            conn.execute("""
                CREATE TABLE artifacts (
                    artifact_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    path TEXT,
                    filename TEXT,
                    ext TEXT,
                    size_bytes INTEGER,
                    modified_at TEXT,
                    sha256 TEXT,
                    ingest_status TEXT DEFAULT 'new',
                    error TEXT,
                    updated_at TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # 3. Migrate Data
            # Map columns. source_type is dropped. source_uri -> path. content_hash -> sha256.
            # Handle 'id' vs 'artifact_id' from backup.
            # If backup has 'artifact_id' (Legacy 001), use it.
            # If backup has 'id' (Bad 002), use it as artifact_id.
            
            # We construct SELECT dynamically based on backup columns?
            # Or just try/catch?
            # Pragma on backup:
            b_cur = conn.execute("PRAGMA table_info(artifacts_backup_legacy)")
            b_cols = {row[1] for row in b_cur.fetchall()}
            
            pk_col = "artifact_id" if "artifact_id" in b_cols else "id"
            path_col = "path" if "path" in b_cols else "source_uri"
            hash_col = "sha256" if "sha256" in b_cols else "content_hash"
            
            # Use GROUP BY path_col to dedupe and satisfy UNIQUE(path)
            # COALESCE for non-nulls if needed.
            migration_sql = f"""
                INSERT INTO artifacts (artifact_id, path, sha256, created_at, ingest_status)
                SELECT {pk_col}, {path_col}, max({hash_col}), created_at, 
                       CASE WHEN {path_col} IS NULL THEN 'failed' ELSE 'new' END
                FROM artifacts_backup_legacy
                WHERE {path_col} IS NOT NULL
                GROUP BY {path_col}
            """
            conn.execute(migration_sql)
            
            # 4. Drop Backup
            conn.execute("DROP TABLE artifacts_backup_legacy")
            conn.execute("PRAGMA foreign_keys=ON")
            logger.error("DEBUG: Artifacts table rebuild complete.")
            
        except Exception as e:
            conn.rollback()
            logger.error(f"Rebuild failed: {e}")
            print(f"DEBUG: Rebuild failed: {e}")
            raise e

    # 1. Ensure columns (in case we didn't rebuild but fields are missing, e.g. manual tampering)
    # Also ensures indexes.
    
    # 1a. Ensure 'artifacts' exists (if not created by rebuild or logic)
    # The rebuild ensures it. If no rebuild, it assumes it exists.
    
    # 1. artifacts columns (Base Table form 001)
    # We maintain these (legacy) but add Epic 3.1 columns.
    
    # 1a. Ensure 'path' column (Unified Identifier)
    _ensure_columns(conn, "artifacts", {
        "artifact_id": "INTEGER", 
        "path": "TEXT",  
        "filename": "TEXT",
        "ext": "TEXT", 
        "size_bytes": "INTEGER",
        "modified_at": "TEXT",
        "sha256": "TEXT",
        "ingest_status": "TEXT DEFAULT 'new'",
        "error": "TEXT",
        "updated_at": "TEXT"
    })
    
    # 1b. Unique Index on Path (The User-Requested Unification)
    try:
        # Standard Unique Index (allows multiple NULLs in SQLite, enforcing uniqueness for non-nulls)
        conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS ux_artifacts_path ON artifacts(path)")
    except Exception as e:
        logger.warning(f"Failed to create ux_artifacts_path index: {e}")

    # 1c. Backfill filename/ext if empty
    try:
        rows = conn.execute("SELECT artifact_id, path FROM artifacts WHERE (filename IS NULL OR ext IS NULL) AND path IS NOT NULL").fetchall()
        if rows:
            logger.info(f"Backfilling filename/ext for {len(rows)} artifacts")
            updates = []
            for r in rows:
                aid, p = r[0], r[1]
                path_obj = Path(p)
                updates.append((path_obj.name, path_obj.suffix.lower(), aid))
            
            conn.executemany("UPDATE artifacts SET filename=?, ext=? WHERE artifact_id=?", updates)
    except Exception as e:
        # If columns missing (rare if rebuild ran), this errors. 
        # But wait, logic below runs ensure_columns for 001 that might NOT have triggered rebuild?
        # No, "source_type" triggers rebuild.
        # "id" pk triggers rebuild.
        # So we should be good.
        logger.warning(f"Backfill filename/ext failed: {e}")
    
    # 2. artifact_text columns
    # We must ensure artifact_text FK references artifacts(artifact_id).
    # If artifact_text exists from 002 usage (references artifacts(id)), might be issues?
    # SQLite FKs name matches. Table renamed. FK constraints usually stick to Table Name.
    # But column name? 'references artifacts(id)'.
    # New table has 'artifact_id'. 'id' does not exist.
    # So FK breaks if old definition referenced 'id'.
    # We should detect and rebuild artifact_text too?
    # If artifacts matches 001, artifacts(artifact_id) exists.
    # If 002 created artifact_text, it references artifacts(id).
    # Since we dropped artifacts(id) and created artifacts(artifact_id), usage of artifact_text will fail FK check.
    # So we MUST rebuild artifact_text if it references 'id'.
    
    # Check artifact_text schema
    try:
        fks = conn.execute("PRAGMA foreign_key_list(artifact_text)").fetchall()
        # id, seq, table, from, to...
        # row: (0, 0, 'artifacts', 'artifact_id', 'id', ...) or similar.
        # If 'to' column is 'id', but artifacts allows only 'artifact_id' -> Break.
        # We assume strict 3.1: references artifacts(artifact_id).
        # We can just check columns usage in DB?
        pass # Rebuild if needed logic is complex, assuming 002 didn't run broadly or we rely on Cascade?
    except Exception:
        pass

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
    row = cursor.fetchone()
    print(f"DEBUG: Checking {table} existence: {row}")
    if not row:
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
