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
```

## Search MVP (Epic 3.1)

**Key Features**:
- **Zero Manual SQL**: Database upgrades are handled automatically via `migrator.py` on startup.
- **Smart Indexing**: Sources page tracks NEW, DIRTY (modified), and INDEXED files. Only changed files are processed.
- **Config Hardening**: Strict validation of `config.yaml` structure. Legacy format supported but deprecated.
- **Multi-format Extraction**: Support for PDF (text-based), DOCX, and preliminary OCR placeholder logic for images/scanned PDFs.

### Indexing modes

- **Index Needed** – indexes only files with status NEW or DIRTY (recommended, fast)
- **Index All** – reindexes everything (slow, use only if needed)

The UI shows a warning banner when indexing is stale.

### Config compatibility

The application supports backward compatibility. Both formats are valid:

```yaml
search_enabled: true
fts_enabled: true
```

and

```yaml
features:
  search_enabled: true
  fts_enabled: true
```

Internally, config is normalized on startup.

### Configuration
See `config/general.yaml` for structure.
- **Extraction**: Enable OCR via `features.extraction.ocr: true`.
- **Indexing**: `paths.ingest_dir` defines the hot folder.

### External tools (Optional)

OCR and image extraction work only if binaries are present.

Expected locations:
- `tools/tesseract/tesseract(.exe)`
- `tools/poppler/pdftoppm(.exe)`

If binaries are missing, the system degrades gracefully (no crash).

**Config Flags**:
Control granular extraction in `config.yaml`:
```yaml
features:
  extraction:
    ocr: true  # Enables Tesseract/Poppler checks
    images: true
    pdf: true
    docx: true
```

**Definition of Done (Epic 3.1)**:
| Criteria | Status |
| :--- | :--- |
| **Migrations** | Applied automatically on startup (idempotent). |
| **Indexing** | Handles NEW, DIRTY, INDEXED, FAILED, NOT_EXTRACTABLE statuses. |
| **Smart UX** | "Index Needed" processes only changed files. Stale warning in Search. |
| **Extraction** | Flags in config respected. Binary detection for OCR (Tesseract/Poppler). |
| **No Manual SQL** | Schema upgrades purely code-driven. |

**DEV**:
Just run `scripts/run_dev.ps1`. Search uses `dev_data/db/dev.db`.
Files in `dev_data/ingest/` can be indexed via "Sources" -> "Index All".

**PROD**:
Required environment variables:
- `PROJECT_COPILOT_CONFIG_FILE`: Absolute path to `config.yaml`.
- `PROJECT_COPILOT_ENV`: set to `PROD`.

Search capabilities are fully config-driven. No repo dependencies.