# Project Copilot – Plus NG

Starter repo for **Project Copilot (MES Plus NG)** with *evidence-first* ingestion and insights.

## Folders

- `app/` — application code (DB, ingestion, pipelines)
- `config/` — committed configuration templates (no secrets)
- `db/migrations/` — SQLite schema migrations (committed)
- `scripts/` — helper scripts (`run_dev.ps1`, `run_prod.ps1`)
- `tests/` — smoke tests and CI tests
- `dev_data/` — local DEV runtime data (ignored by git)

> **Local runtime (PROD) lives outside the repo** in `..\prod\` (venv, local config, db) and is not committed.

## Quick start (dev)

From repo root:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\run_dev.ps1
