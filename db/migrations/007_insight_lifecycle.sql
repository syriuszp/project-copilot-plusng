-- Migration 007: Insight Lifecycle, Identity, and Telemetry (Epic 5)
-- Goal: Transform insights into knowledge management with history and stability metrics.

PRAGMA foreign_keys=OFF;

-- 1. Schema Expansion - Add new columns to insights
-- Note: insight_key is nullable initially for backfill safety. UNIQUE index comes later.
ALTER TABLE insights ADD COLUMN insight_key TEXT;
ALTER TABLE insights ADD COLUMN detection_rule_id TEXT;
ALTER TABLE insights ADD COLUMN detection_pattern TEXT;

-- Status Management
-- 'status' column already exists in 006 with DEFAULT 'open'.
-- We only add status_origin.
-- Strict validation (CHECK) will be enforced via App/Trigger.
ALTER TABLE insights ADD COLUMN status_origin TEXT DEFAULT 'system'; -- 'system' or 'manual'
ALTER TABLE insights ADD COLUMN status_updated_at TIMESTAMP;
ALTER TABLE insights ADD COLUMN previous_status TEXT;

-- Superseded Relationship (One-way: Old -> New)
ALTER TABLE insights ADD COLUMN superseded_by_insight_id TEXT;
ALTER TABLE insights ADD COLUMN status_comment TEXT;

-- Timestamps & Grouping
ALTER TABLE insights ADD COLUMN first_detected_at TIMESTAMP;
ALTER TABLE insights ADD COLUMN last_confirmed_at TIMESTAMP;
ALTER TABLE insights ADD COLUMN section_hint TEXT;

-- 2. History Table for Audit & Flapping Detection (STRICT CONSTRAINTS)
CREATE TABLE IF NOT EXISTS insight_status_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    insight_id TEXT NOT NULL,
    from_status TEXT, 
    to_status TEXT NOT NULL,
    origin TEXT NOT NULL, -- 'system' or 'manual'
    run_id TEXT,
    changed_at TIMESTAMP NOT NULL,
    comment TEXT
);

CREATE INDEX IF NOT EXISTS idx_ish_insight_id ON insight_status_history(insight_id);
CREATE INDEX IF NOT EXISTS idx_ish_run_id ON insight_status_history(run_id);

-- 3. Telemetry Table for Quality Metrics
CREATE TABLE IF NOT EXISTS quality_metrics (
    run_id TEXT PRIMARY KEY,
    recorded_at TIMESTAMP NOT NULL,
    created_count INT NOT NULL DEFAULT 0,
    archived_count INT NOT NULL DEFAULT 0,
    restored_count INT NOT NULL DEFAULT 0,
    resolved_manual_count INT NOT NULL DEFAULT 0,
    flapping_count INT NOT NULL DEFAULT 0
);

PRAGMA foreign_keys=ON;
