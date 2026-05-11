"""Geocode buildings missing coordinates via Photon (Komoot) geocoder.

Two-phase approach:
  Phase 1 (Python): Extract addresses from DuckDB, generate PS1 batch script
  Phase 2 (PowerShell): Run batch geocoding (bypasses corporate proxy)
  Phase 3 (Python): Parse results, transform WGS84→LKS-92, save parquet

Usage:
    .venv\\Scripts\\activate
    py src/dashboard/geocode_missing_coords.py generate   # Phase 1: generate PS1
    powershell -File data/interim/_geocode_batch.ps1       # Phase 2: run geocoding
    py src/dashboard/geocode_missing_coords.py parse       # Phase 3: parse results
"""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path
from urllib.parse import quote

import duckdb
import pandas as pd
from pyproj import Transformer

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DUCKDB_PATH = PROJECT_ROOT / "data" / "interim" / "dashboard_full_residential.duckdb"
OUTPUT_PATH = PROJECT_ROOT / "data" / "processed" / "geocoded_coords.parquet"
PS1_PATH = PROJECT_ROOT / "data" / "interim" / "_geocode_batch.ps1"
RAW_CSV_PATH = PROJECT_ROOT / "data" / "interim" / "_geocode_raw_results.csv"

_transformer = Transformer.from_crs("EPSG:4326", "EPSG:3059", always_xy=True)

PREFIX_TO_TOWN: dict[str, str] = {
    "0100": "Rīga", "1000": "Rīga", "1001": "Rīga",
    "0500": "Daugavpils", "0900": "Jelgava",
    "1300": "Jūrmala", "0270": "Liepāja",
    "0170": "Ventspils", "0210": "Rēzekne",
    "0090": "Jēkabpils", "0800": "Valmiera",
    "0560": "Ogre",
}


def _get_addresses() -> pd.DataFrame:
    """Get buildings needing geocoding from DuckDB."""
    con = duckdb.connect(str(DUCKDB_PATH), read_only=True)
    df = con.execute("""
        SELECT KadastraApzimBuilding, Town, Street, House, Parish, County
        FROM buildings
        WHERE KOORD_X IS NULL AND Street IS NOT NULL AND House IS NOT NULL
    """).fetchdf()
    con.close()

    # Fill missing Town: cadastre prefix → Parish → County
    mask = df["Town"].isna()
    if mask.any():
        prefixes = df.loc[mask, "KadastraApzimBuilding"].str[:4]
        df.loc[mask, "Town"] = prefixes.map(PREFIX_TO_TOWN)

    # For remaining gaps, use Parish name (strip " pag." suffix)
    mask2 = df["Town"].isna() & df["Parish"].notna()
    if mask2.any():
        df.loc[mask2, "Town"] = df.loc[mask2, "Parish"].str.replace(r"\s*pag\.\s*$", "", regex=True)

    # Last resort: County name (strip " nov." suffix)
    mask3 = df["Town"].isna() & df["County"].notna()
    if mask3.any():
        df.loc[mask3, "Town"] = df.loc[mask3, "County"].str.replace(r"\s*nov\.\s*$", "", regex=True)

    return df.dropna(subset=["Town"])


def generate() -> None:
    """Phase 1: Generate PowerShell batch geocoding script."""
    df = _get_addresses()

    # Skip already-done
    already_done: set[str] = set()
    if OUTPUT_PATH.exists():
        prev = pd.read_parquet(OUTPUT_PATH)
        already_done = set(prev["KadastraApzimBuilding"])

    todo = df[~df["KadastraApzimBuilding"].isin(already_done)]
    print(f"Total addresses: {len(df)}, already done: {len(already_done)}, remaining: {len(todo)}")

    lines = [
        '# Auto-generated Photon geocoding batch script',
        f'$outFile = "{RAW_CSV_PATH}"',
        '"cadastre,lat,lon" | Out-File -FilePath $outFile -Encoding utf8',
        '$total = ' + str(len(todo)),
        '$i = 0',
        '$success = 0',
        '',
    ]

    for _, row in todo.iterrows():
        cad = row["KadastraApzimBuilding"]
        q = f"{row['Street']} {row['House']}, {row['Town']}, Latvia"
        url = f"https://photon.komoot.io/api/?q={quote(q)}&limit=1&lang=en"
        # Escape for PS string
        url_escaped = url.replace("'", "''")
        lines.append(f"$i++")
        lines.append(f"try {{")
        lines.append(f"  $r = Invoke-WebRequest -Uri '{url_escaped}' -UseDefaultCredentials -UseBasicParsing -TimeoutSec 10")
        lines.append(f"  $j = $r.Content | ConvertFrom-Json")
        lines.append(f"  if ($j.features.Count -gt 0) {{")
        lines.append(f"    $lon = $j.features[0].geometry.coordinates[0]")
        lines.append(f"    $lat = $j.features[0].geometry.coordinates[1]")
        lines.append(f'    "{cad},$lat,$lon" | Out-File -FilePath $outFile -Append -Encoding utf8')
        lines.append(f"    $success++")
        lines.append(f"  }}")
        lines.append(f"}} catch {{ }}")
        lines.append(f'if ($i % 100 -eq 0) {{ Write-Host "Progress: $i/$total (success=$success)" }}')
        lines.append(f"Start-Sleep -Milliseconds 500")
        lines.append("")

    lines.append('Write-Host "Done: $success/$total geocoded"')

    PS1_PATH.write_text("\n".join(lines), encoding="utf-8")
    print(f"Generated: {PS1_PATH}")
    print(f"Run: powershell -ExecutionPolicy Bypass -File \"{PS1_PATH}\"")


def parse() -> None:
    """Phase 3: Parse CSV results, transform coords, save parquet."""
    if not RAW_CSV_PATH.exists():
        print(f"No results file: {RAW_CSV_PATH}")
        return

    raw = pd.read_csv(RAW_CSV_PATH, dtype=str)
    print(f"Raw results: {len(raw)} rows")

    raw["lat"] = raw["lat"].astype(float)
    raw["lon"] = raw["lon"].astype(float)

    # Transform WGS84 → LKS-92
    eastings, northings = _transformer.transform(
        raw["lon"].values, raw["lat"].values
    )
    # DB convention: KOORD_X=Northing, KOORD_Y=Easting
    raw["KOORD_X"] = northings
    raw["KOORD_Y"] = eastings

    out = raw.rename(columns={"cadastre": "KadastraApzimBuilding", "lat": "geocoded_lat", "lon": "geocoded_lon"})

    # Merge with any previous results
    if OUTPUT_PATH.exists():
        prev = pd.read_parquet(OUTPUT_PATH)
        out = pd.concat([prev, out]).drop_duplicates(subset="KadastraApzimBuilding", keep="last")

    out.to_parquet(OUTPUT_PATH, index=False)
    print(f"Saved {len(out)} records to {OUTPUT_PATH}")

    # Validate coordinate ranges
    print(f"  KOORD_X range: {out['KOORD_X'].min():.0f} - {out['KOORD_X'].max():.0f} (expected ~175k-450k)")
    print(f"  KOORD_Y range: {out['KOORD_Y'].min():.0f} - {out['KOORD_Y'].max():.0f} (expected ~300k-750k)")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "generate"
    if cmd == "generate":
        generate()
    elif cmd == "parse":
        parse()
    else:
        print(f"Unknown command: {cmd}. Use 'generate' or 'parse'.")
