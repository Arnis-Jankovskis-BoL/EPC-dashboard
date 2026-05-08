"""
CSP (Central Statistical Bureau of Latvia) data utilities.

Parses and joins two CSP datasets to the EPC building dataframe:
  - MIV020: Median household equivalised income by territory (EUR/month, 2024)
  - IRD062: Population density by territory (persons/km², 2025)

⚠️ Income data is EXPERIMENTAL STATISTICS — small samples, wide CIs.
   Document this caveat in any publication using these features.

Territory hierarchy (post-2021 reform):
  Latvia → 5 Statistical regions → {10 valstspilsētas + 36 novads} → pagasts/towns

Key join logic:
  - EPC row with Valstspilsetas != "Cits" → direct lookup by city name
  - EPC row with Valstspilsetas == "Cits" → Parish ("Ādažu pag.") → full form
    ("ādažu pagasts") → pagasts→novads lookup → novads key
  - Fallback: Town column direct lookup
"""

from __future__ import annotations

import csv
import logging
import re
from pathlib import Path
from typing import Optional

import pandas as pd

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Valstspilsētas — these are matched directly from Income CSV as bare city names.
# Source: post-2021 reform (Cabinet Regulation 785/2021)
# ---------------------------------------------------------------------------
VALSTSPILSETAS = frozenset([
    "Rīga", "Daugavpils", "Jelgava", "Jēkabpils", "Jūrmala",
    "Liepāja", "Ogre", "Rēzekne", "Valmiera", "Ventspils",
])

# Known region for each valstspilsēta.
# Needed because in IRD062 the 10 cities appear as a flat list AFTER all region
# headers, so the parent-following parse logic assigns them all "Latgales" (last
# region header). We override with this authoritative mapping.
# Source: Official Latvia NUTS classification (post-2021 reform).
VALSTSPILSETA_REGIONS: dict[str, str] = {
    "Rīga":       "Rīgas statistiskais reģions",
    "Jūrmala":    "Rīgas statistiskais reģions",
    "Ogre":       "Rīgas statistiskais reģions",
    "Jelgava":    "Zemgales statistiskais reģions",
    "Jēkabpils":  "Zemgales statistiskais reģions",
    "Liepāja":    "Kurzemes statistiskais reģions",
    "Ventspils":  "Kurzemes statistiskais reģions",
    "Valmiera":   "Vidzemes statistiskais reģions",
    "Daugavpils": "Latgales statistiskais reģions",
    "Rēzekne":    "Latgales statistiskais reģions",
}

# Authoritative novads→region mapping.
# IRD062 lists all novads alphabetically (NOT nested under region headers), so
# region cannot be inferred by parse position. Source: NUTS + Latvia ATVK (post-2021).
_R = "Rīgas statistiskais reģions"
_V = "Vidzemes statistiskais reģions"
_K = "Kurzemes statistiskais reģions"
_Z = "Zemgales statistiskais reģions"
_L = "Latgales statistiskais reģions"
NOVADS_TO_REGION: dict[str, str] = {
    "Ādažu":            _R,
    "Aizkraukles":      _Z,
    "Alūksnes":         _V,
    "Augšdaugavas":     _L,
    "Balvu":            _V,
    "Bauskas":          _Z,
    "Cēsu":             _V,
    "Dienvidkurzemes":  _K,
    "Dobeles":          _Z,
    "Gulbenes":         _V,
    "Jēkabpils":        _Z,
    "Jelgavas":         _Z,
    "Krāslavas":        _L,
    "Kuldīgas":         _K,
    "Ķekavas":          _R,
    "Limbažu":          _V,
    "Līvānu":           _L,
    "Ludzas":           _L,
    "Madonas":          _V,
    "Mārupes":          _R,
    "Ogres":            _R,
    "Olaines":          _R,
    "Preiļu":           _L,
    "Rēzeknes":         _L,
    "Ropažu":           _R,
    "Salaspils":        _R,
    "Saldus":           _K,
    "Saulkrastu":       _R,
    "Siguldas":         _R,
    "Smiltenes":        _V,
    "Talsu":            _K,
    "Tukuma":           _K,
    "Valkas":           _V,
    "Valmieras":        _V,
    "Varakļānu":        _L,
    "Ventspils":        _K,
}

# Rows to skip in income CSV — Latvia-wide and statistical regions
_INCOME_SKIP_PATTERNS = [
    "latvija",           # national average
    "statistiskais reģions",  # regional aggregates
]


def _income_skip(name: str) -> bool:
    """Return True if the income row should be excluded."""
    lower = name.lower()
    return any(p in lower for p in _INCOME_SKIP_PATTERNS)


def _income_key(name: str) -> str:
    """Derive lookup key from income territory name.

    Examples:
        "Ādažu novads" → "Ādažu"
        "Rīga"         → "Rīga"
        "Jelgava"      → "Jelgava"
    """
    # Strip " novads" suffix (present on all novads rows)
    return re.sub(r"\s+novads$", "", name.strip(), flags=re.IGNORECASE)


def parse_income_csv(path: Path) -> dict[str, float]:
    """Parse MIV020 income CSV into a territory→income mapping.

    Args:
        path: Path to MIV020_*.csv

    Returns:
        dict mapping territory key (bare name, no " novads") → float EUR/month
        Keys include: valstspilsēta names ("Rīga", "Jēkabpils" …) and
        novads bare names ("Ādažu", "Aizkraukles" …).
    """
    # Format: row 0 = title, row 1 = blank, row 2 = header, rows 3+ = data
    df = pd.read_csv(
        path,
        skiprows=2,
        encoding="utf-8-sig",
        header=0,
    )
    # Columns: "Teritoriālā vienība", "2024"
    df.columns = ["territory", "income"]

    result: dict[str, float] = {}
    for _, row in df.iterrows():
        name = str(row["territory"]).strip().strip('"')
        value = row["income"]
        if _income_skip(name):
            continue
        try:
            income_val = float(str(value).replace(",", "."))
        except (ValueError, TypeError):
            logger.debug("Skipping income row with non-numeric value: %s = %r", name, value)
            continue
        key = _income_key(name)
        result[key] = income_val

    logger.info("Parsed income CSV: %d territories", len(result))
    return result


# ---------------------------------------------------------------------------
# Statistical region names — used as keys in density-derived region map.
# Normalised to drop date annotation "(no 01.01.2024.)"
# ---------------------------------------------------------------------------
_REGION_PATTERN = re.compile(
    r"statistiskais\s+reģions", re.IGNORECASE
)
_DATE_ANNOTATION = re.compile(r"\s*\((?:no|līdz)\s+\d{2}\.\d{2}\.\d{4}\.?\)", re.IGNORECASE)


def _clean_region_name(raw: str) -> str:
    """Normalise region name: strip NUTS code, date annotations, trailing whitespace.

    "LV00A Rīgas statistiskais reģions (no 01.01.2024.)" → "Rīgas statistiskais reģions"
    """
    # Remove NUTS prefix  "LVxxx " or "LV " (e.g. "LV Latvija")
    name = re.sub(r"^LV\w*\s+", "", raw.strip())
    # Remove date annotations
    name = _DATE_ANNOTATION.sub("", name).strip()
    return name


def parse_density_csv(
    path: Path,
) -> tuple[dict[str, float], dict[str, str], dict[str, str]]:
    """Parse IRD062 density CSV into three lookup tables.

    Args:
        path: Path to IRD062_*.csv

    Returns:
        density_map:       territory_key → density (persons/km²)
                           Keys: valstspilsēta names, novads bare names,
                           pagasts full-form lowercase ("aizkraukles pagasts")
        pagasts_to_novads: lowercase pagasts/sub-town key → novads bare name
        novads_to_region:  novads bare name → statistical region name

    Filtering:
        - value == "…" (expired entry) → skipped
        - "(līdz" in name → old boundary, skipped
        - Only current statistical regions (no 01.01.2024.) are used for region map
    """
    density_map: dict[str, float] = {}
    pagasts_to_novads: dict[str, str] = {}

    current_novads: Optional[str] = None  # bare name of current novads

    with open(path, encoding="utf-8-sig") as fh:
        reader = csv.reader(fh)
        # Skip title (row 0) and blank (row 1) and header (row 2)
        for _ in range(3):
            next(reader, None)
        rows = list(reader)

    for row in rows:
        if len(row) < 2:
            continue

        raw_name = row[0].strip()
        raw_value = row[1].strip()

        # Strip expired values
        if raw_value == "…" or "(līdz" in raw_name:
            continue

        # Parse value
        try:
            value = float(raw_value)
        except (ValueError, TypeError):
            continue

        # Strip NUTS prefix from name (e.g. "LV Latvija", "LV00A Rīgas...", "LV0001000 Rīga")
        # \w* (zero or more) handles "LV Latvija" where nothing follows LV before the space
        name_no_nuts = re.sub(r"^LV\w*\s+", "", raw_name)

        # Detect statistical region header — store aggregate density, skip hierarchy tracking
        if "statistiskais reģions" in name_no_nuts.lower():
            current_novads = None
            # Store region-level density too (key = cleaned region name)
            region_key = _clean_region_name(raw_name)
            density_map[region_key] = value
            continue

        # Detect sub-level (indented with "..")
        if name_no_nuts.startswith(".."):
            sub_name = name_no_nuts[2:].strip()  # remove ".."
            # Determine if pagasts or town
            if "pagasts" in sub_name.lower():
                # "Aiviekstes pagasts" → key = lowercase full name
                key = sub_name.lower()
            else:
                # Town within novads (e.g., "Aizkraukle", "Valmiera")
                key = sub_name.lower()
            density_map[key] = value
            if current_novads:
                pagasts_to_novads[key] = current_novads
            continue

        # Top-level territory: Latvia, valstspilsēta, or novads
        if name_no_nuts.lower() == "latvija":
            density_map["latvija"] = value
            current_novads = None
            continue

        if name_no_nuts.endswith(" novads"):
            # Novads row
            bare = re.sub(r"\s+novads$", "", name_no_nuts, flags=re.IGNORECASE).strip()
            # Use setdefault so a same-named valstspilsēta city density is NOT overwritten.
            # "Jēkabpils novads" (density=13) must NOT overwrite "Jēkabpils" city (density=961).
            density_map.setdefault(bare, value)
            current_novads = bare
            # Region is assigned from authoritative NOVADS_TO_REGION after the loop
            continue

        # Valstspilsēta or nested city (e.g., "Rīga", "Valmiera" inside Valmieras novads)
        city_name = name_no_nuts.strip()
        density_map[city_name] = value
        # Special case: Valmiera appears WITHOUT ".." prefix inside Valmieras novads
        # section (CSP anomaly). Keep current_novads intact so subsequent pagasts entries
        # still map correctly.  Top-level cities have current_novads=None — nothing to do.
        # ⚠️ Income double-counting: Jēkabpils, Ogre, Valmiera residents are also counted
        # inside their novads figures (CSP Important_note.txt). City match takes priority.

    # Build authoritative novads→region and valstspilsēta→region mappings.
    # IRD062 is flat (not nested), so position-based region tracking is unreliable.
    # We use hardcoded dictionaries sourced from Latvia NUTS classification (post-2021).
    novads_to_region = {**NOVADS_TO_REGION, **VALSTSPILSETA_REGIONS}

    logger.info(
        "Parsed density CSV: %d density entries, %d pagasts->novads mappings, "
        "%d novads->region mappings",
        len(density_map),
        len(pagasts_to_novads),
        len(novads_to_region),
    )
    return density_map, pagasts_to_novads, novads_to_region


# ---------------------------------------------------------------------------
# Normalisation: EPC Parish → lookup key
# ---------------------------------------------------------------------------

def _normalise_parish(parish: str) -> str:
    """Convert EPC Parish abbreviation to full-form lowercase key.

    "Ādažu pag."  → "ādažu pagasts"
    "Stopiņu pag." → "stopiņu pagasts"

    Uses a single regex to avoid double-substitution: replacing " pag." first and
    then " pag" would match " pag" inside the already-inserted " pagasts" and
    produce garbled output like "ādažu pagastsasts".
    """
    # Match " pag" optionally followed by "." at end of string
    cleaned = re.sub(r"\s+pag\.?\s*$", " pagasts", parish.strip(), flags=re.IGNORECASE)
    return cleaned.lower()


def resolve_territory_key(
    town_parish: str,
    pagasts_to_novads: dict[str, str],
) -> Optional[str]:
    """Resolve the territory lookup key for a single EPC row.

    Uses the unified ``Town_Parish`` column created by the R pipeline, which
    already encodes "whichever administrative level is available":
      - Parish rows:  ``"Ādažu pag."``  → normalise → pagasts_to_novads → novads key
      - Town rows:    ``"Mārupe"``       → used directly (novads sub-town or city)
      - City rows:    ``"Jūrmala"``      → used directly (valstspilsēta)

    Args:
        town_parish:       EPC ``Town_Parish`` value
        pagasts_to_novads: lookup from :func:`parse_density_csv`

    Returns:
        Territory key string, or None if not resolvable.
    """
    tp = str(town_parish).strip()
    if not tp or tp == "nan":
        return None

    # Pagasts: contains "pag" abbreviation → resolve to novads
    if "pag" in tp.lower():
        norm = _normalise_parish(tp)
        if norm in pagasts_to_novads:
            return pagasts_to_novads[norm]
        # Pagasts not found in lookup (e.g. pre-2021 territory) → fall through
        return None

    # Non-pagasts town (e.g. "Mārupe", "Ādaži", "Sigulda").
    # These are sub-items in IRD062 stored as lowercase keys in pagasts_to_novads.
    # Resolving them to their parent novads gives consistent novads-level keys
    # for both income and density lookup.
    tp_lower = tp.lower()
    if tp_lower in pagasts_to_novads:
        return pagasts_to_novads[tp_lower]

    # City or bare novads name (e.g. "Rīga", "Jūrmala") — use directly
    return tp


def join_csp_features(
    df: pd.DataFrame,
    income_map: dict[str, float],
    density_map: dict[str, float],
    pagasts_to_novads: dict[str, str],
    novads_to_region: dict[str, str],
) -> pd.DataFrame:
    """Add CSP socioeconomic features to the EPC dataframe.

    New columns added:
        municipality_income_median  : float   — median household income EUR/month (MIV020)
        municipality_pop_density    : float   — population density persons/km² (IRD062)
        statistical_region          : str     — one of 5 Latvian statistical regions

    Args:
        df:                 EPC dataframe with columns Valstspilsetas, Town, Parish
        income_map:         from parse_income_csv()
        density_map:        from parse_density_csv() [0]
        pagasts_to_novads:  from parse_density_csv() [1]
        novads_to_region:   from parse_density_csv() [2]

    Returns:
        df with three new columns appended (left-join semantics — preserves all rows).
    """
    df = df.copy()
    n_rows = len(df)

    if "Town_Parish" not in df.columns:
        raise KeyError(
            "Expected 'Town_Parish' column (created by R pipeline). "
            "Available columns: " + ", ".join(df.columns.tolist())
        )

    # Resolve territory key using the unified Town_Parish column.
    # Town_Parish encodes whichever administrative level is present for each row:
    #   pagasts rows  → "Ādažu pag."  → pagasts_to_novads → novads bare name
    #   town rows     → "Mārupe"       → used directly
    #   city rows     → "Jūrmala"      → used directly
    keys = df["Town_Parish"].apply(
        lambda tp: resolve_territory_key(tp, pagasts_to_novads)
    )

    df["municipality_income_median"] = keys.map(income_map)
    df["municipality_pop_density"] = keys.map(density_map)
    df["statistical_region"] = keys.map(novads_to_region)

    # Log match rates
    n_income = df["municipality_income_median"].notna().sum()
    n_density = df["municipality_pop_density"].notna().sum()
    n_region = df["statistical_region"].notna().sum()
    logger.info(
        "CSP join: rows=%d | income matched=%d (%.1f%%) | density matched=%d (%.1f%%) "
        "| region matched=%d (%.1f%%)",
        n_rows,
        n_income, 100 * n_income / n_rows,
        n_density, 100 * n_density / n_rows,
        n_region, 100 * n_region / n_rows,
    )

    # Log unresolved keys for diagnostic purposes
    unmatched_income = (
        keys[df["municipality_income_median"].isna()]
        .dropna()
        .value_counts()
        .head(20)
    )
    if not unmatched_income.empty:
        logger.warning(
            "Top unmatched income keys (no CSP entry found):\n%s",
            unmatched_income.to_string(),
        )

    assert len(df) == n_rows, "Row count changed during CSP join — left join violated"
    return df
