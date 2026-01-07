-- 004_strict_schema_enforcement.sql
-- Purpose: Enforce the 'Strict' Schema as the single source of truth.
-- This replaces the Python-side ensure_schema() logic.

-- 1. Artifacts Table (Strict ID PK)
CREATE TABLE IF NOT EXISTS artifacts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    path TEXT NOT NULL,
    filename TEXT,
    ext TEXT,
    size_bytes INTEGER,
    modified_at REAL,
    sha256 TEXT,
    ingest_status TEXT DEFAULT 'new',
    error TEXT,
    updated_at TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_artifacts_path UNIQUE(path)
);

-- 2. Artifact Text (1:1 Relation)
CREATE TABLE IF NOT EXISTS artifact_text (
    artifact_id INTEGER PRIMARY KEY,
    text TEXT,
    extracted_at TEXT,
    extractor TEXT,
    chars INTEGER,
    FOREIGN KEY(artifact_id) REFERENCES artifacts(id) ON DELETE CASCADE
);

-- 3. Telemetry (Index Runs)
CREATE TABLE IF NOT EXISTS index_runs (
    run_id TEXT PRIMARY KEY,
    started_at TEXT,
    ended_at TEXT,
    env TEXT,
    ingest_dir TEXT,
    files_seen INTEGER,
    files_indexed INTEGER,
    files_failed INTEGER,
    files_not_extractable INTEGER,
    fts_enabled INTEGER DEFAULT 0
);

-- 4. Indexes (Performance)
CREATE INDEX IF NOT EXISTS idx_artifacts_ext ON artifacts(ext);
CREATE INDEX IF NOT EXISTS idx_artifacts_status ON artifacts(ingest_status);
CREATE INDEX IF NOT EXISTS idx_artifacts_modified_at ON artifacts(modified_at);

-- 5. FTS (Full Text Search)
-- Note: 'content' option allows external content table, but here we use standard FTS
-- and manage sync via app or triggers. The app manually inserts into FTS.
-- To allow FTS to be reliable, we ensure it exists.
CREATE VIRTUAL TABLE IF NOT EXISTS artifact_fts USING fts5(
    filename, 
    path, 
    text, 
    ref_id UNINDEXED
);
