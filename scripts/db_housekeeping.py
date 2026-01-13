import sqlite3
import argparse
import logging
from typing import List
import os

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def list_legacy_tables(db_path: str) -> List[str]:
    if not os.path.exists(db_path):
        return []
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE '%_legacy_backup'")
        tables = [row[0] for row in cursor.fetchall()]
        return tables
    finally:
        conn.close()

def drop_legacy_tables(db_path: str, dry_run: bool = True):
    tables = list_legacy_tables(db_path)
    if not tables:
        logger.info("No legacy tables found.")
        return

    logger.info(f"Found {len(tables)} legacy tables: {tables}")
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    try:
        for table in tables:
            if dry_run:
                logger.info(f"[DRY RUN] Would DROP TABLE {table}")
            else:
                logger.info(f"Dropping table {table}...")
                cursor.execute(f"DROP TABLE IF EXISTS {table}")
        conn.commit()
    finally:
        conn.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Clean up legacy backup tables.")
    parser.add_argument("--db-path", default="data/project_copilot.db", help="Path to SQLite DB")
    parser.add_argument("--force", action="store_true", help="Execute drops (disable dry-run)")
    
    args = parser.parse_args()
    
    if not os.path.exists(args.db_path):
        logger.error(f"Database not found at {args.db_path}")
        exit(1)
        
    drop_legacy_tables(args.db_path, dry_run=not args.force)
