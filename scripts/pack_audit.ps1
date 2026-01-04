
$ErrorActionPreference = "Stop"

$releaseDir = "releases/epic31_audit"
$zipFile = "releases/epic31_audit.zip"

write-host "Cleaning old release..."
if (Test-Path $releaseDir) { Remove-Item -Recurse -Force $releaseDir }
if (Test-Path $zipFile) { Remove-Item -Force $zipFile }

write-host "Creating directories..."
New-Item -ItemType Directory -Path "$releaseDir/docs/audit_artifacts" -Force

write-host "Copying Code..."
Copy-Item -Recurse app, config, db, scripts, tests "$releaseDir/"
Copy-Item README.md, pyproject.toml, .gitignore, requirements.txt "$releaseDir/" -ErrorAction SilentlyContinue

write-host "Copying Runtime Data..."
if (Test-Path "dev_data") {
    Copy-Item -Recurse dev_data "$releaseDir/"
} else {
    New-Item -ItemType Directory -Path "$releaseDir/dev_data/db" -Force
}
# Check excludes.
# Copy-Item -Recurse dev_data copies everything.
# We want to be sure project_copilot.dev.db is included.

write-host "Copying Artifacts..."
$artifactPath = "c:\Users\ROBBYRA\.gemini\antigravity\brain\2d89ea78-0373-4f69-9e17-50aef4591b06"
Copy-Item "$artifactPath\*.md" "$releaseDir/docs/audit_artifacts/"

write-host "Zipping..."
Compress-Archive -Path "$releaseDir/*" -DestinationPath $zipFile

write-host "Done. Zip created at $zipFile"
