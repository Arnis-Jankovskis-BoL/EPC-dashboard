$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent (Split-Path -Parent $PSCommandPath)
$DeployDir = Join-Path $ProjectRoot "deploy"

Write-Host "Syncing dashboard to deploy/ ..." -ForegroundColor Cyan

# Clean previous code
foreach ($d in @("dashboard", "utils", "data")) {
    $target = Join-Path $DeployDir $d
    if (Test-Path $target) { Remove-Item $target -Recurse -Force }
}
$appTarget = Join-Path $DeployDir "app.py"
if (Test-Path $appTarget) { Remove-Item $appTarget -Force }

# Copy dashboard code
$dashSrc = Join-Path $ProjectRoot "src\dashboard"
$dashDst = Join-Path $DeployDir "dashboard"
Copy-Item $dashSrc $dashDst -Recurse -Force
Get-ChildItem $dashDst -Directory -Recurse -Filter "__pycache__" | Remove-Item -Recurse -Force

# Copy utils
$utilsDst = Join-Path $DeployDir "utils"
New-Item $utilsDst -ItemType Directory -Force | Out-Null
Copy-Item (Join-Path $ProjectRoot "src\utils\bol_style.py") $utilsDst
Copy-Item (Join-Path $ProjectRoot "src\utils\csp.py") $utilsDst
$initPath = Join-Path $utilsDst "__init__.py"
if (-not (Test-Path $initPath)) { Set-Content $initPath "" }

# Copy data files
New-Item (Join-Path $DeployDir "data\interim") -ItemType Directory -Force | Out-Null
New-Item (Join-Path $DeployDir "data\processed") -ItemType Directory -Force | Out-Null
New-Item (Join-Path $DeployDir "data\raw\geo\Daugavpils") -ItemType Directory -Force | Out-Null
New-Item (Join-Path $DeployDir "data\raw\geo\Latvia\admin_territories") -ItemType Directory -Force | Out-Null
New-Item (Join-Path $DeployDir "data\raw\geo\Riga") -ItemType Directory -Force | Out-Null

$pairs = @{
    "data\interim\epc_core.parquet" = "data\interim\epc_core.parquet"
    "data\interim\epc_core_featured.parquet" = "data\interim\epc_core_featured.parquet"
    "data\interim\model_tree_ready.parquet" = "data\interim\model_tree_ready.parquet"
    "data\interim\dashboard_full_residential.parquet" = "data\interim\dashboard_full_residential.parquet"
    "data\interim\dashboard_full_residential.duckdb" = "data\interim\dashboard_full_residential.duckdb"
    "data\processed\housing_stock_predictions.parquet" = "data\processed\housing_stock_predictions.parquet"
    "data\raw\geo\Daugavpils\apkaimes_daugavpils.gpkg" = "data\raw\geo\Daugavpils\apkaimes_daugavpils.gpkg"
    "data\raw\geo\Daugavpils\apkaimes_daugavpils_4326.geojson" = "data\raw\geo\Daugavpils\apkaimes_daugavpils_4326.geojson"
    "data\raw\geo\Latvia\admin_territories\latvia_territories_4326.geojson" = "data\raw\geo\Latvia\admin_territories\latvia_territories_4326.geojson"
    "data\raw\geo\Riga\apkaimes_4326.geojson" = "data\raw\geo\Riga\apkaimes_4326.geojson"
}

# Copy output/plots directory for model info page
$plotsSrc = Join-Path $ProjectRoot "output\plots"
$plotsDst = Join-Path $DeployDir "output\plots"
if (Test-Path $plotsSrc) {
    New-Item $plotsDst -ItemType Directory -Force | Out-Null
    Copy-Item "$plotsSrc\*.png" $plotsDst -Force
    $pngCount = (Get-ChildItem $plotsDst -Filter "*.png").Count
    Write-Host "  [DATA] output\plots\ ($pngCount PNGs)" -ForegroundColor Green
}

foreach ($key in $pairs.Keys) {
    $src = Join-Path $ProjectRoot $key
    $dst = Join-Path $DeployDir $pairs[$key]
    if (Test-Path $src) {
        Copy-Item $src $dst -Force
        Write-Host "  [DATA] $key" -ForegroundColor Green
    } else {
        Write-Host "  [SKIP] $key not found" -ForegroundColor Yellow
    }
}

# Rewrite imports in all .py files
$pyFiles = Get-ChildItem $DeployDir -Recurse -Filter "*.py"
foreach ($pyFile in $pyFiles) {
    $content = Get-Content $pyFile.FullName -Raw
    $original = $content
    $content = $content -replace 'from src\.dashboard\.', 'from dashboard.'
    $content = $content -replace 'from src\.utils\.', 'from utils.'
    $content = $content -replace 'import src\.dashboard\.', 'import dashboard.'
    $content = $content -replace 'import src\.utils\.', 'import utils.'
    $content = $content -replace 'parents\[2\]', 'parents[1]'
    $content = $content -replace 'parents\[3\]', 'parents[2]'
    if ($content -ne $original) {
        Set-Content $pyFile.FullName $content -NoNewline
        Write-Host "  [REWRITE] $($pyFile.Name)" -ForegroundColor Magenta
    }
}

# Create app.py
$appPy = "import os`nimport sys`nfrom pathlib import Path`n`n"
$appPy += "_DEPLOY_ROOT = Path(__file__).resolve().parent`n"
$appPy += "if str(_DEPLOY_ROOT) not in sys.path:`n"
$appPy += "    sys.path.insert(0, str(_DEPLOY_ROOT))`n`n"
$appPy += "from dash import Dash`n"
$appPy += "import dash_bootstrap_components as dbc`n`n"
$appPy += "from dashboard.layout import build_layout, register_routing`n`n"
$appPy += "app = Dash(`n"
$appPy += "    __name__,`n"
$appPy += "    assets_folder=str(_DEPLOY_ROOT / ""dashboard"" / ""assets""),`n"
$appPy += "    external_stylesheets=[dbc.themes.BOOTSTRAP],`n"
$appPy += "    suppress_callback_exceptions=True,`n"
$appPy += ")`n"
$appPy += "app.title = ""EPC Explorer - Bank of Latvia""`n`n"
$appPy += "app.layout = build_layout()`n"
$appPy += "register_routing(app)`n`n"
$appPy += "server = app.server`n`n"
$appPy += "if __name__ == ""__main__"":`n"
$appPy += "    app.run(debug=False, port=8050)`n"
Set-Content $appTarget $appPy -NoNewline
Write-Host "  [CREATE] app.py" -ForegroundColor Green

Write-Host ""
Write-Host "Done! deploy/ is ready." -ForegroundColor Cyan
