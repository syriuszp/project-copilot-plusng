from __future__ import annotations

import sqlite3
import logging
from pathlib import Path
from dataclasses import dataclass
from typing import Optional

from app.db import migrator

logger = logging.getLogger(__name__)

@dataclass
class DbInitResult:
    db_path: Path
    status: str
    error: Optional[str] = None
    applied_migrations: Optional[list] = None

def _resolve_paths(cfg: dict) -> tuple[Path, Path]:
    repo_root = Path(__file__).resolve().parents[2]
    
    # migrations_dir is simpler: always relative to repo/db/migrations
    migrations_dir = repo_root / "db" / "migrations"
    
    # db_path from config or default
    # Config structure: { "paths": { "db_path": "..." }, ... } or flattened?
    # Based on usage in state.py (config["db_path"]), it might be flat or pre-processed.
    # But database.py previously expected specific structure.
    # Let's assume cfg is the app_config dict.
    
    db_rel = cfg.get("db_path")
    if not db_rel:
        # Fallback to checking paths.db_path just in case structure varies
        if "paths" in cfg and isinstance(cfg["paths"], dict):
             db_rel = cfg["paths"].get("db_path")
    
    if not db_rel:
        # Default dev path if not specified
        db_rel = "data/project_copilot.db"
        logger.warning(f"No db_path in config, using default: {db_rel}")

    db_path = (repo_root / db_rel).resolve()
    return db_path, migrations_dir


def _sanity_check(db_path: Path):
    """
    Fast Fail: Verify critical DB integrity immediately after init.
    Ensures that 'artifacts', 'artifact_text', and strict columns exist.
    """
    try:
        with sqlite3.connect(str(db_path)) as conn:
            # 1. Check Tables
            tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            required = {"artifacts", "artifact_text", "index_runs", "schema_migrations"}
            missing = required - tables
            if missing:
                raise RuntimeError(f"DB Sanity Fail: Missing tables {missing}")
            
            # 2. Check Columns (Strict Schema 004 features)
            # artifacts must have sha256, files_not_extractable is in index_runs
            # We trust migrations mostly, but this catches incomplete runs
            cols = {r[1] for r in conn.execute("PRAGMA table_info(artifacts)")}
            if "sha256" not in cols:
                raise RuntimeError("DB Sanity Fail: 'artifacts' missing 'sha256' column (Legacy schema?)")
                
            logger.info("DB Sanity Check Passed.")
    except Exception as e:
        logger.critical(f"DB Sanity Check FAILED for {db_path}: {e}")
        raise

def init_or_upgrade_db(cfg: dict, migrations_dir: Optional[Path] = None) -> DbInitResult:
    """
    Single entrypoint for DB initialization.
    Delegates to implementation layer (app.db.migrator).
    """
    try:
        resolved_db, resolved_migrations = _resolve_paths(cfg)
        final_migrations = migrations_dir if migrations_dir else resolved_migrations
        
        logger.info(f"Initializing DB at {resolved_db} with migrations from {final_migrations}")
        applied = migrator.init_db(resolved_db, final_migrations)
        
        # Auditor P0: Fail Fast Sanity Check
        _sanity_check(resolved_db)
        
        return DbInitResult(db_path=resolved_db, status="OK", applied_migrations=applied)
    except Exception as e:
        logger.error(f"DB Init failed: {e}")
        # Return a path even in error if possible, or dummy
        # We try to resolve path at least
        try:
             db_path, _ = _resolve_paths(cfg)
        except:
             db_path = Path("unknown.db")
        return DbInitResult(db_path=db_path, status="ERROR", error=str(e))


def connect(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(str(db_path))
    con.row_factory = sqlite3.Row
    return con

