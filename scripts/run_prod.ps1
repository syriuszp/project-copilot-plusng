$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $repoRoot

$prodRoot = Resolve-Path (Join-Path $repoRoot "..\prod")
$pythonProd = Join-Path $prodRoot "venv\Scripts\python.exe"
if (!(Test-Path $pythonProd)) { throw "PROD python not found: $pythonProd" }

$env:PYTHONPATH = $repoRoot

& $pythonProd -m app.db.cli --config (Join-Path $prodRoot "config\config.yaml")
