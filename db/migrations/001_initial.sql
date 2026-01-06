PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS schema_migrations (
  version TEXT PRIMARY KEY,
  applied_at TEXT NOT NULL DEFAULT (datetime('now'))
);

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

CREATE TABLE IF NOT EXISTS artifact_text (
    artifact_id INTEGER PRIMARY KEY,
    text TEXT,
    extracted_at TEXT,
    extractor TEXT,
    chars INTEGER,
    FOREIGN KEY(artifact_id) REFERENCES artifacts(id) ON DELETE CASCADE
);

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

CREATE VIRTUAL TABLE IF NOT EXISTS artifact_fts USING fts5(
    filename, 
    path, 
    text, 
    ref_id UNINDEXED
);

-- Legacy tables preserved but updated for consistency
CREATE TABLE IF NOT EXISTS chunks (
  chunk_id INTEGER PRIMARY KEY,
  artifact_id INTEGER NOT NULL,
  chunk_type TEXT NOT NULL,
  content_text TEXT NOT NULL,
  page INTEGER,
  bbox TEXT,
  embedding BLOB,
  tags TEXT,
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  FOREIGN KEY(artifact_id) REFERENCES artifacts(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS insights (
  insight_id INTEGER PRIMARY KEY,
  insight_type TEXT NOT NULL,
  statement TEXT NOT NULL,
  confidence REAL,
  evidence_chunk_ids TEXT,
  status TEXT NOT NULL DEFAULT 'new',
  created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_chunks_artifact_id ON chunks(artifact_id);
CREATE INDEX IF NOT EXISTS idx_insights_type ON insights(insight_type);

-- Validation Indexes
CREATE INDEX IF NOT EXISTS idx_artifacts_ext ON artifacts(ext);
CREATE INDEX IF NOT EXISTS idx_artifacts_status ON artifacts(ingest_status);
CREATE INDEX IF NOT EXISTS idx_artifacts_modified_at ON artifacts(modified_at);

