"""Data loading and caching for the dashboard."""

from __future__ import annotations

import functools
from pathlib import Path

import pandas as pd

_PROJECT_ROOT = Path(__file__).resolve().parents[1]

# Columns to expose in the Building Explorer table
# Grouped thematically for the column picker UI
EPC_TABLE_COLUMNS: list[str] = [
    # Identification
    "KadastraApzimBuilding",
    "DokNr",
    "cert_date",
    "cert_year",
    "source",
    "address_mismatch",
    "estimated_from_address",
    # Location
    "Town_Parish",
    "Parish",
    "Street",
    "House",
    "postal_code_clean",
    "Adrese",
    "Valstspilsetas",
    "statistical_region",
    "gis_territory_name",
    "apkaime_name",
    # Energy Performance
    "EnergoefektivKlase",
    "EnergijaApkurei",
    "EnergoefektivKlase_georiga_pref",
    "EnergijaApkurei_georiga_pref",
    "PrimaraNeatjaunojamaEnergija",
    "estimated_primary_energy",
    "eu_taxonomy_top15",
    "primary_energy_pctile",
    "primary_energy_pctile_type",
    # Predicted (model proxy — available for full residential dataset)
    "predicted_epc_class",
    "predicted_heating_kwh",
    # Combined (certificate if available, otherwise predicted)
    "combined_epc_class",
    "combined_heating_kwh",
    # Physical Characteristics
    "building_type",
    "ekas_veids_grouped",
    "construction_year",
    "era_bin",
    "BuildingExploitYear",
    "BuildingArea",
    "ReferencesPlatiba",
    "BuildingGroundFloors",
    "BuildingDeprecation",
    "wall_material_grouped",
    "area_band",
    "apartment_count",
    "building_volume_m3",
    "underground_floors",
    "footprint_area_m2",
    "wwr_archetype",
    "estimated_wall_U",
    "estimated_window_U",
    "estimated_roof_U",
    "volume_per_apartment",
    "area_per_apartment",
    # Heating & Renovation
    "heating_type_grouped",
    "district_heating_flag",
    "is_renovated_before_epc",
    "renovation_count",
    "renovation_detected",
    "years_since_renovation",
    "partial_renovation_flag",
]

# Default columns shown on first load (subset for readability)
DEFAULT_VISIBLE: list[str] = [
    # Identification
    "KadastraApzimBuilding",
    # Location
    "Town_Parish",
    "Street",
    "House",
    "postal_code_clean",
    "Adrese",
    # Energy
    "EnergoefektivKlase",
    "EnergijaApkurei",
    "combined_epc_class",
    "combined_heating_kwh",
    # Physical
    "construction_year",
    "BuildingGroundFloors",
    "wall_material_grouped",
]


@functools.lru_cache(maxsize=1)
def load_epc_data() -> pd.DataFrame:
    """Load EPC core data for the Building Explorer table."""
    path = _PROJECT_ROOT / "data" / "interim" / "epc_core.parquet"
    df = pd.read_parquet(path)

    # Columns that live in the featured parquet (not in epc_core)
    featured_path = _PROJECT_ROOT / "data" / "interim" / "epc_core_featured.parquet"
    # Columns to OVERRIDE from featured parquet (better fill rate)
    _override_cols = ["construction_year"]
    # Columns that only exist in featured parquet
    _featured_cols = [
        "era_bin", "area_band", "apartment_count", "building_volume_m3",
        "underground_floors", "footprint_area_m2", "wwr_archetype",
        "estimated_wall_U", "estimated_window_U", "estimated_roof_U",
        "volume_per_apartment", "area_per_apartment",
        "heating_type_grouped", "district_heating_flag",
        "is_renovated_before_epc", "renovation_count", "renovation_detected",
        "years_since_renovation", "partial_renovation_flag",
        "statistical_region", "gis_territory_name", "apkaime_name",
    ]
    if featured_path.exists():
        # Override columns with better versions from featured parquet
        override_avail = [c for c in _override_cols if c in df.columns]
        if override_avail:
            feat_override = pd.read_parquet(featured_path, columns=override_avail)
            for c in override_avail:
                df[c] = feat_override[c]
        # Load columns that don't already exist
        need = [c for c in _featured_cols if c not in df.columns]
        if need:
            feat = pd.read_parquet(featured_path, columns=need)
            df = df.join(feat)

    # Estimate missing fields (needs KOORD_X/Y for KNN — must run before column filter)
    df = _estimate_fields_from_address(df)

    # Fill Daugavpils neighbourhoods via spatial join (needs KOORD_X/Y + gis_territory_name)
    df = _fill_daugavpils_neighbourhoods(df)

    # Derived energy fields: estimated primary energy + EU Taxonomy flag
    # Linear model: primary = 1.41 * heating + 34.18 (R²=0.65, from P16-S5)
    _heating = pd.to_numeric(df.get("EnergijaApkurei_georiga_pref", df.get("EnergijaApkurei")),
                             errors="coerce")
    _real_primary = pd.to_numeric(df.get("PrimaraNeatjaunojamaEnergija"), errors="coerce")
    df["estimated_primary_energy"] = _real_primary.fillna(1.41 * _heating + 34.18).round(1)
    # EU Taxonomy top 15%: primary energy <= 141.8 kWh/m²/yr (P16-S5 threshold, all types)
    _pe = df["estimated_primary_energy"]
    df["eu_taxonomy_top15"] = _pe <= 141.8
    # Percentile rank (lower energy = lower percentile = better)
    df["primary_energy_pctile"] = _pe.rank(pct=True, method="average").mul(100).round(1)
    # By building type (Individual houses vs Apartments)
    _bt = df.get("building_type")
    if _bt is not None:
        df["primary_energy_pctile_type"] = (
            _pe.groupby(_bt).rank(pct=True, method="average").mul(100).round(1)
        )

    # Keep only columns needed for display
    cols = [c for c in EPC_TABLE_COLUMNS if c in df.columns]
    df = df[cols].copy()

    # ID safety: cadastre always string
    if "KadastraApzimBuilding" in df.columns:
        df["KadastraApzimBuilding"] = df["KadastraApzimBuilding"].astype(str)

    # Format cert_date as YYYY-MM-DD string (avoid T00:00:00 in AG Grid)
    if "cert_date" in df.columns:
        df["cert_date"] = df["cert_date"].dt.strftime("%Y-%m-%d")

    # Shorten statistical_region values for readability
    if "statistical_region" in df.columns:
        _REGION_SHORT = {
            "Rīgas statistiskais reģions": "Rīga",
            "Kurzemes statistiskais reģions": "Kurzeme",
            "Zemgales statistiskais reģions": "Zemgale",
            "Vidzemes statistiskais reģions": "Vidzeme",
            "Latgales statistiskais reģions": "Latgale",
        }
        df["statistical_region"] = df["statistical_region"].map(_REGION_SHORT).fillna(df["statistical_region"])

    # Round floats to 1 decimal
    float_cols = df.select_dtypes(include="float").columns
    df[float_cols] = df[float_cols].round(1)

    # Derive address_mismatch: check if Street + House matches Adrese
    if all(c in df.columns for c in ("Street", "House", "Adrese")):
        df["address_mismatch"] = _detect_address_mismatch(df)

    return df


# Columns available in the full residential dataset
FULL_RESIDENTIAL_COLUMNS: list[str] = [
    "KadastraApzimBuilding",
    "BuildingArea",
    "BuildingGroundFloors",
    "construction_year",
    "BuildingDeprecation",
    "BuildingUseKindId",
    "Town",
    "Parish",
    "Street",
    "House",
    "postal_code_clean",
    "KOORD_X",
    "KOORD_Y",
    "wall_material_grouped",
    "era_bin",
    "gis_territory_name",
    "predicted_epc_class",
    "predicted_heating_kwh",
]

@functools.lru_cache(maxsize=1)
def load_full_residential() -> pd.DataFrame:
    """Load pre-computed full residential stock (380k) for dashboard.

    Source: data/interim/dashboard_full_residential.parquet
    Generated by: src/dashboard/prepare_full_data.py
    Contains cadaster_residential (380k) with era_bin, wall_material_grouped,
    gis_territory_name, and predicted EPC class/energy pre-joined.
    """
    path = _PROJECT_ROOT / "data" / "interim" / "dashboard_full_residential.parquet"
    full = pd.read_parquet(path)
    full["KadastraApzimBuilding"] = full["KadastraApzimBuilding"].astype(str)

    # Get EPC data (23k, all enriched columns)
    epc = load_epc_data().copy()

    # Remove EPC rows from cadaster (EPC versions have richer data)
    epc_ids = set(epc["KadastraApzimBuilding"]) if "KadastraApzimBuilding" in epc.columns else set()
    non_epc = full[~full["KadastraApzimBuilding"].isin(epc_ids)].copy()

    # Concatenate: EPC rows keep all columns, non-EPC get NaN for EPC-only fields
    combined = pd.concat([epc, non_epc], ignore_index=True)

    # Round floats
    float_cols = combined.select_dtypes(include="float").columns
    combined[float_cols] = combined[float_cols].round(1)

    return combined


def _fill_daugavpils_neighbourhoods(df: pd.DataFrame) -> pd.DataFrame:
    """Spatial join: assign Daugavpils neighbourhood to buildings with coordinates.

    Uses data/raw/geo/Daugavpils/apkaimes_daugavpils.gpkg (25 OSM boundaries, EPSG:3059).
    Buildings in Daugavpils with KOORD_X/Y but no apkaime_name get neighbourhood assigned.
    """
    if "apkaime_name" not in df.columns or "KOORD_X" not in df.columns:
        return df

    gpkg = _PROJECT_ROOT / "data" / "raw" / "geo" / "Daugavpils" / "apkaimes_daugavpils.gpkg"
    if not gpkg.exists():
        return df

    # Only process Daugavpils buildings missing apkaime_name
    # Convert categorical to string to allow new values
    if hasattr(df["apkaime_name"], "cat"):
        df["apkaime_name"] = df["apkaime_name"].astype("object")
    mask = (
        df["apkaime_name"].isna()
        & df["KOORD_X"].notna()
        & df["KOORD_Y"].notna()
        & (df.get("gis_territory_name") == "Daugavpils pilsēta")
    )
    if not mask.any():
        return df

    import geopandas as gpd
    from shapely.geometry import Point

    # Read Daugavpils neighbourhood polygons
    dpils_gdf = gpd.read_file(gpkg)  # EPSG:3059

    # Build GeoDataFrame from EPC building coordinates
    subset = df.loc[mask].copy()
    subset["KOORD_X"] = pd.to_numeric(subset["KOORD_X"], errors="coerce")
    subset["KOORD_Y"] = pd.to_numeric(subset["KOORD_Y"], errors="coerce")
    valid = subset["KOORD_X"].notna() & subset["KOORD_Y"].notna()
    pts = gpd.GeoDataFrame(
        subset.loc[valid],
        geometry=[Point(y, x) for x, y in zip(
            subset.loc[valid, "KOORD_X"], subset.loc[valid, "KOORD_Y"]
        )],
        crs="EPSG:3059",
    )

    # Spatial join
    joined = gpd.sjoin(pts, dpils_gdf[["neighborhood", "geometry"]], how="left", predicate="within")

    # Fill apkaime_name
    for idx in joined.index:
        nbr = joined.at[idx, "neighborhood"]
        if pd.notna(nbr):
            df.at[idx, "apkaime_name"] = nbr

    return df


def _detect_address_mismatch(df: pd.DataFrame) -> pd.Series:
    """Flag rows where Street + House does not appear in Adrese.

    Handles Adrese that may start with a postal code (e.g., "LV-1010, ...").
    """
    import re

    def _check(street: object, house: object, adrese: object) -> bool | None:
        if pd.isna(adrese) or pd.isna(street):
            return None  # can't determine
        a = str(adrese).strip()
        # Strip leading postal code (LV-XXXX or just XXXX followed by comma)
        a = re.sub(r"^(?:LV-?)?\d{4}\s*,?\s*", "", a, flags=re.IGNORECASE)
        s = str(street).strip()
        h = str(house).strip() if pd.notna(house) else ""
        # Check if street name appears in address
        if s.lower() not in a.lower():
            return True  # mismatch
        # If house is given, check it appears too
        if h and h not in a:
            return True
        return False

    return df.apply(lambda r: _check(r["Street"], r["House"], r["Adrese"]), axis=1)


def _estimate_fields_from_address(df: pd.DataFrame) -> pd.DataFrame:
    """Estimate missing Town_Parish, Street, House, Valstspilsetas, statistical_region,
    postal_code_clean, gis_territory_name from the Adrese field and coordinates.

    Algorithm overview:
    1. Parse Adrese: split by comma/space patterns.
       - First token = municipality/city (→ Town_Parish)
       - Last token that matches "Street HouseNr" pattern → Street + House
       - If no street pattern found (rural), last token = house name (→ Street)
       - Intermediate tokens may be parish/village names (skipped for now)
    2. Build lookup tables from existing data:
       - Town_Parish → (Valstspilsetas, statistical_region) via mode
       - Known municipalities suffixed with "nov." → novads name
    3. KNN spatial estimation for buildings with coordinates:
       - Use KOORD_X/KOORD_Y to find K nearest neighbours from 380k housing dataset
       - Estimate postal_code_clean, gis_territory_name, statistical_region via
         distance-weighted voting
    4. Fill missing fields, mark estimated rows.

    **Dashboard-only estimation** — for production pipeline, re-implement in
    src/02_feature_engineering.py with proper cadastre joins and geocoding.
    See docs/findings/address_estimation_algorithm.md for full documentation.
    """
    import re
    from collections import Counter

    df["estimated_from_address"] = False

    # Build lookup from existing data
    if "Town_Parish" not in df.columns:
        return df

    known = df[df["Town_Parish"].notna()].copy()
    tp_lookup: dict[str, dict[str, str]] = {}
    for tp in known["Town_Parish"].unique():
        subset = known[known["Town_Parish"] == tp]
        entry: dict[str, str] = {}
        for col in ("Valstspilsetas", "statistical_region", "gis_territory_name"):
            if col in subset.columns:
                mode = subset[col].dropna().mode()
                if len(mode):
                    entry[col] = mode.iloc[0]
        tp_lookup[tp] = entry

    # Known city names (valstspilsētas)
    _CITIES = {"Rīga", "Daugavpils", "Jelgava", "Jēkabpils", "Jūrmala",
               "Liepāja", "Ogre", "Rēzekne", "Valmiera", "Ventspils"}

    # Street indicators (Latvian)
    _STREET_INDICATORS = {"iela", "bulvāris", "prospekts", "gatve", "laukums",
                          "šosejas", "ceļš", "aleja", "līnija"}

    # Parish suffixes to strip from address parts
    _PARISH_RE = re.compile(r"^.+\s+pag\.\s*", flags=re.IGNORECASE)

    def _parse_adrese(adrese: str) -> dict:
        """Parse Adrese field into components.

        Handles patterns:
        - "Rīga, Ziedu iela 10" → town=Rīga, street=Ziedu iela, house=10
        - "Rīga, Ceru iela 2 k-2" → street=Ceru iela, house=2 k-2
        - "Stopiņu nov., Upeslejas Ērči" → town=Stopiņu nov., street=Ērči (rural)
        - "Bauskas nov., Gailīšu pag. Dižriekstiņi" → street=Dižriekstiņi (strip parish)
        - "Ķekavas nov., Ķekavas pag., Ķekava Mežakrūmiņi" → street=Mežakrūmiņi
        """
        result: dict = {"town": None, "street": None, "house": None}
        # Strip leading postal code
        clean = re.sub(r"^(?:LV-?)?\d{4}\s*,?\s*", "", adrese.strip(), flags=re.IGNORECASE)
        parts = [p.strip() for p in clean.split(",") if p.strip()]
        # Remove trailing postal code parts (e.g. "LV-5410")
        while parts and re.match(r"^(?:LV-?)?\d{4}$", parts[-1], re.IGNORECASE):
            # Capture postal code before discarding
            if "postal" not in result:
                result["postal"] = parts[-1]
            parts.pop()
        if not parts:
            return result

        result["town"] = parts[0]

        if len(parts) < 2:
            return result

        # Take the last part for street+house extraction
        last = parts[-1].strip()

        # Strip parish prefix ("Gailīšu pag. Dižriekstiņi" → "Dižriekstiņi")
        last = _PARISH_RE.sub("", last).strip()
        if not last:
            last = parts[-1].strip()  # fallback if stripping removed everything

        # Pattern: "street_name house_number [k-N]" — number (optionally with korpuss)
        # Match: "Ceru iela 2 k-2", "Ziedu iela 10", "Krasts 14"
        m = re.match(r"^(.+?)\s+(\d+(?:\s*k-\d+)?\S*)$", last)
        if m:
            candidate_street = m.group(1).strip()
            candidate_house = m.group(2).strip()
            # Verify: street should contain a street indicator or be >1 word
            candidate_lower = candidate_street.lower()
            if any(ind in candidate_lower for ind in _STREET_INDICATORS) or " " in candidate_street:
                result["street"] = candidate_street
                result["house"] = candidate_house
            else:
                # Single word + number — could be "village_name house_nr"
                # e.g., "Silabrieži Krasts 14" — treat full last as street+house
                # Try splitting differently: everything before last number group
                result["street"] = candidate_street
                result["house"] = candidate_house
        else:
            # No house number. Rural property name or street without number.
            last_lower = last.lower()
            has_street_indicator = any(ind in last_lower for ind in _STREET_INDICATORS)
            if has_street_indicator:
                result["street"] = last
            else:
                # Rural house name — use last word(s) as property name
                # If multiple words, last word is likely the property name
                result["street"] = last

        return result

    # Phase 1: Address parsing
    mask = df["Adrese"].notna() & (
        df["Town_Parish"].isna() | df["Street"].isna() | df["House"].isna()
    )
    for idx in df.index[mask]:
        adrese = str(df.at[idx, "Adrese"])
        parsed = _parse_adrese(adrese)
        estimated = False

        if parsed["town"] and pd.isna(df.at[idx, "Town_Parish"]):
            df.at[idx, "Town_Parish"] = parsed["town"]
            estimated = True

        if parsed["street"] and (pd.isna(df.at[idx, "Street"]) if "Street" in df.columns else True):
            df.at[idx, "Street"] = parsed["street"]
            estimated = True

        if parsed["house"] and (pd.isna(df.at[idx, "House"]) if "House" in df.columns else True):
            df.at[idx, "House"] = parsed["house"]
            estimated = True

        # Fill Valstspilsetas for known cities
        town = parsed["town"] or ""
        if "Valstspilsetas" in df.columns and pd.isna(df.at[idx, "Valstspilsetas"]):
            if town in _CITIES:
                df.at[idx, "Valstspilsetas"] = town
                estimated = True

        # Fill statistical_region and other fields from lookup
        tp = df.at[idx, "Town_Parish"]
        if pd.notna(tp) and tp in tp_lookup:
            for col, val in tp_lookup[tp].items():
                if col in df.columns and pd.isna(df.at[idx, col]):
                    df.at[idx, col] = val
                    estimated = True

        if estimated:
            df.at[idx, "estimated_from_address"] = True

    # Phase 2: KNN spatial estimation for buildings with coordinates but missing
    # postal_code_clean, gis_territory_name, or statistical_region
    _knn_target_cols = ["postal_code_clean", "gis_territory_name", "statistical_region"]
    knn_cols = [c for c in _knn_target_cols if c in df.columns]
    coord_cols = ["KOORD_X", "KOORD_Y"]
    if all(c in df.columns for c in coord_cols) and knn_cols:
        # Convert coords to numeric
        for c in coord_cols:
            df[c] = pd.to_numeric(df[c], errors="coerce")

        # Rows needing KNN: have coords but missing at least one target
        has_coords = df["KOORD_X"].notna() & df["KOORD_Y"].notna()
        needs_knn = has_coords & df[knn_cols].isna().any(axis=1)

        if needs_knn.any():
            # Reference set: rows with coords and all targets filled
            ref = df[has_coords & df[knn_cols].notna().all(axis=1)].copy()
            if len(ref) > 10:
                from scipy.spatial import cKDTree
                tree = cKDTree(ref[coord_cols].values)
                k = 5

                for idx in df.index[needs_knn]:
                    pt = df.loc[idx, coord_cols].values.astype(float)
                    if any(pd.isna(pt)):
                        continue
                    dists, idxs = tree.query(pt, k=min(k, len(ref)))
                    if not hasattr(idxs, "__len__"):
                        idxs = [idxs]
                        dists = [dists]

                    for col in knn_cols:
                        if pd.isna(df.at[idx, col]):
                            # Distance-weighted voting
                            votes: dict[str, float] = {}
                            for d, ri in zip(dists, idxs):
                                val = ref.iloc[ri][col]
                                if pd.notna(val):
                                    weight = 1.0 / max(d, 1.0)  # inverse distance
                                    votes[val] = votes.get(val, 0) + weight
                            if votes:
                                best = max(votes, key=votes.get)  # type: ignore[arg-type]
                                df.at[idx, col] = best
                                df.at[idx, "estimated_from_address"] = True

    # Phase 3: Lookup region/territory from NOVADS_TO_REGION + housing dataset
    _housing_path = Path("data/raw/full_housing_data.parquet")

    # Import CSP territory mappings (needed for stat_region and gis_territory)
    import sys as _sys
    _src = str(Path(__file__).resolve().parents[1])  # src/
    if _src not in _sys.path:
        _sys.path.insert(0, _src)
    from utils.csp import NOVADS_TO_REGION, VALSTSPILSETA_REGIONS
    all_region = {**NOVADS_TO_REGION, **VALSTSPILSETA_REGIONS}

    # Pre-2021 municipalities merged in 2021 reform → post-2021 novads region
    _PRE2021_REMAP: dict[str, str] = {
        "Aizputes":     "Kurzemes statistiskais reģions",
        "Beverīnas":    "Vidzemes statistiskais reģions",
        "Carnikavas":   "Rīgas statistiskais reģions",
        "Durbes":       "Kurzemes statistiskais reģions",
        "Garkalnes":    "Rīgas statistiskais reģions",
        "Lielvārdes":   "Rīgas statistiskais reģions",
        "Nīcas":        "Kurzemes statistiskais reģions",
        "Stopiņu":      "Rīgas statistiskais reģions",
    }

    # Shorten region names (same mapping as earlier in load_epc_data)
    _REGION_SHORT = {
        "Rīgas statistiskais reģions": "Rīga",
        "Kurzemes statistiskais reģions": "Kurzeme",
        "Zemgales statistiskais reģions": "Zemgale",
        "Vidzemes statistiskais reģions": "Vidzeme",
        "Latgales statistiskais reģions": "Latgale",
    }

    # 3a: statistical_region from NOVADS_TO_REGION (authoritative CSP mapping)
    if "statistical_region" in df.columns and "Town_Parish" in df.columns:
        still_missing_sr = df["statistical_region"].isna() & df["Town_Parish"].notna()
        if still_missing_sr.any():
            for idx in df.index[still_missing_sr]:
                tp = str(df.at[idx, "Town_Parish"])
                bare = re.sub(r"\s+nov\.$", "", re.sub(r"\s+pag\.$", "", tp)).strip()

                # Try tp_lookup first (exact match from existing EPC data)
                if tp in tp_lookup and "statistical_region" in tp_lookup[tp]:
                    df.at[idx, "statistical_region"] = tp_lookup[tp]["statistical_region"]
                    df.at[idx, "estimated_from_address"] = True
                    continue

                # Try NOVADS_TO_REGION (post-2021 names)
                region = all_region.get(bare) or _PRE2021_REMAP.get(bare)
                if region:
                    # Apply same shortening as dashboard display
                    df.at[idx, "statistical_region"] = _REGION_SHORT.get(region, region)
                    df.at[idx, "estimated_from_address"] = True

    # 3a-gis: gis_territory_name from tp_lookup + novads name derivation
    if "gis_territory_name" in df.columns and "Town_Parish" in df.columns:
        # Pre-2021 municipalities → post-2021 novads name (gis_territory format)
        _PRE2021_TO_GIS: dict[str, str] = {
            "Aizputes":     "Dienvidkurzemes novads",
            "Beverīnas":    "Valmieras novads",
            "Carnikavas":   "Ādažu novads",
            "Durbes":       "Dienvidkurzemes novads",
            "Garkalnes":    "Ropažu novads",
            "Lielvārdes":   "Ogres novads",
            "Nīcas":        "Dienvidkurzemes novads",
            "Stopiņu":      "Ropažu novads",
        }
        # Cities → pilsēta form
        _CITY_TO_GIS: dict[str, str] = {
            "Rīga":       "Rīgas pilsēta",
            "Daugavpils":  "Daugavpils pilsēta",
            "Jelgava":     "Jelgavas pilsēta",
            "Jēkabpils":   "Jēkabpils novads",  # absorbed into novads
            "Jūrmala":     "Jūrmalas pilsēta",
            "Liepāja":     "Liepājas pilsēta",
            "Ogre":        "Ogres novads",  # absorbed into novads
            "Rēzekne":     "Rēzeknes pilsēta",
            "Valmiera":    "Valmieras novads",  # absorbed into novads
            "Ventspils":   "Ventspils pilsēta",
        }

        still_missing_gis = df["gis_territory_name"].isna() & df["Town_Parish"].notna()
        if still_missing_gis.any():
            for idx in df.index[still_missing_gis]:
                tp = str(df.at[idx, "Town_Parish"])

                # 1) Try tp_lookup (exact match from known EPC data)
                if tp in tp_lookup and "gis_territory_name" in tp_lookup.get(tp, {}):
                    df.at[idx, "gis_territory_name"] = tp_lookup[tp]["gis_territory_name"]
                    df.at[idx, "estimated_from_address"] = True
                    continue

                # 2) Derive from "X nov." → "X novads"
                bare = re.sub(r"\s+nov\.$", "", re.sub(r"\s+pag\.$", "", tp)).strip()

                # Check pre-2021 remap
                gis = _PRE2021_TO_GIS.get(bare)
                if gis:
                    df.at[idx, "gis_territory_name"] = gis
                    df.at[idx, "estimated_from_address"] = True
                    continue

                # Check city
                gis = _CITY_TO_GIS.get(bare)
                if gis:
                    df.at[idx, "gis_territory_name"] = gis
                    df.at[idx, "estimated_from_address"] = True
                    continue

                # Expand "nov." → "novads" for post-2021 novads names
                if tp.endswith(" nov."):
                    # Check if bare name is a known novads (in NOVADS_TO_REGION)
                    if bare in NOVADS_TO_REGION:
                        df.at[idx, "gis_territory_name"] = bare + " novads"
                        df.at[idx, "estimated_from_address"] = True

        # 3b: Postal code from housing dataset — nearby house on same street
        if "postal_code_clean" in df.columns:
            still_need_postal = df["postal_code_clean"].isna() & df["Town_Parish"].notna()
            if still_need_postal.any():
                import polars as plr

                # Genitive (novads name) → Nominative (housing Town) mapping
                # Latvian novads names use genitive case; housing data uses nominative
                _GENI_TO_NOM: dict[str, str] = {
                    "Ādažu": "Ādaži", "Aizkraukles": "Aizkraukle",
                    "Alūksnes": "Alūksne", "Augšdaugavas": "Augšdaugava",
                    "Balvu": "Balvi", "Bauskas": "Bauska",
                    "Cēsu": "Cēsis", "Dienvidkurzemes": "Dienvidkurzeme",
                    "Dobeles": "Dobele", "Gulbenes": "Gulbene",
                    "Jēkabpils": "Jēkabpils", "Jelgavas": "Jelgava",
                    "Krāslavas": "Krāslava", "Kuldīgas": "Kuldīga",
                    "Ķekavas": "Ķekava", "Limbažu": "Limbaži",
                    "Līvānu": "Līvāni", "Ludzas": "Ludza",
                    "Madonas": "Madona", "Mārupes": "Mārupe",
                    "Ogres": "Ogre", "Olaines": "Olaine",
                    "Preiļu": "Preiļi", "Rēzeknes": "Rēzekne",
                    "Ropažu": "Ropaži", "Salaspils": "Salaspils",
                    "Saldus": "Saldus", "Saulkrastu": "Saulkrasti",
                    "Siguldas": "Sigulda", "Smiltenes": "Smiltene",
                    "Talsu": "Talsi", "Tukuma": "Tukums",
                    "Valkas": "Valka", "Valmieras": "Valmiera",
                    "Varakļānu": "Varakļāni", "Ventspils": "Ventspils",
                    # Pre-2021 municipalities
                    "Aizputes": "Aizpute", "Beverīnas": "Beverīna",
                    "Carnikavas": "Carnikava", "Durbes": "Durbe",
                    "Garkalnes": "Garkalne", "Lielvārdes": "Lielvārde",
                    "Nīcas": "Nīca", "Stopiņu": "Stopiņi",
                }

                # Collect town names needed (both genitive and nominative forms)
                needed_towns = set()
                geni_to_nom_map: dict[str, str] = {}  # bare genitive → housing nominative
                for tp in df.loc[still_need_postal, "Town_Parish"].dropna().unique():
                    bare = re.sub(r"\s+nov\.$", "", tp)
                    needed_towns.add(bare)
                    nom = _GENI_TO_NOM.get(bare, bare)
                    needed_towns.add(nom)
                    geni_to_nom_map[bare] = nom

                # Load housing data
                housing = plr.read_parquet(
                    _housing_path,
                    columns=["Town", "Street", "House", "PostIndex"],
                )

                # Normalize postal codes: "LV3907" → "LV-3907"
                housing = housing.with_columns(
                    plr.col("PostIndex").str.replace(r"^LV(\d)", "LV-$1").alias("PostIndex")
                ).filter(
                    plr.col("PostIndex").is_not_null()
                    & plr.col("Town").is_not_null()
                    & plr.col("Town").is_in(list(needed_towns))
                )

                # Extract numeric house number
                housing = housing.with_columns(
                    plr.col("House")
                    .str.extract(r"^(\d+)", 1)
                    .cast(plr.Int32, strict=False)
                    .alias("_house_num")
                )

                # Build (Town, Street) → [(house_num, PostIndex)] dict
                street_postal_pdf = (
                    housing
                    .filter(
                        plr.col("Street").is_not_null()
                        & plr.col("_house_num").is_not_null()
                    )
                    .select(["Town", "Street", "_house_num", "PostIndex"])
                    .unique(subset=["Town", "Street", "_house_num"])
                    .to_pandas()
                )

                street_dict: dict[tuple[str, str], list[tuple[int, str]]] = {}
                for _, row in street_postal_pdf.iterrows():
                    key = (row["Town"], row["Street"])
                    street_dict.setdefault(key, []).append(
                        (int(row["_house_num"]), row["PostIndex"])
                    )

                # Town → most common PostIndex (fallback)
                town_postal_pdf = (
                    housing
                    .group_by("Town")
                    .agg(plr.col("PostIndex").mode().first().alias("postal"))
                    .to_pandas()
                )
                town_dict: dict[str, str] = {
                    r["Town"]: r["postal"]
                    for _, r in town_postal_pdf.iterrows()
                    if pd.notna(r.get("postal"))
                }

                del housing  # free memory

                # Match EPC rows — nearby house strategy
                for idx in df.index[still_need_postal]:
                    tp = df.at[idx, "Town_Parish"]
                    if pd.isna(tp):
                        continue
                    tp_str = str(tp)
                    town_geni = re.sub(r"\s+nov\.$", "", tp_str)
                    # Try both genitive and nominative forms
                    town_nom = geni_to_nom_map.get(town_geni, town_geni)
                    st = df.at[idx, "Street"] if "Street" in df.columns else None
                    ho = df.at[idx, "House"] if "House" in df.columns else None

                    if pd.notna(st):
                        # Try nominative first (housing data uses nominative)
                        entries = street_dict.get((town_nom, str(st)), [])
                        if not entries:
                            entries = street_dict.get((town_geni, str(st)), [])
                        if entries:
                            tgt_num = None
                            if pd.notna(ho):
                                m_num = re.match(r"^(\d+)", str(ho))
                                if m_num:
                                    tgt_num = int(m_num.group(1))

                            if tgt_num is not None:
                                # Find nearest house number on same street
                                best_postal = min(
                                    entries, key=lambda x: abs(x[0] - tgt_num)
                                )[1]
                            else:
                                # No house number — majority vote on street
                                from collections import Counter as _Ctr
                                votes = _Ctr(p for _, p in entries)
                                best_postal = votes.most_common(1)[0][0]

                            df.at[idx, "postal_code_clean"] = best_postal
                            df.at[idx, "estimated_from_address"] = True
                            continue

                    # Fallback: Town → most common postal code
                    postal = town_dict.get(town_nom) or town_dict.get(town_geni)
                    if postal:
                        df.at[idx, "postal_code_clean"] = postal
                        df.at[idx, "estimated_from_address"] = True

    return df
