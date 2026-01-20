
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
    # Handle both full repo path and relative path fallbacks
    try:
        if os.path.exists(MIGRATIONS_DIR):
            mig_files = sorted([f for f in os.listdir(MIGRATIONS_DIR) if f.endswith(".sql")])
            current_mig_dir = MIGRATIONS_DIR
        else:
            current_mig_dir = os.path.abspath("db/migrations")
            mig_files = sorted([f for f in os.listdir(current_mig_dir) if f.endswith(".sql")])
    except FileNotFoundError:
         current_mig_dir = "db/migrations"
         mig_files = sorted([f for f in os.listdir(current_mig_dir) if f.endswith(".sql")])
        
    conn = sqlite3.connect(db_path)
    try:
        # Enable WAL for tests too
        conn.execute("PRAGMA journal_mode=WAL;")
        
        for mig in mig_files:
            mig_path = os.path.join(current_mig_dir, mig)
            with open(mig_path, 'r', encoding='utf-8') as f:
                script = f.read()
                conn.executescript(script)
    finally:
        conn.close()
        
    return db_path
