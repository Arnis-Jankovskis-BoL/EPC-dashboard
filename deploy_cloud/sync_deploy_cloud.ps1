# sync_deploy_cloud.ps1 — Creates cloud deploy from local deploy + password gate
# Run AFTER sync_deploy.ps1 (which builds deploy/ from src/)

$ErrorActionPreference = "Stop"
$deployDir = Join-Path $PSScriptRoot "..\deploy"
$cloudDir = $PSScriptRoot

Write-Host "Syncing deploy_cloud/ from deploy/ ..."

# Copy everything from deploy/ except sync_deploy.ps1 and rsconnect-python/
# NOTE: Must remove existing destination folders first to avoid PowerShell
# Copy-Item -Recurse nesting bug (copies folder INSIDE existing destination).
$exclude = @("sync_deploy.ps1", "rsconnect-python")
Get-ChildItem $deployDir -Exclude $exclude | ForEach-Object {
    $dest = Join-Path $cloudDir $_.Name
    if ($_.PSIsContainer) {
        if (Test-Path $dest) {
            Remove-Item $dest -Recurse -Force
        }
        Copy-Item $_.FullName $dest -Recurse -Force
    } else {
        Copy-Item $_.FullName $dest -Force
    }
}

# Overwrite app.py with cloud version (has password gate)
Copy-Item (Join-Path $cloudDir "app_cloud.py") (Join-Path $cloudDir "app.py") -Force

Write-Host "Done! deploy_cloud/ is ready for Posit Cloud."
