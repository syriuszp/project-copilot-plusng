$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $repoRoot

Write-Host "== DEV =="
$pythonDev = Join-Path $repoRoot ".venv\Scripts\python.exe"
if (!(Test-Path $pythonDev)) { throw "DEV python not found: $pythonDev" }

& $pythonDev -c "import sys; print('DEV python:', sys.executable)"
& $pythonDev -c "import app; print('DEV app ok')"
powershell -ExecutionPolicy Bypass -File (Join-Path $repoRoot "scripts\run_dev.ps1")

Write-Host "== PROD (wheel) =="

# In CI the sibling ../prod folder will not exist (repo-only checkout).
# Locally you *do* have ../prod and we want to validate PROD too.
$prodCandidate = Join-Path $repoRoot "..\prod"
$inCI = ($env:GITHUB_ACTIONS -eq "true")

if (!(Test-Path $prodCandidate)) {
  if ($inCI) {
    Write-Host "SKIP: PROD folder not found in CI (expected). Repo-only smoke is OK."
    Write-Host "OK: smoke test passed"
    exit 0
  } else {
    throw "PROD folder not found: $prodCandidate (expected locally)."
  }
}

$prodRoot = Resolve-Path $prodCandidate
$pythonProd = Join-Path $prodRoot "venv\Scripts\python.exe"
if (!(Test-Path $pythonProd)) { throw "PROD python not found: $pythonProd" }

& $pythonProd -c "import sys; print('PROD python:', sys.executable)"
& $pythonProd -c "import app; print('PROD app ok')"
& $pythonProd -m app.db.cli --config (Join-Path $prodRoot "config\config.yaml")

Write-Host "OK: smoke test passed"
