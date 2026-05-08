# EPC Explorer Dashboard — Deployment Package

Self-contained dashboard for deployment to Posit Connect via GitLab.

## Structure

```
deploy/
  app.py                    ← Entry point (Posit Connect detects this)
  requirements.txt          ← Python dependencies
  dashboard/                ← Dashboard code (layout, pages, assets)
  utils/                    ← Shared utilities (bol_style)
  data/                     ← Data files (parquets, geojson, gpkg)
  sync_deploy.ps1           ← Script to sync latest code from main project
```

## Deployment

1. Run `sync_deploy.ps1` from the project root to copy latest code + data
2. Push `deploy/` to GitLab
3. Posit Connect auto-detects `app.py` as a Dash app

## Updating

After making changes to the main project dashboard code, re-run:
```powershell
.\deploy\sync_deploy.ps1
```
This copies and rewrites imports to be self-contained.
