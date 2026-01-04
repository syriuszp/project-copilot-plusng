-- Migration: 002_create_artifacts_tables
-- Created at: 2026-01-03

CREATE TABLE IF NOT EXISTS artifacts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    path TEXT UNIQUE NOT NULL,
    filename TEXT NOT NULL,
    ext TEXT NOT NULL,
    size_bytes INTEGER,
    modified_at TEXT,
    sha256 TEXT,
    ingest_status TEXT NOT NULL DEFAULT 'new', -- new | indexed | failed | not_extractable
    error TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);



CREATE TABLE IF NOT EXISTS artifact_text (
    artifact_id INTEGER PRIMARY KEY REFERENCES artifacts(id) ON DELETE CASCADE,
    text TEXT,
    extracted_at TEXT,
    extractor TEXT,
    chars INTEGER
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
