PRAGMA foreign_keys=ON;

-- Rename legacy tables safely (Audit Requirement: Non-destructive)
-- Note: 'chunks' table exists from Epic 3. We rename it to preserve data.
-- We do NOT drop legacy_YYYY tables if they exist, to avoid accidental data loss during re-runs.
-- Instead, we only rename 'chunks' if 'chunks_legacy' does NOT exist.
-- But SQLite SQL script limitations: hard to do conditional logic without block.
-- Simple approach compliant with Audit: Rename blindly? No, errors if target exists.
-- Correct approach: 
-- 1. If chunks exists AND chunks_legacy does not -> RENAME.
-- 2. If chunks_legacy exists -> We assume migration already ran or partial state.

-- Since we cannot easily script "IF NOT EXISTS" for rename in standard SQL batch without wrapper:
-- We will assume standard "Apply" flow:
-- If this fails, DBA intervention needed (or wrapper handles it).
-- BUT, to pass "test_migrations_upgrade", we can just do the rename.
-- To be safe, we DROP chunks_legacy only if we are sure it's trash? 
-- Auditor said: "nie powinna dropować... bez ostrzeżenia".
-- So, let's try to just RENAME. If it fails (target exists), script fails -> Safe default.
-- BUT, if we want idempotency for local dev re-runs... 
-- Let's stick to simple rename. If chunks_legacy exists, let it fail (signal manual check).

ALTER TABLE chunks RENAME TO chunks_legacy;
ALTER TABLE insights RENAME TO insights_legacy;

-- New chunks table (Epic 4 Contract)
CREATE TABLE chunks (
  chunk_rowid INTEGER PRIMARY KEY AUTOINCREMENT,
  chunk_id TEXT UNIQUE NOT NULL,
  artifact_id TEXT NOT NULL,
  index_run_id TEXT NOT NULL,
  content_text TEXT,
  chunk_type TEXT NOT NULL,
  hash TEXT NOT NULL,
  position_index INTEGER NOT NULL,
  page INTEGER,
  slide INTEGER,
  section TEXT,
  bbox TEXT,
  is_active INTEGER NOT NULL DEFAULT 1,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_chunks_artifact_id ON chunks(artifact_id);
CREATE INDEX idx_chunks_run_id ON chunks(index_run_id);
CREATE INDEX idx_chunks_active ON chunks(is_active);

-- FTS contentless (Manual Sync)
CREATE VIRTUAL TABLE chunks_fts USING fts5(
  content_text,
  content='',
  tokenize='unicode61'
);

-- Embeddings (SQLite is SoT)
CREATE TABLE chunk_embeddings (
  chunk_id TEXT NOT NULL,
  model_id TEXT NOT NULL,
  dim INTEGER NOT NULL,
  vector BLOB NOT NULL,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (chunk_id, model_id),
  FOREIGN KEY (chunk_id) REFERENCES chunks(chunk_id)
);

-- Insights + evidence (Epic 4 Contract)
CREATE TABLE insights (
  insight_id TEXT PRIMARY KEY,
  index_run_id TEXT NOT NULL,
  type TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'open',
  statement TEXT NOT NULL,
  confidence REAL NOT NULL,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE insight_evidence (
  insight_id TEXT NOT NULL,
  chunk_id TEXT NOT NULL,
  PRIMARY KEY (insight_id, chunk_id),
  FOREIGN KEY (insight_id) REFERENCES insights(insight_id),
  FOREIGN KEY (chunk_id) REFERENCES chunks(chunk_id)
);
