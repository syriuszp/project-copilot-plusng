$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $repoRoot

Write-Host "== DEV =="
& (Join-Path $repoRoot ".venv\Scripts\python.exe") -c "import sys; print('DEV python:', sys.executable)"
& (Join-Path $repoRoot ".venv\Scripts\python.exe") -c "import app; print('DEV app ok')"
powershell -ExecutionPolicy Bypass -File (Join-Path $repoRoot "scripts\run_dev.ps1")

Write-Host "== PROD (wheel) =="
$prodRoot = Resolve-Path (Join-Path $repoRoot "..\prod")
$pythonProd = Join-Path $prodRoot "venv\Scripts\python.exe"
& $pythonProd -c "import sys; print('PROD python:', sys.executable)"
& $pythonProd -c "import app; print('PROD app ok')"
& $pythonProd -m app.db.cli --config (Join-Path $prodRoot "config\config.yaml")

Write-Host "OK: smoke test passed"
