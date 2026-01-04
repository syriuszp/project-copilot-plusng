-- Migration: 002_create_artifacts_tables
-- Created at: 2026-01-03

-- Modified to rely on 001_initial for artifacts base table.
-- Columns are added via migrator.py (Python-driven schema upgrade).

CREATE TABLE IF NOT EXISTS artifact_text (
    artifact_id INTEGER PRIMARY KEY,
    text TEXT,
    extracted_at TEXT,
    extractor TEXT,
    chars INTEGER,
    FOREIGN KEY(artifact_id) REFERENCES artifacts(artifact_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS index_runs (
    run_id TEXT PRIMARY KEY,
    started_at TEXT,
    ended_at TEXT,
    env TEXT,
    ingest_dir TEXT,
    files_seen INTEGER DEFAULT 0,
    files_indexed INTEGER DEFAULT 0,
    files_failed INTEGER DEFAULT 0,
    files_not_extractable INTEGER DEFAULT 0,
    fts_enabled INTEGER DEFAULT 0
);
