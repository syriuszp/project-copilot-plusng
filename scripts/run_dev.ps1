$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $repoRoot

$pythonDev = Join-Path $repoRoot ".venv\Scripts\python.exe"
if (!(Test-Path $pythonDev)) { throw "DEV python not found: $pythonDev" }

$env:PYTHONPATH = $repoRoot

& $pythonDev -m app.db.cli --config (Join-Path $repoRoot "config\dev.yaml")
