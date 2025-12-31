$ErrorActionPreference = "Stop"

# scripts/ -> repo root
$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $repoRoot

$env:PYTHONPATH = $repoRoot

$prodRoot = Resolve-Path (Join-Path $repoRoot "..\prod")
$py = Join-Path $prodRoot "venv\Scripts\python.exe"
$cfg = Join-Path $prodRoot "config\config.yaml"
$cli = Join-Path $repoRoot "app\db\cli.py"

& $py $cli --config $cfg
