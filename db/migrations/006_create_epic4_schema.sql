PRAGMA foreign_keys=OFF;

DROP TABLE IF EXISTS chunks;
CREATE TABLE chunks (
    chunk_rowid INTEGER PRIMARY KEY AUTOINCREMENT,
    chunk_id TEXT NOT NULL UNIQUE,
    artifact_id TEXT NOT NULL,
    index_run_id TEXT NOT NULL,
    content_text TEXT,
    chunk_type TEXT NOT NULL, -- 'text', 'table', 'image'
    hash TEXT NOT NULL,
    position_index INTEGER NOT NULL,
    page INTEGER,
    slide INTEGER,
    section TEXT,
    bbox TEXT,
    is_active INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- FTS5 using External Content
DROP TABLE IF EXISTS chunks_fts;
CREATE VIRTUAL TABLE chunks_fts USING fts5(
    content_text,
    content='chunks', -- External content table
    content_rowid='chunk_rowid' -- Row count reference
);

DROP TABLE IF EXISTS chunk_embeddings;
CREATE TABLE chunk_embeddings (
    chunk_id TEXT NOT NULL,
    model_id TEXT NOT NULL,
    dim INTEGER NOT NULL,
    vector BLOB NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (chunk_id, model_id),
    FOREIGN KEY (chunk_id) REFERENCES chunks(chunk_id)
);

DROP TABLE IF EXISTS insights;
CREATE TABLE insights (
    insight_id TEXT PRIMARY KEY,
    index_run_id TEXT NOT NULL,
    type TEXT NOT NULL, -- 'unknown', 'decision', 'dependency'
    status TEXT DEFAULT 'open', -- 'open', 'closed'
    statement TEXT NOT NULL,
    confidence REAL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    insight_fingerprint TEXT -- P2 Hardening (Epic 4b)
);

DROP TABLE IF EXISTS insight_evidence;
CREATE TABLE insight_evidence (
    insight_id TEXT NOT NULL,
    chunk_id TEXT NOT NULL,
    PRIMARY KEY (insight_id, chunk_id),
    FOREIGN KEY (insight_id) REFERENCES insights(insight_id),
    FOREIGN KEY (chunk_id) REFERENCES chunks(chunk_id)
);

-- Indexes for performance
DROP INDEX IF EXISTS idx_chunks_artifact;
CREATE INDEX idx_chunks_artifact ON chunks(artifact_id);

DROP INDEX IF EXISTS idx_chunks_is_active;
CREATE INDEX idx_chunks_is_active ON chunks(is_active);

DROP INDEX IF EXISTS idx_chunks_run_id;
CREATE INDEX idx_chunks_run_id ON chunks(index_run_id);

DROP INDEX IF EXISTS idx_chunks_hash;
CREATE INDEX idx_chunks_hash ON chunks(hash);

DROP INDEX IF EXISTS idx_insights_run_id;
CREATE INDEX idx_insights_run_id ON insights(index_run_id);

-- P2 Hardening Index
CREATE UNIQUE INDEX IF NOT EXISTS idx_insight_fingerprint ON insights(insight_fingerprint);

PRAGMA foreign_keys=ON;
