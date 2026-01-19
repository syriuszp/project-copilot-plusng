
import os
import sqlite3
import pytest
import uuid
import logging

# Path to migrations
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
MIGRATIONS_DIR = os.path.join(PROJECT_ROOT, "db", "migrations")

def create_test_db(tmp_path):
    """
    Creates a temporary database and applies all strict migrations.
    Returns the absolute path to the db file.
    """
    db_path = str(tmp_path / f"test_db_{uuid.uuid4()}.sqlite")
    
    # Apply migrations
    mig_files = sorted([f for f in os.listdir(MIGRATIONS_DIR) if f.endswith(".sql")])
    
    conn = sqlite3.connect(db_path)
    try:
        # Enable WAL for tests too
        conn.execute("PRAGMA journal_mode=WAL;")
        
        for mig in mig_files:
            mig_path = os.path.join(MIGRATIONS_DIR, mig)
            with open(mig_path, 'r', encoding='utf-8') as f:
                script = f.read()
                conn.executescript(script)
    finally:
        conn.close()
        
    return db_path
