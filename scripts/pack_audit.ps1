
$ErrorActionPreference = "Stop"

$releaseDir = "releases/search_fix_audit"
$zipFile = "releases/search_fix_audit.zip"

write-host "Cleaning old release..."
if (Test-Path $releaseDir) { Remove-Item -Recurse -Force $releaseDir }
if (Test-Path $zipFile) { Remove-Item -Force $zipFile }

write-host "Creating directories..."
New-Item -ItemType Directory -Path "$releaseDir/docs/audit_artifacts" -Force

write-host "Copying Code..."
Copy-Item -Recurse app, config, db, scripts, tests "$releaseDir/"
Copy-Item README.md, pyproject.toml, .gitignore "$releaseDir/" -ErrorAction SilentlyContinue

write-host "Copying Runtime Data..."
if (Test-Path "dev_data") {
    # Exclude index to save space if needed, but for audit usually keep DB
    Copy-Item -Recurse dev_data "$releaseDir/"
} else {
    New-Item -ItemType Directory -Path "$releaseDir/dev_data/db" -Force
}

write-host "Copying Artifacts..."
$artifactPath = "C:\Users\ROBBYRA\.gemini\antigravity\brain\3267939f-d72f-4968-beb8-803725810142"
Copy-Item "$artifactPath\*.md" "$releaseDir/docs/audit_artifacts/"

write-host "Zipping..."
Compress-Archive -Path "$releaseDir/*" -DestinationPath $zipFile

write-host "Done. Zip created at $zipFile"
