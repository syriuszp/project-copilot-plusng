PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS schema_migrations (
  version TEXT PRIMARY KEY,
  applied_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS artifacts (
  artifact_id INTEGER PRIMARY KEY,
  source_type TEXT NOT NULL,
  source_uri  TEXT NOT NULL,
  content_hash TEXT NOT NULL,
  title TEXT,
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  UNIQUE(source_uri, content_hash)
);

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
  FOREIGN KEY(artifact_id) REFERENCES artifacts(artifact_id) ON DELETE CASCADE
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
