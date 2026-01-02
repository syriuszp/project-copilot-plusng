$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$prodRoot = Resolve-Path (Join-Path $repoRoot "..\prod")

$pythonProd = Join-Path $prodRoot "venv\Scripts\python.exe"
if (!(Test-Path $pythonProd)) { throw "PROD python not found: $pythonProd" }

# IMPORTANT: do NOT set PYTHONPATH to repoRoot on PROD.
# PROD must run the installed wheel from site-packages.

& $pythonProd -m app.db.cli --config (Join-Path $prodRoot "config\config.yaml")
