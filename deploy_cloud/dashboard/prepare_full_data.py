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

GEO_DIR = PROJECT_ROOT / "data" / "raw" / "geo"

# Provenance bitmask: each bit indicates a field was derived/estimated (not from primary source)
# Bit 0 (1): address fields from full_housing_data fallback join (lstrip prefix)
# Bit 1 (2): apkaime_name from spatial join (not from EPC source)
# Bit 2 (4): gis_territory_name from cadastre prefix fallback
# Bit 3 (8): combined_epc_class is predicted (not from certificate)
# Bit 4 (16): combined_heating_kwh is predicted (not from certificate)
# Bit 5 (32): estimated_primary_energy from linear model (not actual)
# Bit 6 (64): address fields from full_housing_data exact join (secondary source)
PROV_ADDR_FALLBACK = 1
PROV_APKAIME_SPATIAL = 2
PROV_TERRITORY_PREFIX = 4
PROV_EPC_PREDICTED = 8
PROV_KWH_PREDICTED = 16
PROV_PRIMARY_ESTIMATED = 32
PROV_ADDR_SECONDARY = 64
PROV_YEAR_ESTIMATED = 128

# Mapping: column name → provenance bit(s) that indicate value is estimated/imputed
COLUMN_PROVENANCE_BITS: dict[str, int] = {
    "construction_year": PROV_YEAR_ESTIMATED,  # estimated from acceptance year
}


def _enrich_neighbourhoods(cad: pd.DataFrame) -> None:
    """Spatial-join Riga/Daugavpils neighbourhood boundaries for buildings with coords but no apkaime."""
    import geopandas as gpd

    has_coords = cad["KOORD_X"].notna() & cad["KOORD_Y"].notna()
    if "apkaime_name" not in cad.columns:
        cad["apkaime_name"] = pd.NA
    # Ensure string dtype (may be categorical from EPC merge)
    if hasattr(cad["apkaime_name"], "cat"):
        cad["apkaime_name"] = cad["apkaime_name"].astype("object")
    needs = has_coords & cad["apkaime_name"].isna()
    n_needs = int(needs.sum())
    if n_needs == 0:
        print("  Neighbourhood spatial join: nothing to enrich")
        return

    print(f"  Neighbourhood spatial join: {n_needs:,} buildings with coords need assignment...")
    # KOORD_Y = easting (x), KOORD_X = northing (y) in EPSG:3059
    pts = gpd.GeoDataFrame(
        cad.loc[needs, ["KadastraApzimBuilding"]].copy(),
        geometry=gpd.points_from_xy(cad.loc[needs, "KOORD_Y"], cad.loc[needs, "KOORD_X"]),
        crs="EPSG:3059",
    )
    total_assigned = 0

    for city, gpkg_path, name_col in [
        ("Riga", GEO_DIR / "Riga" / "apkaimes.gpkg", "apkaime"),
        ("Daugavpils", GEO_DIR / "Daugavpils" / "apkaimes_daugavpils.gpkg", "neighborhood"),
    ]:
        if not gpkg_path.exists():
            print(f"    {city}: GPKG not found at {gpkg_path}")
            continue
        enc = "cp1257" if city == "Riga" else None
        polys = gpd.read_file(gpkg_path, encoding=enc) if enc else gpd.read_file(gpkg_path)
        polys = polys.rename(columns={name_col: "NOSAUKUMS"})
        if polys.crs != pts.crs:
            polys = polys.to_crs(pts.crs)
        # Filter points to city bounding box to avoid huge spatial index
        bbox = polys.total_bounds  # minx, miny, maxx, maxy
        in_bbox = (
            (pts.geometry.x >= bbox[0]) & (pts.geometry.x <= bbox[2]) &
            (pts.geometry.y >= bbox[1]) & (pts.geometry.y <= bbox[3])
        )
        city_pts = pts.loc[in_bbox]
        if len(city_pts) == 0:
            print(f"    {city}: 0 points in bounding box")
            continue
        print(f"    {city}: {len(city_pts):,} points in bbox, joining...")
        joined = gpd.sjoin(city_pts, polys[["NOSAUKUMS", "geometry"]], how="left", predicate="intersects")
        # Drop duplicate indices (point on boundary → pick first match)
        joined = joined[~joined.index.duplicated(keep="first")]
        matched = joined["NOSAUKUMS"].notna()
        if matched.any():
            idx = joined.loc[matched].index
            cad.loc[idx, "apkaime_name"] = joined.loc[matched, "NOSAUKUMS"].values
            # Mark as spatially estimated
            cad.loc[idx, "_provenance"] |= PROV_APKAIME_SPATIAL
            # Remove matched from pts for next city
            pts = pts.loc[~pts.index.isin(idx)]
            n = int(matched.sum())
            total_assigned += n
            print(f"    {city}: {n:,} assigned")
        else:
            print(f"    {city}: 0 assigned")

    total_apk = int(cad["apkaime_name"].notna().sum())
    print(f"  Neighbourhood total: {total_apk:,}/{len(cad):,} ({total_assigned:,} newly assigned)")


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
        "acception_years",
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

    # Initialize provenance bitmask (0 = all values from primary source)
    import numpy as np
    cad["_provenance"] = np.int32(0)

    # 1b. Fill construction_year from acception_years for recent buildings (2025+)
    from datetime import datetime
    current_year = datetime.now().year
    _missing_year = cad["construction_year"].isna()
    _has_accept = cad["acception_years"].notna()
    if _has_accept.any():
        def _parse_max_accept(s: str) -> float | None:
            try:
                years = [int(y.strip()) for y in str(s).split(",") if y.strip().isdigit()]
                return max(years) if years else None
            except (ValueError, TypeError):
                return None
        _max_accept = cad["acception_years"].apply(
            lambda s: _parse_max_accept(s) if pd.notna(s) else None
        )
        _fill_mask = _missing_year & (_max_accept >= 2025)
        n_filled = _fill_mask.sum()
        if n_filled > 0:
            cad.loc[_fill_mask, "construction_year"] = float(current_year)
            cad.loc[_fill_mask, "_provenance"] |= np.int32(PROV_YEAR_ESTIMATED)
            print(f"  Filled construction_year={current_year} for {n_filled:,} buildings with recent acceptance years")
    cad.drop(columns=["acception_years"], inplace=True)

    # 2. Derive era_bin, wall_material_grouped
    print("  Deriving era_bin, wall_material_grouped...")
    cad["era_bin"] = assign_era_bins(cad["construction_year"])
    cad["wall_material_grouped"] = group_wall_materials(cad["wall_material_name"])
    cad.drop(columns=["wall_material_name"], inplace=True)

    # 3. Join address info — cadaster address register is primary, full_housing_data is secondary

    # 3a. Primary source: cadaster_addresses.parquet (from address.zip — State Address Register)
    addr_fields = ["Town", "County", "Parish", "Street", "House", "postal_code_clean"]
    cad_addr_path = PROJECT_ROOT / "data" / "processed" / "cadaster_addresses.parquet"
    primary_cads: set[str] = set()
    if cad_addr_path.exists():
        print(f"  Loading primary address source: {cad_addr_path.name}...")
        cad_addr = pd.read_parquet(cad_addr_path)
        cad_addr["KadastraApzimBuilding"] = cad_addr["KadastraApzimBuilding"].astype(str)
        cad_addr = cad_addr.rename(columns={"PostIndex": "postal_code_clean"})
        cad_addr = cad_addr.drop_duplicates(subset=["KadastraApzimBuilding"], keep="first")
        cad_addr = cad_addr[["KadastraApzimBuilding"] + [c for c in addr_fields if c in cad_addr.columns]]
        cad = cad.merge(cad_addr, on="KadastraApzimBuilding", how="left")
        primary_cads = set(cad_addr["KadastraApzimBuilding"])
        primary_matched = int(cad["House"].notna().sum())
        print(f"  Primary address join: {primary_matched:,}/{len(cad):,} matched")
    else:
        print(f"  WARNING: {cad_addr_path.name} not found — skipping primary address source")
        for col in addr_fields:
            cad[col] = pd.NA

    # 3b. Secondary source: full_housing_data (provides coords + fills address gaps)
    fhd_path = PROJECT_ROOT / "data" / "raw" / "full_housing_data.parquet"
    print(f"  Loading secondary address source: {fhd_path.name}...")
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
    print(f"  Secondary address entries: {len(addr):,}")

    # Align secondary data to cad index via merge
    sec = addr.set_index("KadastraApzimBuilding").reindex(cad["KadastraApzimBuilding"].values)
    sec.index = cad.index

    # Coords: always from secondary (address register has none)
    cad["KOORD_X"] = sec["KOORD_X"]
    cad["KOORD_Y"] = sec["KOORD_Y"]
    coord_matched = int(cad["KOORD_X"].notna().sum())
    print(f"  Coords join (exact): {coord_matched:,}/{len(cad):,}")
    # All coords are from secondary source
    cad.loc[cad["KOORD_X"].notna(), "_provenance"] |= PROV_ADDR_SECONDARY

    # Address fields: fill gaps where primary had no value
    sec_filled_count = 0
    for col in addr_fields:
        if col not in cad.columns:
            cad[col] = pd.NA
        was_missing = cad[col].isna()
        cad[col] = cad[col].fillna(sec.get(col))
        newly_filled = was_missing & cad[col].notna()
        sec_filled_count += int(newly_filled.sum())
        # Mark these as from secondary source
        cad.loc[newly_filled, "_provenance"] |= PROV_ADDR_SECONDARY
    addr_filled = int(cad["Town"].notna().sum())
    print(f"  Secondary filled {sec_filled_count:,} address gaps")
    print(f"  Address total (primary+secondary exact): {addr_filled:,}/{len(cad):,}")

    # 3c. Fallback join for Riga/Daugavpils/Jelgava: different cadastre prefixes
    unmatched_coords = cad["KOORD_X"].isna()
    n_unmatched = int(unmatched_coords.sum())
    if n_unmatched > 0:
        cad_stripped = cad.loc[unmatched_coords, "KadastraApzimBuilding"].str.lstrip("0")
        addr_stripped = addr.copy()
        addr_stripped["_stripped_key"] = addr_stripped["KadastraApzimBuilding"].str.lstrip("0")
        addr_stripped = addr_stripped.drop_duplicates(subset=["_stripped_key"], keep="first")
        strip_map = addr_stripped.set_index("_stripped_key")

        matched_mask = cad_stripped.isin(strip_map.index)
        matched_keys = cad_stripped[matched_mask]
        # Fill coords from fallback
        for col in ["KOORD_X", "KOORD_Y"]:
            cad.loc[matched_keys.index, col] = strip_map.loc[matched_keys.values, col].values
        # Fill address gaps from fallback too
        for col in addr_fields:
            gap = cad.loc[matched_keys.index, col].isna()
            if gap.any():
                gap_idx = gap[gap].index
                gap_keys = cad_stripped.loc[gap_idx]
                cad.loc[gap_idx, col] = strip_map.loc[gap_keys.values, col].values

        fallback_matched = int(matched_mask.sum())
        total_coords = int(cad["KOORD_X"].notna().sum())
        print(f"  Fallback join (stripped keys): {fallback_matched:,} additional coords → total {total_coords:,}/{len(cad):,}")
        # Mark fallback-matched rows
        cad.loc[matched_keys.index, "_provenance"] |= (PROV_ADDR_FALLBACK | PROV_ADDR_SECONDARY)

    # 3d. Geocoded coordinates (from Photon/OSM, for buildings with address but no coords)
    geocoded_path = PROJECT_ROOT / "data" / "processed" / "geocoded_coords.parquet"
    if geocoded_path.exists():
        geo = pd.read_parquet(geocoded_path)
        geo["KadastraApzimBuilding"] = geo["KadastraApzimBuilding"].astype(str)
        still_no_coords = cad["KOORD_X"].isna()
        n_before = int(still_no_coords.sum())
        geo = geo.set_index("KadastraApzimBuilding")
        for col in ["KOORD_X", "KOORD_Y"]:
            match_idx = cad.loc[still_no_coords, "KadastraApzimBuilding"]
            match_idx = match_idx[match_idx.isin(geo.index)]
            cad.loc[match_idx.index, col] = geo.loc[match_idx.values, col].values
        n_after = int(cad["KOORD_X"].isna().sum())
        n_filled = n_before - n_after
        print(f"  Geocoded coords: {n_filled:,} filled (from {len(geo):,} available) → {n_after:,} still missing")
    else:
        print("  No geocoded_coords.parquet found — skipping geocoded fill")

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
        # Mark prefix-fallback rows
        filled_mask = missing_territory & cad["gis_territory_name"].notna()
        cad.loc[filled_mask, "_provenance"] |= PROV_TERRITORY_PREFIX

    # 5. Join predictions
    pred_path = PROJECT_ROOT / "data" / "processed" / "housing_stock_predictions.parquet"
    print(f"  Loading predictions from {pred_path.name}...")
    pred = pd.read_parquet(pred_path, columns=[
        "BuildingCadastreNr", "predicted_class", "predicted_kwh",
        "confidence", "max_prob",
        "cqr_lower", "cqr_upper", "interval_width",
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
    if "apkaime_name" in cad.columns:
        _n_apk = int(cad["apkaime_name"].notna().sum())
        print(f"  Neighbourhood coverage (from EPC): {_n_apk:,}/{len(cad):,}")

    # 5b2. Neighbourhood spatial join for buildings with coords but no apkaime_name
    _enrich_neighbourhoods(cad)

    # 5c. Fill building_type from BuildingUseKindId for all unclassified buildings
    _bt_null = cad["building_type"].isna()
    cad.loc[_bt_null & (cad["BuildingUseKindId"] == "1110"), "building_type"] = "Residential_Individual"
    cad.loc[_bt_null & cad["BuildingUseKindId"].isin(["1121", "1122", "1130"]), "building_type"] = "Residential_Apartment"
    _bt_filled = _bt_null.sum() - cad["building_type"].isna().sum()
    print(f"  Building type filled from BuildingUseKindId: {_bt_filled:,} buildings")
    print(f"  Building type: {cad['building_type'].value_counts().to_dict()}")

    # 5d. Create separate and combined EPC columns
    # epc_class_cert: EPC class from certificate only (not GeoRiga)
    _is_georiga_only = cad["source"] == "GeoRiga"
    cad["epc_class_cert"] = cad["EnergoefektivKlase"].copy()
    cad.loc[_is_georiga_only, "epc_class_cert"] = pd.NA

    # epc_class_georiga: EPC class from GeoRiga only
    _has_georiga = cad["source"].isin(["GeoRiga", "Combined (EPC+GeoRiga)"])
    cad["epc_class_georiga"] = pd.NA
    cad.loc[_has_georiga, "epc_class_georiga"] = cad.loc[_has_georiga, "EnergoefektivKlase_georiga_pref"]

    # combined_epc_class: cert → georiga → predicted
    cad["combined_epc_class"] = (
        cad["epc_class_cert"]
        .fillna(cad["epc_class_georiga"])
        .fillna(cad["predicted_epc_class"])
    )
    cad["combined_heating_kwh"] = cad["EnergijaApkurei"].fillna(cad["predicted_heating_kwh"])
    # Mark rows where combined values come from prediction (not certificate/georiga)
    _is_predicted = cad["epc_class_cert"].isna() & cad["epc_class_georiga"].isna() & cad["predicted_epc_class"].notna()
    cad.loc[_is_predicted, "_provenance"] |= PROV_EPC_PREDICTED
    _kwh_predicted = cad["EnergijaApkurei"].isna() & cad["predicted_heating_kwh"].notna()
    cad.loc[_kwh_predicted, "_provenance"] |= PROV_KWH_PREDICTED

    # 5d. Derived energy columns
    # Estimated primary energy: actual if available, else linear model from combined heating
    _heating = pd.to_numeric(cad["combined_heating_kwh"], errors="coerce")
    _real_primary = pd.to_numeric(cad.get("PrimaraNeatjaunojamaEnergija"), errors="coerce")
    cad["estimated_primary_energy"] = _real_primary.fillna(1.41 * _heating + 34.18).round(1)
    # Mark rows where primary energy was estimated from linear model
    cad.loc[_real_primary.isna() & _heating.notna(), "_provenance"] |= PROV_PRIMARY_ESTIMATED

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

    # 5g. Print provenance summary
    _p = cad["_provenance"]
    print(f"  Provenance summary:")
    print(f"    Address from secondary source: {(_p & PROV_ADDR_SECONDARY > 0).sum():,}")
    print(f"    Address from fallback join: {(_p & PROV_ADDR_FALLBACK > 0).sum():,}")
    print(f"    Neighbourhood from spatial join: {(_p & PROV_APKAIME_SPATIAL > 0).sum():,}")
    print(f"    Territory from prefix fallback: {(_p & PROV_TERRITORY_PREFIX > 0).sum():,}")
    print(f"    EPC class predicted: {(_p & PROV_EPC_PREDICTED > 0).sum():,}")
    print(f"    Heating kWh predicted: {(_p & PROV_KWH_PREDICTED > 0).sum():,}")
    print(f"    Primary energy estimated: {(_p & PROV_PRIMARY_ESTIMATED > 0).sum():,}")

    # 5b. Pre-compute WGS84 coordinates for map display
    _has_coords = cad["KOORD_X"].notna() & cad["KOORD_Y"].notna()
    if _has_coords.any():
        from pyproj import Transformer
        _t = Transformer.from_crs("EPSG:3059", "EPSG:4326", always_xy=True)
        # EPSG:3059: KOORD_X=northing, KOORD_Y=easting
        _lons, _lats = _t.transform(
            cad.loc[_has_coords, "KOORD_Y"].values,
            cad.loc[_has_coords, "KOORD_X"].values,
        )
        cad["lat_4326"] = np.nan
        cad["lon_4326"] = np.nan
        cad.loc[_has_coords, "lat_4326"] = np.round(_lats, 6)
        cad.loc[_has_coords, "lon_4326"] = np.round(_lons, 6)
        print(f"  Pre-computed WGS84 coords for {_has_coords.sum():,} buildings")

    # 6. Round floats, select columns, save
    float_cols = cad.select_dtypes(include="float").columns
    # Preserve precision for WGS84 coordinates (6 decimals ≈ 0.1m accuracy)
    _no_round = {"lat_4326", "lon_4326"}
    _round_cols = [c for c in float_cols if c not in _no_round]
    cad[_round_cols] = cad[_round_cols].round(1)

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
    con.execute("CREATE INDEX idx_apkaime ON buildings (apkaime_name)")
    row_count = con.execute("SELECT count(*) FROM buildings").fetchone()[0]
    con.close()
    print(f"\n  DuckDB: {db_path}")
    print(f"  Rows: {row_count:,}")
    print(f"  File size: {db_path.stat().st_size / 1024 / 1024:.1f} MB")


if __name__ == "__main__":
    main()
