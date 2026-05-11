"""Parse address.zip BUILDING records into a parquet file for dashboard pipeline integration.

Extracts BUILDING-type address records (14-digit cadastre) from Cadaster address.zip.
Output: data/processed/cadaster_addresses.parquet

Run once when address.zip changes:
    .venv\\Scripts\\python src/dashboard/parse_cadaster_addresses.py
"""
from __future__ import annotations

import time
import zipfile
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
ADDRESS_ZIP = PROJECT_ROOT / "_additional_data_temp" / "Cadaster" / "address.zip"
OUTPUT_PATH = PROJECT_ROOT / "data" / "processed" / "cadaster_addresses.parquet"

FIELDS = ["ARCode", "PostIndex", "County", "Parish", "Town", "Street", "House"]


def _parse_xml(zf: zipfile.ZipFile, fname: str) -> list[dict]:
    """Parse one XML file — extract BUILDING-type address records using lxml for speed."""
    from lxml import etree
    with zf.open(fname) as f:
        tree = etree.parse(f)
    records = []
    for item in tree.iter("AddressItemData"):
        obj_type = item.findtext(".//ObjectType")
        if obj_type != "BUILDING":
            continue
        cad = item.findtext(".//ObjectCadastreNr")
        if not cad or len(cad) != 14:
            continue
        rec = {"KadastraApzimBuilding": cad}
        addr = item.find("AddressData")
        if addr is not None:
            for field in FIELDS:
                el = addr.find(field)
                if el is not None and el.text:
                    rec[field] = el.text
        records.append(rec)
    return records


def main() -> None:
    print(f"Parsing {ADDRESS_ZIP.name}...")
    t0 = time.time()
    zf = zipfile.ZipFile(ADDRESS_ZIP)
    xmls = sorted([f for f in zf.namelist() if f.endswith(".xml")])
    print(f"  {len(xmls)} XML files")

    all_records: list[dict] = []
    for i, fname in enumerate(xmls):
        recs = _parse_xml(zf, fname)
        all_records.extend(recs)
        if (i + 1) % 10 == 0:
            print(f"  Parsed {i+1}/{len(xmls)} ({len(all_records):,} building records, {time.time()-t0:.0f}s)")

    print(f"  Total: {len(all_records):,} BUILDING records in {time.time()-t0:.0f}s")

    df = pd.DataFrame(all_records)
    df["KadastraApzimBuilding"] = df["KadastraApzimBuilding"].astype(str)
    # Deduplicate: keep first occurrence per building
    before = len(df)
    df = df.drop_duplicates(subset=["KadastraApzimBuilding"], keep="first")
    print(f"  Deduplicated: {before:,} → {len(df):,} unique buildings")

    df.to_parquet(OUTPUT_PATH, index=False)
    print(f"  Saved: {OUTPUT_PATH}")
    print(f"  Columns: {list(df.columns)}")
    for col in FIELDS:
        if col in df.columns:
            print(f"    {col}: {df[col].notna().sum():,} / {len(df):,} ({100*df[col].notna().sum()/len(df):.1f}%)")


if __name__ == "__main__":
    main()
