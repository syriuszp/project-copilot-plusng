PRAGMA foreign_keys=OFF;

-- 1. chunks_fts
DROP TABLE IF EXISTS chunks_fts_legacy_backup;
DROP TABLE IF EXISTS chunks_fts;

-- 2. chunks
DROP TABLE IF EXISTS chunks_legacy_backup;
DROP TABLE IF EXISTS chunks;

-- 3. chunk_embeddings
DROP TABLE IF EXISTS chunk_embeddings_legacy_backup;
DROP TABLE IF EXISTS chunk_embeddings;

-- 4. insights
DROP TABLE IF EXISTS insights_legacy_backup;
DROP TABLE IF EXISTS insights;

-- 5. insight_evidence
DROP TABLE IF EXISTS insight_evidence_legacy_backup;
DROP TABLE IF EXISTS insight_evidence;

PRAGMA foreign_keys=ON;
