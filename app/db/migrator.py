
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
    Enforces Strict Epic 3.1 Schema:
    - artifacts: artifact_id PK, path UNIQUE, no legacy columns.
    - artifact_text: artifact_id PK.
    - index_runs: run_id PK.
    """
    logger.info("Ensuring Strict DB Schema (Epic 3.1 Compliance)...")
    
    # ---------------------------------------------------------
    # 1. ARTIFACTS TABLE ENFORCEMENT
    # ---------------------------------------------------------
    
    # Check 1: Does table exist?
    cur = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='artifacts'")
    if cur.fetchone() is None:
        logger.warning("Table 'artifacts' missing. This should have been created by 003 migration. Creating now.")
        # Fallback create if SQL migration failed or wasn't applied
        conn.execute("""
            CREATE TABLE IF NOT EXISTS artifacts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                path TEXT NOT NULL,
                filename TEXT,
                ext TEXT,
                size_bytes INTEGER,
                modified_at TEXT,
                sha256 TEXT,
                ingest_status TEXT DEFAULT 'new',
                error TEXT,
                updated_at TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                CONSTRAINT uq_artifacts_path UNIQUE(path)
            )
        """)

    # Check 2: Analyze Current State (Legacy detection)
    cur = conn.execute("PRAGMA table_info(artifacts)")
    cols_map = {row[1]: row for row in cur.fetchall()}
    cols = set(cols_map.keys())
    
    has_legacy_source_type = "source_type" in cols
    has_legacy_id = "id" in cols and "artifact_id" not in cols # 002 bug state
    
    # Check 3: Unique Constraint on PATH
    # SQLite: check index list for unique origin
    has_unique_path = False
    for idx in conn.execute("PRAGMA index_list(artifacts)"):
        # idx: (seq, name, unique, origin, partial)
        if idx[2] == 1: # Unique
            # Check columns in this index
            idx_cols = [c[2] for c in conn.execute(f"PRAGMA index_info({idx[1]})")]
            if idx_cols == ["path"]:
                has_unique_path = True
                break
                
    need_rebuild = has_legacy_source_type or has_legacy_id or not has_unique_path
    
    if need_rebuild:
        try:
            logger.warning(f"Strict Schema Rebuild Triggered. Legacy: {has_legacy_source_type}, BadID: {has_legacy_id}, UniquePath: {has_unique_path}")
            conn.execute("PRAGMA foreign_keys=OFF")
            
            # A. Rename
            conn.execute("ALTER TABLE artifacts RENAME TO artifacts_backup_legacy")
            
            # B. Create Strict New (PRIMARY KEY is 'id')
            conn.execute("""
                CREATE TABLE artifacts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    path TEXT NOT NULL,
                    filename TEXT,
                    ext TEXT,
                    size_bytes INTEGER,
                    modified_at TEXT,
                    sha256 TEXT,
                    ingest_status TEXT DEFAULT 'new',
                    error TEXT,
                    updated_at TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    CONSTRAINT uq_artifacts_path UNIQUE(path)
                )
            """)
            
            # C. Detect Source Map
            b_cur = conn.execute("PRAGMA table_info(artifacts_backup_legacy)")
            b_cols = {row[1] for row in b_cur.fetchall()}
            
            src_pk = "artifact_id" if "artifact_id" in b_cols else "id"
            src_path = "path" if "path" in b_cols else "source_uri"
            src_hash = "sha256" if "sha256" in b_cols else "content_hash"
            src_time = "created_at"
            
            # D. Migrate Data
            logger.info("Migrating data to strict schema (id PK)...")
            
            # Fallback for path
            if src_path not in b_cols:
                if "source" in b_cols: src_path = "source"
            
            # We map legacy PK to new 'id' if possible, or let AUTOINCREMENT handle it?
            # User wants: "Naprawcie klucz główny: artifacts.id".
            # If we preserve IDs, we should select src_pk as id.
            
            migration_sql = f"""
                INSERT INTO artifacts (id, path, sha256, created_at, ingest_status, filename, ext, size_bytes, modified_at, error, updated_at)
                SELECT 
                    MAX({src_pk}) as aid, 
                    {src_path} as p, 
                    MAX({src_hash}), 
                    MAX({src_time}), 
                    'new', 
                    MAX(filename), MAX(ext), MAX(size_bytes), MAX(modified_at), MAX(error), MAX(updated_at)
                FROM artifacts_backup_legacy
                WHERE {src_path} IS NOT NULL
                GROUP BY {src_path}
            """
            
            # Construct dynamic select
            select_parts = [f"MAX({src_pk})", f"{src_path}", f"MAX({src_hash})", f"MAX({src_time})", "'new'"]
            insert_cols = ["id", "path", "sha256", "created_at", "ingest_status"]
            
            if "filename" in b_cols: 
                select_parts.append("MAX(filename)")
                insert_cols.append("filename")
            if "ext" in b_cols: 
                select_parts.append("MAX(ext)")
                insert_cols.append("ext")
            if "size_bytes" in b_cols: 
                select_parts.append("MAX(size_bytes)")
                insert_cols.append("size_bytes")
            if "modified_at" in b_cols: 
                select_parts.append("MAX(modified_at)")
                insert_cols.append("modified_at")
            if "error" in b_cols:
                select_parts.append("MAX(error)")
                insert_cols.append("error")
            if "updated_at" in b_cols:
                select_parts.append("MAX(updated_at)")
                insert_cols.append("updated_at")

            final_sql = f"""
                INSERT INTO artifacts ({', '.join(insert_cols)})
                SELECT {', '.join(select_parts)}
                FROM artifacts_backup_legacy
                WHERE {src_path} IS NOT NULL
                GROUP BY {src_path}
            """
            
            conn.execute(final_sql)
            conn.execute("DROP TABLE artifacts_backup_legacy")
            conn.execute("PRAGMA foreign_keys=ON")
            logger.info("Strict Rebuild Complete (id PK).")
            
        except Exception as e:
            conn.rollback()
            logger.error(f"Strict Rebuild Failed: {e}")
            raise e

    # ---------------------------------------------------------
    # 2. ARTIFACT_TEXT ENFORCEMENT
    # ---------------------------------------------------------
    # ---------------------------------------------------------
    # 2. ARTIFACT_TEXT ENFORCEMENT
    # ---------------------------------------------------------
    
    # Check if table exists 
    has_text_table = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='artifact_text'").fetchone() is not None
    
    need_text_rebuild = False
    if has_text_table:
        # Check FK
        fks = conn.execute("PRAGMA foreign_key_list(artifact_text)").fetchall()
        # Expected: (id, seq, table, from, to, ...)
        # We want to='id' and from='artifact_id' and table='artifacts'
        
        # Helper to find specific FK
        valid_fk = False
        for fk in fks:
            if fk[2] == "artifacts" and fk[3] == "artifact_id" and fk[4] == "id":
                valid_fk = True
                break
        
        if not valid_fk:
            logger.warning("artifact_text has invalid FK or legacy schema. Triggering Rebuild.")
            need_text_rebuild = True
    else:
        # If missing, we must create it (003 should have, but ensure idempotent)
        logger.warning("artifact_text missing. Creating.")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS artifact_text (
                artifact_id INTEGER PRIMARY KEY,
                text TEXT,
                extracted_at TEXT,
                extractor TEXT,
                chars INTEGER,
                FOREIGN KEY(artifact_id) REFERENCES artifacts(id) ON DELETE CASCADE
            )
        """)
        
    if need_text_rebuild:
        try:
             conn.execute("ALTER TABLE artifact_text RENAME TO artifact_text_legacy")
             
             # Create New Strict
             conn.execute("""
                CREATE TABLE artifact_text (
                    artifact_id INTEGER PRIMARY KEY,
                    text TEXT,
                    extracted_at TEXT,
                    extractor TEXT,
                    chars INTEGER,
                    FOREIGN KEY(artifact_id) REFERENCES artifacts(id) ON DELETE CASCADE
                )
             """)
             
             # Migrate Data
             # Columns usually: artifact_id, text, extracted_at, extractor, chars
             # Detect what legacy has
             t_cur = conn.execute("PRAGMA table_info(artifact_text_legacy)")
             t_cols = {row[1] for row in t_cur.fetchall()}
             
             cols_to_copy = ["artifact_id", "text", "extracted_at", "extractor"]
             if "chars" in t_cols: cols_to_copy.append("chars")
             
             # Only copy if artifact_id exists in NEW artifacts table (referential integrity)
             # The new artifacts table uses 'id'.
             # Assuming artifact_id in legacy text map to 'id' in new artifacts.
             # Note: if strict artifacts rebuild happened, PKs might have shifted ONLY if we didn't preserve them.
             # In artifacts rebuild, we did SELECT MAX(id) as aid -> So we preserved IDs.
             
             conn.execute(f"""
                INSERT INTO artifact_text ({', '.join(cols_to_copy)})
                SELECT {', '.join(cols_to_copy)}
                FROM artifact_text_legacy
                WHERE artifact_id IN (SELECT id FROM artifacts) 
             """)
             
             conn.execute("DROP TABLE artifact_text_legacy")
             logger.info("artifact_text Strict Rebuild Complete.")
             
        except Exception as e:
            conn.rollback()
            logger.error(f"Failed to rebuild artifact_text: {e}")
            raise e

    # Ensure columns (double check)
    _ensure_columns(conn, "artifact_text", {
         "artifact_id": "INTEGER", 
         "text": "TEXT", 
         "extracted_at": "TEXT",
         "extractor": "TEXT",
         "chars": "INTEGER"
    })
    
    # ---------------------------------------------------------
    # 3. INDEX_RUNS
    # ---------------------------------------------------------
    _ensure_columns(conn, "index_runs", {
        "run_id": "TEXT",
        "started_at": "TEXT",
        "ended_at": "TEXT",
        "env": "TEXT",
        "ingest_dir": "TEXT",
        "files_seen": "INTEGER",
        "files_indexed": "INTEGER",
        "files_failed": "INTEGER",
        "files_not_extractable": "INTEGER"
    })

    # ---------------------------------------------------------
    # 4. FTS & INDEXES
    # ---------------------------------------------------------
    _ensure_indexes(conn)
    _ensure_fts(conn)

    logger.info("DB Strict Schema Verified.")

def _ensure_indexes(conn: sqlite3.Connection):
    try:
        conn.execute("CREATE INDEX IF NOT EXISTS idx_artifacts_ext ON artifacts(ext)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_artifacts_status ON artifacts(ingest_status)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_artifacts_modified_at ON artifacts(modified_at)")
    except Exception as e:
        logger.warning(f"Failed to create indexes: {e}")

def _ensure_columns(conn: sqlite3.Connection, table: str, required_columns: dict):
    cursor = conn.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table}'")
    if not cursor.fetchone():
         return
    
    existing_cols = {row[1]: row for row in conn.execute(f"PRAGMA table_info({table})")}
    for col_name, col_type in required_columns.items():
        if col_name not in existing_cols:
            try:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {col_name} {col_type}")
                logger.debug(f"Added column {col_name} to {table}")
            except Exception as e:
                logger.error(f"Failed to add column {table}.{col_name}: {e}")

def _ensure_fts(conn: sqlite3.Connection):
    try:
        # Check if table exists
        row = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='artifact_fts'").fetchone()
        if not row:

             conn.execute("""
                CREATE VIRTUAL TABLE IF NOT EXISTS artifact_fts USING fts5(
                    filename, 
                    path, 
                    text, 
                    ref_id
                );
            """)
    except Exception as e:
        logger.warning(f"FTS5 init failed: {e}")

def init_or_upgrade_db(db_path: Path, migrations_dir: Path):
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA foreign_keys=ON;")
    
    try:
        if migrations_dir.exists():
            apply_sql_migrations(conn, migrations_dir)
        
        ensure_schema(conn)
        
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()
