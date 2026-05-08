"""
Pre-generate dashboard_full_residential.parquet for the Building Explorer dashboard.

Merges cadaster_residential (380k) with full_housing_data address info (Town/County/coords),
derives era_bin, wall_material_grouped, gis_territory_name, and joins predictions.
Output: data/interim/dashboard_full_residential.parquet (~380k rows × ~15 cols)

Run once when data changes:
    .venv\Scripts\python src/dashboard/prepare_full_data.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from utils.data_cleaning import group_wall_materials
from utils.features import assign_era_bins


# Cities that appear as "X pilsēta" in admin territory GeoJSON
_VALSTSPILSETAS = frozenset([
    "Daugavpils", "Jelgava", "Jūrmala", "Liepāja",
    "Rēzekne", "Rīga", "Ventspils",
])

# Cadastre prefix → territory name (for buildings not in full_housing_data)
# Based on official ATVK codes: 0100=Rīga, 0500=Daugavpils, 0900=Jelgava, etc.
_PREFIX_TO_TERRITORY = {
    "0100": "Rīgas pilsēta",
    "0500": "Daugavpils pilsēta",
    "0900": "Jelgavas pilsēta",
    "1300": "Jūrmalas pilsēta",
    "1700": "Liepājas pilsēta",
    "2100": "Rēzeknes pilsēta",
    "2700": "Ventspils pilsēta",
}


def _derive_territory(town: pd.Series, county: pd.Series) -> pd.Series:
    """Derive gis_territory_name from Town/County columns (vectorized)."""
    territory = county.str.replace(" nov.", " novads", regex=False)
    is_v = town.isin(_VALSTSPILSETAS)
    ends_s = town.str.endswith("s", na=False)
    city_name = pd.Series(index=town.index, dtype="object")
    city_name[is_v & ends_s] = town[is_v & ends_s] + " pilsēta"
    city_name[is_v & ~ends_s] = town[is_v & ~ends_s] + "s pilsēta"
    has_town_no_county = town.notna() & ~is_v & territory.isna()
    city_name[has_town_no_county & ends_s] = town[has_town_no_county & ends_s] + " pilsēta"
    city_name[has_town_no_county & ~ends_s] = town[has_town_no_county & ~ends_s] + "s pilsēta"
    territory = territory.where(city_name.isna(), city_name)
    return territory


def main() -> None:
    print("=== Preparing dashboard_full_residential.parquet ===")

    # 1. Load cadaster residential (380k)
    cad_path = PROJECT_ROOT / "data" / "processed" / "cadaster_residential.parquet"
    print(f"  Loading {cad_path.name}...")
    cad = pd.read_parquet(cad_path, columns=[
        "building_cadastre_nr", "building_area_m2", "ground_floors",
        "exploit_year_registry", "deprecation_raw", "use_kind_id",
        "wall_material_name", "apartment_count", "building_volume_m3",
        "underground_floors", "footprint_area_m2", "total_area_m2",
        "heating_type", "has_central_heating",
        "elem_year_walls", "elem_year_roof", "elem_year_facade",
        "elem_year_foundation", "elem_year_ceiling", "elem_year_floor",
    ])
    cad = cad.rename(columns={
        "building_cadastre_nr": "KadastraApzimBuilding",
        "building_area_m2": "BuildingArea",
        "ground_floors": "BuildingGroundFloors",
        "exploit_year_registry": "construction_year",
        "deprecation_raw": "BuildingDeprecation",
        "use_kind_id": "BuildingUseKindId",
    })
    cad["KadastraApzimBuilding"] = cad["KadastraApzimBuilding"].astype(str)
    print(f"  Cadaster: {len(cad):,} rows")

    # 2. Derive era_bin, wall_material_grouped
    print("  Deriving era_bin, wall_material_grouped...")
    cad["era_bin"] = assign_era_bins(cad["construction_year"])
    cad["wall_material_grouped"] = group_wall_materials(cad["wall_material_name"])
    cad.drop(columns=["wall_material_name"], inplace=True)

    # 3. Join address info from full_housing_data
    fhd_path = PROJECT_ROOT / "data" / "raw" / "full_housing_data.parquet"
    print(f"  Loading address info from {fhd_path.name}...")
    addr = pd.read_parquet(fhd_path, columns=[
        "KadastraApzimBuildingB", "Town", "County", "Parish",
        "Street", "House", "PostIndex", "KOORD_X", "KOORD_Y",
    ])
    addr = addr.rename(columns={
        "KadastraApzimBuildingB": "KadastraApzimBuilding",
        "PostIndex": "postal_code_clean",
    })
    addr["KadastraApzimBuilding"] = addr["KadastraApzimBuilding"].astype(str)
    addr = addr.drop_duplicates(subset=["KadastraApzimBuilding"], keep="first")
    print(f"  Address entries: {len(addr):,}")

    cad = cad.merge(addr, on="KadastraApzimBuilding", how="left")
    matched = cad["Town"].notna().sum()
    print(f"  Address join: {matched:,}/{len(cad):,} matched")

    # 4. Derive gis_territory_name
    print("  Deriving territory...")
    town_filled = cad["Town"].fillna("")
    county_filled = cad["County"].fillna("")
    cad["gis_territory_name"] = _derive_territory(town_filled, county_filled)

    # Fill unmatched rows using cadastre prefix → territory mapping
    missing_territory = cad["gis_territory_name"].isna() | (cad["gis_territory_name"] == "")
    if missing_territory.any():
        prefix = cad.loc[missing_territory, "KadastraApzimBuilding"].str[:4]
        cad.loc[missing_territory, "gis_territory_name"] = prefix.map(_PREFIX_TO_TERRITORY)
        filled = cad.loc[missing_territory, "gis_territory_name"].notna().sum()
        still_missing = missing_territory.sum() - filled
        print(f"  Prefix fallback filled {filled:,}, still missing: {still_missing:,}")

    # 5. Join predictions
    pred_path = PROJECT_ROOT / "data" / "processed" / "housing_stock_predictions.parquet"
    print(f"  Loading predictions from {pred_path.name}...")
    pred = pd.read_parquet(pred_path, columns=[
        "BuildingCadastreNr", "predicted_class", "predicted_kwh",
        "confidence", "max_prob",
    ])
    pred = pred.rename(columns={
        "BuildingCadastreNr": "KadastraApzimBuilding",
        "predicted_class": "predicted_epc_class",
        "predicted_kwh": "predicted_heating_kwh",
    })
    pred["KadastraApzimBuilding"] = pred["KadastraApzimBuilding"].astype(str)
    cad = cad.merge(pred, on="KadastraApzimBuilding", how="left")

    # 5b. Join EPC certificate + feature data for dashboard columns
    epc_path = PROJECT_ROOT / "data" / "interim" / "epc_core_featured.parquet"
    print(f"  Loading EPC features from {epc_path.name}...")
    # Columns from EPC_TABLE_COLUMNS that exist in epc_core_featured but not yet in cad
    epc_extra_cols = [
        "DokNr", "cert_date", "cert_year", "source",
        "Town_Parish", "Adrese", "Valstspilsetas", "statistical_region",
        "apkaime_name",
        "EnergoefektivKlase", "EnergijaApkurei",
        "EnergoefektivKlase_georiga_pref", "EnergijaApkurei_georiga_pref",
        "PrimaraNeatjaunojamaEnergija",
        "building_type", "ekas_veids_grouped",
        "BuildingExploitYear", "ReferencesPlatiba",
        "area_band", "wwr_archetype",
        "estimated_wall_U", "estimated_window_U", "estimated_roof_U",
        "volume_per_apartment", "area_per_apartment",
        "heating_type_grouped", "district_heating_flag",
        "is_renovated_before_epc", "renovation_count",
        "renovation_detected", "years_since_renovation",
        "partial_renovation_flag",
    ]
    epc = pd.read_parquet(epc_path, columns=["KadastraApzimBuilding"] + epc_extra_cols)
    epc["KadastraApzimBuilding"] = epc["KadastraApzimBuilding"].astype(str)
    epc = epc.drop_duplicates(subset=["KadastraApzimBuilding"], keep="first")
    cad = cad.merge(epc, on="KadastraApzimBuilding", how="left")
    epc_matched = cad["EnergoefektivKlase"].notna().sum()
    print(f"  EPC certificate join: {epc_matched:,}/{len(cad):,} matched")

    # 5c. Create combined columns (certificate preferred, else predicted)
    cad["combined_epc_class"] = cad["EnergoefektivKlase"].fillna(cad["predicted_epc_class"])
    cad["combined_heating_kwh"] = cad["EnergijaApkurei"].fillna(cad["predicted_heating_kwh"])

    # 5d. Derived energy columns
    # Estimated primary energy: actual if available, else linear model from combined heating
    _heating = pd.to_numeric(cad["combined_heating_kwh"], errors="coerce")
    _real_primary = pd.to_numeric(cad.get("PrimaraNeatjaunojamaEnergija"), errors="coerce")
    cad["estimated_primary_energy"] = _real_primary.fillna(1.41 * _heating + 34.18).round(1)

    # EU Taxonomy top 15%: buildings in the lowest 15th percentile of primary energy
    _pe = cad["estimated_primary_energy"]
    _threshold = _pe.quantile(0.15)
    cad["eu_taxonomy_top15"] = _pe <= _threshold
    print(f"  EU taxonomy 15% threshold: {_threshold:.1f} kWh/m\u00b2/yr ({cad['eu_taxonomy_top15'].sum():,} buildings)")

    # Percentile rank (lower = more efficient)
    cad["primary_energy_pctile"] = (
        cad["estimated_primary_energy"].rank(pct=True, method="average").mul(100).round(1)
    )

    # By building type
    _bt = cad.get("building_type")
    if _bt is not None:
        cad["primary_energy_pctile_type"] = (
            cad["estimated_primary_energy"]
            .groupby(_bt)
            .rank(pct=True, method="average")
            .mul(100)
            .round(1)
        )
    else:
        cad["primary_energy_pctile_type"] = None

    # 5e. Address mismatch flag (Street+House vs Adrese)
    _has_inputs = cad["Adrese"].notna() & (cad["Street"].notna() | cad["House"].notna())
    cad["address_mismatch"] = None  # default: not applicable
    if _has_inputs.any():
        subset = cad.loc[_has_inputs]
        adrese_clean = subset["Adrese"].str.replace(r"^LV-\d{4}\s*", "", regex=True).str.lower()
        street_lower = subset["Street"].fillna("").str.lower()
        house_lower = subset["House"].fillna("").str.lower()
        # Vectorized: check street substring match
        street_in = pd.array([
            s == "" or s in a
            for s, a in zip(street_lower, adrese_clean)
        ], dtype="boolean")
        house_in = pd.array([
            h == "" or h in a
            for h, a in zip(house_lower, adrese_clean)
        ], dtype="boolean")
        cad.loc[_has_inputs, "address_mismatch"] = ~(street_in & house_in)

    # 5f. Estimated from address flag (True if address was estimated via fallback)
    # For the 380k dataset, only EPC-matched rows had address estimation done
    # Mark as False/None — actual logic is only relevant for EPC rows
    cad["estimated_from_address"] = None

    # 6. Round floats, select columns, save
    float_cols = cad.select_dtypes(include="float").columns
    cad[float_cols] = cad[float_cols].round(1)

    # Convert era_bin to string for parquet (avoid categorical serialization issues)
    if "era_bin" in cad.columns:
        cad["era_bin"] = cad["era_bin"].astype(str).replace("nan", pd.NA)

    out_path = PROJECT_ROOT / "data" / "interim" / "dashboard_full_residential.parquet"
    cad.to_parquet(out_path, index=False)
    print(f"\n  Saved: {out_path}")
    print(f"  Shape: {cad.shape}")
    print(f"  Territory coverage: {cad['gis_territory_name'].notna().sum():,}/{len(cad):,}")
    print(f"  Era bin coverage: {cad['era_bin'].notna().sum():,}/{len(cad):,}")
    print(f"  Wall material coverage: {cad['wall_material_grouped'].notna().sum():,}/{len(cad):,}")
    print(f"  Predictions coverage: {cad['predicted_epc_class'].notna().sum():,}/{len(cad):,}")

    # 7. Generate DuckDB file with indices for fast dashboard queries
    import duckdb
    db_path = PROJECT_ROOT / "data" / "interim" / "dashboard_full_residential.duckdb"
    if db_path.exists():
        db_path.unlink()
    con = duckdb.connect(str(db_path))
    con.execute("CREATE TABLE buildings AS SELECT * FROM read_parquet(?)", [str(out_path)])
    con.execute("CREATE INDEX idx_territory ON buildings (gis_territory_name)")
    con.execute("CREATE INDEX idx_era ON buildings (era_bin)")
    con.execute("CREATE INDEX idx_wall ON buildings (wall_material_grouped)")
    con.execute("CREATE INDEX idx_epc ON buildings (predicted_epc_class)")
    row_count = con.execute("SELECT count(*) FROM buildings").fetchone()[0]
    con.close()
    print(f"\n  DuckDB: {db_path}")
    print(f"  Rows: {row_count:,}")
    print(f"  File size: {db_path.stat().st_size / 1024 / 1024:.1f} MB")


if __name__ == "__main__":
    main()
