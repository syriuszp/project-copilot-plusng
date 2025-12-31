$ErrorActionPreference = "Stop"

# scripts/ -> repo root
$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $repoRoot

$py = Join-Path $repoRoot ".venv\Scripts\python.exe"
$cfg = Join-Path $repoRoot "config\dev.yaml"

& $py -m app.db.cli --config $cfg
