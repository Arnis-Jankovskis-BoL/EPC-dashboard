"""Building Explorer page — AG Grid table with column selector, search, and filter chain."""

from __future__ import annotations

import json

import pandas as pd
import plotly.graph_objects as go
from dash import ALL, Input, Output, State, callback, clientside_callback, ctx, dcc, html, no_update
import dash_ag_grid as dag
import dash_bootstrap_components as dbc


from dashboard.data_loader import (
    DEFAULT_VISIBLE,
    EPC_TABLE_COLUMNS,
)
from dashboard.column_meta import get_display_name, get_filter_type, get_tooltip
from dashboard.theme import BOL_PALETTE, CARD_STYLE, EPC_PALETTE, EPC_CLASSES
from dashboard.i18n import t

# Provenance bitmask → column mapping for teal font on estimated values.
# Currently empty — all 381k dashboard values come from official sources.
# Will be populated when KNN/parsed estimates are added to the pipeline.
COLUMN_PROVENANCE_BITS: dict[str, int] = {
    "construction_year": 128,  # PROV_YEAR_ESTIMATED — estimated from acceptance year
}

_PLOT_STYLE_VISIBLE = {"flex": "0 1 340px", "minWidth": "260px", "maxWidth": "380px"}
_PLOT_STYLE_HIDDEN = {"display": "none"}

# Reorder EPC: best (A) first → worst (F) last
EPC_CLASSES_DISPLAY = ["A", "B", "C", "D", "E", "F"]

# Ordered construction eras (matches Latvian regulation periods)
ERA_BINS = [
    "Pre-1945", "1946-1960", "1961-1990", "1991-2002",
    "2003-2014", "2015-2020", "2021+",
]

# Wall materials with themed colors
WALL_MATERIALS = [
    "Wood", "Brick and stone", "Concrete",
    "Lightweight concrete", "Metal and glass", "Other",
]
WALL_COLORS: dict[str, str] = {
    "Lightweight concrete": "#A0A0A0",  # grey
    "Brick and stone": "#C0392B",       # brick red
    "Wood": "#8B6914",                  # brown/wood
    "Concrete": "#707070",              # dark grey
    "Metal and glass": "#5DADE2",       # steel blue
    "Other": "#95A5A6",                 # light grey
    "N/A": "#999",
}

# Floor count groups (BuildingGroundFloors → display group)
FLOOR_GROUPS = ["1", "2", "3", "4", "5", "6", "7", "8", "9", "10+"]

# Building type groups
BUILDING_TYPES = ["Residential_Individual", "Residential_Apartment"]
BUILDING_TYPE_DISPLAY: dict[str, dict[str, str]] = {
    "Residential_Individual": {"lv": "Individuālā", "en": "Individual"},
    "Residential_Apartment": {"lv": "Daudzdzīvokļu", "en": "Apartment"},
}
BUILDING_TYPE_COLORS: dict[str, str] = {
    "Residential_Individual": BOL_PALETTE["accent1"],
    "Residential_Apartment": BOL_PALETTE["accent1"],
    "N/A": "#999",
}


def _floor_group(val: int | None) -> str:
    """Map a raw BuildingGroundFloors integer to a display group."""
    if val is None or pd.isna(val):
        return "N/A"
    val = int(val)
    if val <= 0:
        return "N/A"
    if val <= 9:
        return str(val)
    return "10+"

# Column picker blocks — ordered list of (block_label, [col_names])
# Only columns that actually exist in the data will be shown.
COLUMN_BLOCKS: list[tuple[str, list[str]]] = [
    ("Identification", [
        "KadastraApzimBuilding", "DokNr", "cert_date", "cert_year",
        "source", "address_mismatch", "estimated_from_address",
    ]),
    ("Location", [
        "Town_Parish", "Parish", "Street", "House", "postal_code_clean", "Adrese",
        "Valstspilsetas",
        "statistical_region", "gis_territory_name", "apkaime_name",
    ]),
    ("Energy", [
        "combined_epc_class", "combined_heating_kwh",
        "EnergoefektivKlase", "EnergijaApkurei",
        "EnergoefektivKlase_georiga_pref", "EnergijaApkurei_georiga_pref",
        "PrimaraNeatjaunojamaEnergija", "estimated_primary_energy",
        "eu_taxonomy_top15",
        "primary_energy_pctile", "primary_energy_pctile_type",
        "predicted_epc_class", "predicted_heating_kwh",
    ]),
    ("Physical", [
        "building_type", "ekas_veids_grouped", "construction_year", "era_bin",
        "BuildingExploitYear", "BuildingArea", "ReferencesPlatiba",
        "BuildingGroundFloors", "BuildingDeprecation", "wall_material_grouped", "area_band",
        "apartment_count", "building_volume_m3", "underground_floors",
        "footprint_area_m2", "wwr_archetype", "estimated_wall_U",
        "estimated_window_U", "estimated_roof_U",
        "volume_per_apartment", "area_per_apartment",
    ]),
    ("Heating & Renovation", [
        "heating_type_grouped", "district_heating_flag",
        "is_renovated_before_epc", "renovation_count", "renovation_detected",
        "years_since_renovation", "partial_renovation_flag",
    ]),
]


# Columns only meaningfully populated in "Full residential" mode
_FULL_ONLY_COLS = {"predicted_epc_class", "predicted_heating_kwh"}


def _build_column_picker(available_cols: set[str], picker_type: str = "display", lang: str = "en", selected: set[str] | None = None) -> html.Div:
    """Build a grouped column picker with labelled blocks.
    
    picker_type: "load" for data loading panel, "display" for table visibility panel.
    selected: if provided, use these as checked values instead of DEFAULT_VISIBLE.
    """
    use_selected = selected if selected is not None else set(DEFAULT_VISIBLE)
    blocks = []
    for label, cols in COLUMN_BLOCKS:
        valid_cols = [c for c in cols if c in available_cols]
        if not valid_cols:
            continue
        display_label = BLOCK_LABELS.get(label, {}).get(lang, label)
        blocks.append(html.Div([
            html.Div(display_label, style={
                "fontWeight": "600", "fontSize": "0.78rem",
                "color": BOL_PALETTE["navy"], "marginBottom": "2px",
                "borderBottom": f"1px solid {BOL_PALETTE['grey']}",
                "paddingBottom": "2px",
            }),
            dbc.Checklist(
                id={"type": f"col-{picker_type}", "block": label},
                options=[
                    {
                        "label": html.Span(
                            get_display_name(c, lang),
                            title=get_tooltip(c, lang),
                            style={"cursor": "help",
                                   "color": "#1565C0", "fontWeight": "600"}
                            if c in _FULL_ONLY_COLS else {"cursor": "help"},
                        ),
                        "value": c,
                    }
                    for c in valid_cols
                ],
                value=[c for c in valid_cols if c in use_selected],
                inline=True,
                style={"fontSize": "0.82rem"},
            ),
        ], style={"marginBottom": "8px"}))
    return html.Div(blocks)


# ---------------------------------------------------------------------------
# AG Grid filter-model interpreter (replicates client-side filtering in Python
# for the filter-chain display)
# ---------------------------------------------------------------------------

def _get_filter_mask(df: pd.DataFrame, col: str, filt: dict) -> pd.Series:
    """Compute a boolean mask for a single AG Grid filter condition."""
    ftype = filt.get("type", "contains")
    filter_kind = filt.get("filterType", "text")

    if filter_kind == "text":
        val = str(filt.get("filter", "")).lower()
        s = df[col].astype(str).str.lower()
        if ftype == "contains":
            return s.str.contains(val, na=False, regex=False)
        if ftype == "notContains":
            return ~s.str.contains(val, na=False, regex=False)
        if ftype == "equals":
            return s == val
        if ftype == "notEqual":
            return s != val
        if ftype == "startsWith":
            return s.str.startswith(val, na=False)
        if ftype == "endsWith":
            return s.str.endswith(val, na=False)
        if ftype == "blank":
            return df[col].isna() | (df[col].astype(str).str.strip() == "")
        if ftype == "notBlank":
            return df[col].notna() & (df[col].astype(str).str.strip() != "")

    elif filter_kind == "number":
        val = filt.get("filter")
        s = pd.to_numeric(df[col], errors="coerce")
        if ftype == "equals":
            return s == val
        if ftype == "notEqual":
            return s != val
        if ftype == "greaterThan":
            return s > val
        if ftype == "greaterThanOrEqual":
            return s >= val
        if ftype == "lessThan":
            return s < val
        if ftype == "lessThanOrEqual":
            return s <= val
        if ftype == "inRange":
            return (s >= val) & (s <= filt.get("filterTo", val))
        if ftype == "blank":
            return s.isna()
        if ftype == "notBlank":
            return s.notna()

    # Unknown filter type — keep all rows
    return pd.Series(True, index=df.index)


def _apply_column_filter(df: pd.DataFrame, col: str, filt: dict) -> pd.DataFrame:
    """Apply a single column's AG Grid filter (may be compound AND/OR)."""
    if col not in df.columns:
        return df
    if "operator" in filt:
        m1 = _get_filter_mask(df, col, filt["condition1"])
        m2 = _get_filter_mask(df, col, filt["condition2"])
        mask = (m1 & m2) if filt["operator"] == "AND" else (m1 | m2)
        return df[mask]
    return df[_get_filter_mask(df, col, filt)]


def _describe_condition(filt: dict) -> str:
    """Human-readable label for one filter condition."""
    ftype = filt.get("type", "contains")
    val = filt.get("filter", "")
    labels = {
        "contains": f'contains "{val}"',
        "notContains": f'excludes "{val}"',
        "equals": f'= "{val}"',
        "notEqual": f'\u2260 "{val}"',
        "startsWith": f'starts with "{val}"',
        "endsWith": f'ends with "{val}"',
        "greaterThan": f"> {val}",
        "greaterThanOrEqual": f"\u2265 {val}",
        "lessThan": f"< {val}",
        "lessThanOrEqual": f"\u2264 {val}",
        "inRange": f"in [{val}, {filt.get('filterTo', '')}]",
        "blank": "is blank",
        "notBlank": "is not blank",
    }
    return labels.get(ftype, str(ftype))


def _describe_filter(col: str, filt: dict) -> str:
    """Human-readable label for a column filter (may be compound)."""
    nice = col.replace("_", " ").title()
    if "operator" in filt:
        d1 = _describe_condition(filt["condition1"])
        d2 = _describe_condition(filt["condition2"])
        return f"{nice} ({d1} {filt['operator']} {d2})"
    return f"{nice} {_describe_condition(filt)}"


# ---------------------------------------------------------------------------
# Column defs helper
# ---------------------------------------------------------------------------

def _make_column_defs(
    visible: list[str], all_cols: list[str], dtypes: dict[str, str] | None = None,
    lang: str = "en",
) -> list[dict]:
    """Generate AG Grid columnDefs with hide toggling, display names, tooltips, and filter types.

    Visible columns appear first (in DEFAULT_VISIBLE order), then hidden columns.
    """
    dtypes = dtypes or {}
    # Columns to keep left-aligned (long text / addresses / IDs)
    _LEFT_ALIGN: set[str] = set()  # All columns centered per user request
    # Order: visible first (preserving EPC_TABLE_COLUMNS canonical order), then hidden
    vis_set = set(visible)
    ordered = [c for c in EPC_TABLE_COLUMNS if c in vis_set and c in all_cols]
    ordered += [c for c in EPC_TABLE_COLUMNS if c not in vis_set and c in all_cols]
    defs = []
    for col in ordered:
        cd: dict = {
            "field": col,
            "headerName": get_display_name(col, lang),
            "headerTooltip": get_tooltip(col, lang),
            "sortable": True,
            "filter": get_filter_type(col, dtypes.get(col, "")),
            "resizable": True,
            "hide": col not in visible,
        }
        # Center non-text columns
        if col not in _LEFT_ALIGN:
            base_style = {"textAlign": "center"}
        else:
            base_style = {}
        # Add provenance-based teal font for estimated/derived values
        prov_bits = COLUMN_PROVENANCE_BITS.get(col)
        if prov_bits:
            cd["cellStyle"] = {
                "styleConditions": [
                    {
                        "condition": f"params.data && (params.data._provenance & {prov_bits}) > 0",
                        "style": {**base_style, "color": "#489E9E"},
                    },
                ],
                "defaultStyle": base_style,
            }
        else:
            cd["cellStyle"] = base_style
        if col not in _LEFT_ALIGN:
            cd["headerClass"] = "ag-header-cell-center"
        # EPC class → small colored badge via JS renderer
        if col in ("EnergoefektivKlase", "EnergoefektivKlase_georiga_pref",
                   "epc_class_cert", "epc_class_georiga",
                   "combined_epc_class", "predicted_epc_class"):
            cd["cellRenderer"] = "EpcBadge"
            cd["cellStyle"] = {"textAlign": "center"}
        # Boolean columns → checkbox renderer
        if dtypes.get(col, "") in ("bool", "boolean", "object") and col in _BOOL_COLS:
            cd["cellRenderer"] = "BoolCheck"
        defs.append(cd)
    return defs

_BOOL_COLS = {"address_mismatch", "estimated_from_address", "district_heating_flag",
              "is_renovated_before_epc", "renovation_detected", "partial_renovation_flag",
              "eu_taxonomy_top15"}

# Wall material display translations (data values are always English)
WALL_MATERIAL_DISPLAY: dict[str, dict[str, str]] = {
    "Wood": {"en": "Wood", "lv": "Koks"},
    "Brick and stone": {"en": "Brick and stone", "lv": "Ķieģeļi un akmens"},
    "Concrete": {"en": "Concrete", "lv": "Betons"},
    "Lightweight concrete": {"en": "Lightweight concrete", "lv": "Vieglais betons"},
    "Metal and glass": {"en": "Metal and glass", "lv": "Metāls un stikls"},
    "Other": {"en": "Other", "lv": "Cits"},
    "N/A": {"en": "N/A", "lv": "N/A"},
}

# Block label translations for column picker
BLOCK_LABELS: dict[str, dict[str, str]] = {
    "Identification": {"en": "Identification", "lv": "Identifikācija"},
    "Location": {"en": "Location", "lv": "Atrašanās vieta"},
    "Energy": {"en": "Energy", "lv": "Enerģija"},
    "Physical": {"en": "Physical", "lv": "Fiziskās īpašības"},
    "Heating & Renovation": {"en": "Heating & Renovation", "lv": "Apkure un atjaunošana"},
}


# ---------------------------------------------------------------------------
# Slicer builders
# ---------------------------------------------------------------------------

def _build_epc_slicer() -> html.Div:
    return html.Div([
        html.Span("EPC klase: ", id="epc-slicer-label", style={"fontSize": "0.85rem", "color": BOL_PALETTE["grey"], "marginRight": "6px"}),
        *[html.Button(cls, id={"type": "epc-slicer", "index": cls}, n_clicks=0, style={
            "backgroundColor": EPC_PALETTE[cls], "color": "#FFF" if cls in ("F", "E", "A") else BOL_PALETTE["navy"],
            "border": "2px solid transparent", "borderRadius": "16px", "padding": "4px 14px",
            "marginRight": "4px", "fontWeight": "600", "fontSize": "0.85rem", "cursor": "pointer",
        }) for cls in EPC_CLASSES_DISPLAY],
        html.Button("N/A", id={"type": "epc-slicer", "index": "N/A"}, n_clicks=0, style={
            "backgroundColor": "#BDBDBD", "color": "#FFF", "border": "2px solid transparent",
            "borderRadius": "16px", "padding": "4px 12px", "marginRight": "4px", "fontWeight": "500",
            "fontSize": "0.85rem", "cursor": "pointer",
        }),
        html.Button("Visi", id="epc-slicer-all", n_clicks=0, style={
            "backgroundColor": BOL_PALETTE["navy"], "color": "#FFF", "border": "2px solid transparent",
            "borderRadius": "16px", "padding": "4px 14px", "marginLeft": "8px", "fontWeight": "600",
            "fontSize": "0.85rem", "cursor": "pointer",
        }),
    ], style={"marginBottom": "0.5rem", "display": "flex", "alignItems": "center"})


def _build_era_slicer() -> html.Div:
    return html.Div([
        html.Span("Periods: ", id="era-slicer-label", style={"fontSize": "0.85rem", "color": BOL_PALETTE["grey"], "marginRight": "6px"}),
        *[html.Button(era, id={"type": "era-slicer", "index": era}, n_clicks=0, style={
            "backgroundColor": BOL_PALETTE["accent1"], "color": "#FFF", "border": "2px solid transparent",
            "borderRadius": "16px", "padding": "4px 12px", "marginRight": "4px", "fontWeight": "500",
            "fontSize": "0.8rem", "cursor": "pointer",
        }) for era in ERA_BINS],
        html.Button("N/A", id={"type": "era-slicer", "index": "N/A"}, n_clicks=0, style={
            "backgroundColor": "#BDBDBD", "color": "#FFF", "border": "2px solid transparent",
            "borderRadius": "16px", "padding": "4px 12px", "marginRight": "4px", "fontWeight": "500",
            "fontSize": "0.8rem", "cursor": "pointer",
        }),
        html.Button("Visi", id="era-slicer-all", n_clicks=0, style={
            "backgroundColor": BOL_PALETTE["navy"], "color": "#FFF", "border": "2px solid transparent",
            "borderRadius": "16px", "padding": "4px 14px", "marginLeft": "8px", "fontWeight": "600",
            "fontSize": "0.8rem", "cursor": "pointer",
        }),
    ], style={"marginBottom": "0.5rem", "display": "flex", "alignItems": "center", "flexWrap": "wrap"})


def _build_floor_slicer() -> html.Div:
    return html.Div([
        html.Span("Stāvi: ", id="floor-slicer-label", style={"fontSize": "0.85rem", "color": BOL_PALETTE["grey"], "marginRight": "6px"}),
        *[html.Button(fg, id={"type": "floor-slicer", "index": fg}, n_clicks=0, style={
            "backgroundColor": BOL_PALETTE["accent1"], "color": "#FFF", "border": "2px solid transparent",
            "borderRadius": "16px", "padding": "4px 12px", "marginRight": "4px", "fontWeight": "500",
            "fontSize": "0.8rem", "cursor": "pointer",
        }) for fg in FLOOR_GROUPS],
        html.Button("N/A", id={"type": "floor-slicer", "index": "N/A"}, n_clicks=0, style={
            "backgroundColor": "#BDBDBD", "color": "#FFF", "border": "2px solid transparent",
            "borderRadius": "16px", "padding": "4px 12px", "marginRight": "4px", "fontWeight": "500",
            "fontSize": "0.8rem", "cursor": "pointer",
        }),
        html.Button("Visi", id="floor-slicer-all", n_clicks=0, style={
            "backgroundColor": BOL_PALETTE["navy"], "color": "#FFF", "border": "2px solid transparent",
            "borderRadius": "16px", "padding": "4px 14px", "marginLeft": "8px", "fontWeight": "600",
            "fontSize": "0.8rem", "cursor": "pointer",
        }),
    ], style={"marginBottom": "0.5rem", "display": "flex", "alignItems": "center", "flexWrap": "wrap"})


def _build_wall_slicer() -> html.Div:
    return html.Div([
        html.Span("Sienas: ", id="wall-slicer-label", style={"fontSize": "0.85rem", "color": BOL_PALETTE["grey"], "marginRight": "6px"}),
        *[html.Button(WALL_MATERIAL_DISPLAY[mat]["lv"], id={"type": "wall-slicer", "index": mat}, n_clicks=0, style={
            "backgroundColor": WALL_COLORS[mat], "color": "#FFF", "border": "2px solid transparent",
            "borderRadius": "16px", "padding": "4px 12px", "marginRight": "4px", "fontWeight": "500",
            "fontSize": "0.8rem", "cursor": "pointer",
        }) for mat in WALL_MATERIALS],
        html.Button("N/A", id={"type": "wall-slicer", "index": "N/A"}, n_clicks=0, style={
            "backgroundColor": "#BDBDBD", "color": "#FFF", "border": "2px solid transparent",
            "borderRadius": "16px", "padding": "4px 12px", "marginRight": "4px", "fontWeight": "500",
            "fontSize": "0.8rem", "cursor": "pointer",
        }),
        html.Button("Visi", id="wall-slicer-all", n_clicks=0, style={
            "backgroundColor": BOL_PALETTE["navy"], "color": "#FFF", "border": "2px solid transparent",
            "borderRadius": "16px", "padding": "4px 14px", "marginLeft": "8px", "fontWeight": "600",
            "fontSize": "0.8rem", "cursor": "pointer",
        }),
    ], style={"marginBottom": "0.5rem", "display": "flex", "alignItems": "center", "flexWrap": "wrap"})




def _build_type_slicer() -> html.Div:
    return html.Div([
        html.Span("Ēkas tips: ", id="type-slicer-label", style={"fontSize": "0.85rem", "color": BOL_PALETTE["grey"], "marginRight": "6px"}),
        *[html.Button(BUILDING_TYPE_DISPLAY[bt]["lv"], id={"type": "type-slicer", "index": bt}, n_clicks=0, style={
            "backgroundColor": BOL_PALETTE["accent1"], "color": "#FFF", "border": "2px solid transparent",
            "borderRadius": "16px", "padding": "4px 12px", "marginRight": "4px", "fontWeight": "500",
            "fontSize": "0.8rem", "cursor": "pointer",
        }) for bt in BUILDING_TYPES],
        html.Button("Visi", id="type-slicer-all", n_clicks=0, style={
            "backgroundColor": BOL_PALETTE["navy"], "color": "#FFF", "border": "2px solid transparent",
            "borderRadius": "16px", "padding": "4px 14px", "marginLeft": "8px", "fontWeight": "600",
            "fontSize": "0.8rem", "cursor": "pointer",
        }),
    ], style={"marginBottom": "0.5rem", "display": "flex", "alignItems": "center", "flexWrap": "wrap"})

# ---------------------------------------------------------------------------
# Layout
# ---------------------------------------------------------------------------

def layout() -> html.Div:
    """Return the Building Explorer page layout."""
    # Get column types from DuckDB schema (no parquet dependency)
    try:
        con = _get_duckdb_con()
        schema = con.execute(
            "SELECT column_name, data_type FROM information_schema.columns WHERE table_name='buildings'"
        ).fetchall()
        dtypes = {name: dtype for name, dtype in schema}
    except Exception:
        dtypes = {}
    # Show ALL defined columns (DuckDB has the full set)
    all_cols = list(EPC_TABLE_COLUMNS)

    column_defs = _make_column_defs(DEFAULT_VISIBLE, all_cols, dtypes, lang="lv")

    return html.Div([
        html.H2(
            "Ēku pārlūks",
            id="explorer-heading",
            style={"color": BOL_PALETTE["navy"], "marginBottom": "1rem"},
        ),

        # Hidden stores for search state
        dcc.Store(id="search-terms-store", data=[]),

        # Controls row
        dbc.Row([
            # Chip-based search input
            dbc.Col(
                html.Div([
                    # Chips + input wrapper (looks like one input)
                    html.Div(
                        [
                            html.Div(id="search-chips", style={
                                "display": "inline",
                            }),
                            dbc.Input(
                                id="search-input",
                                placeholder="Ievadiet un nospiediet Enter...",
                                type="text",
                                debounce=True,
                                style={
                                    "border": "none",
                                    "outline": "none",
                                    "boxShadow": "none",
                                    "display": "inline-block",
                                    "width": "auto",
                                    "minWidth": "200px",
                                    "flex": "1",
                                    "padding": "0.25rem 0.5rem",
                                },
                            ),
                        ],
                        id="search-box-container",
                        style={
                            "display": "flex",
                            "flexWrap": "wrap",
                            "alignItems": "center",
                            "gap": "4px",
                            "border": "1px solid #ced4da",
                            "borderRadius": "6px",
                            "padding": "4px 6px",
                            "backgroundColor": "#FFFFFF",
                            "minHeight": "38px",
                        },
                    ),
                    dbc.Tooltip(
                        "Ievadiet meklēšanas vārdu un nospiediet Enter, lai pievienotu filtru. "
                        "Pievienojiet vairākus vārdus — izmantojiet Jebkurš/Visi pārslēgu.",
                        id="search-tooltip",
                        target="search-box-container",
                        placement="top",
                    ),
                    # AND/OR toggle
                    html.Div(
                        [
                            html.Span("Atbilstība: ", id="search-match-label", style={"fontSize": "0.8rem", "color": BOL_PALETTE["grey"], "marginRight": "4px"}),
                            dbc.Switch(
                                id="search-mode-switch",
                                label="",
                                value=False,
                                style={"display": "inline-block", "margin": "0 4px"},
                            ),
                            html.Span(id="search-mode-label", children="Jebkurš",
                                      style={"fontSize": "0.8rem", "fontWeight": "600", "color": BOL_PALETTE["navy"]}),
                            dbc.Tooltip(
                                "Jebkurš: rāda ēkas, kas atbilst vismaz vienam vārdam. "
                                "Visi: rāda tikai ēkas, kas atbilst visiem vārdiem.",
                                id="search-mode-tooltip",
                                target="search-mode-switch",
                                placement="right",
                            ),
                        ],
                        style={"marginTop": "4px", "display": "flex", "alignItems": "center"},
                    ),
                    # Hidden store to bridge switch → existing callback
                    dcc.Store(id="search-mode", data="any"),
                ], style={"minWidth": "500px", "maxWidth": "600px"}),
                width="auto",
            ),
            # Row count badge — right of search bar
            dbc.Col(
                html.Span(
                    id="explorer-row-count",
                    children="Loading...",
                    style={
                        "backgroundColor": BOL_PALETTE["teal"],
                        "color": "#FFFFFF",
                        "padding": "0.3rem 0.8rem",
                        "borderRadius": "12px",
                        "fontSize": "0.9rem",
                        "fontWeight": "600",
                        "whiteSpace": "nowrap",
                    },
                ),
                width="auto",
                style={"paddingTop": "9px", "marginLeft": "3px"},
            ),
        ], className="mb-2"),

        # Stores for slicer state
        dcc.Store(id="epc-slicer-store", data=list(EPC_CLASSES_DISPLAY) + ["N/A"]),
        dcc.Store(id="era-slicer-store", data=list(ERA_BINS) + ["N/A"]),
        dcc.Store(id="floor-slicer-store", data=list(FLOOR_GROUPS) + ["N/A"]),
        dcc.Store(id="wall-slicer-store", data=list(WALL_MATERIALS) + ["N/A"]),
        dcc.Store(id="type-slicer-store", data=list(BUILDING_TYPES)),

        # Button row: Columns | Custom Filters | Filtering Breakdown | Plots
        html.Div(id="panel-loading-msg",
                 children="Ielādē papildu funkcijas...",
                 style={"fontSize": "0.82rem", "color": BOL_PALETTE["grey"],
                        "fontStyle": "italic", "marginBottom": "6px"}),
        dcc.Interval(id="panel-enable-timer", interval=5_000, n_intervals=0, max_intervals=1),
        dbc.Row([
            dbc.Col(dbc.Button(
                "Kolonnas \u25bc", id="col-selector-toggle",
                color="secondary", size="sm", className="me-2", disabled=True,
            ), width="auto"),
            dbc.Col(dbc.Button(
                "Pielāgoti filtri \u25bc", id="custom-filter-toggle",
                color="secondary", size="sm", className="me-2", disabled=True,
            ), width="auto"),
            dbc.Col(dbc.Button(
                "Filtrēšanas sadalījums \u25bc", id="filter-breakdown-toggle",
                color="secondary", size="sm", className="me-2", disabled=True,
            ), width="auto"),
            dbc.Col(dbc.Button(
                "Grafiki ▼", id="plots-toggle",
                color="secondary", size="sm", className="me-2", disabled=True,
            ), width="auto"),
            dbc.Col(dbc.Button(
                "Kartes ▼", id="maps-toggle",
                color="secondary", size="sm", className="me-2", disabled=True,
            ), width="auto"),
            dbc.Col(dbc.Button(
                "Pielāgota izlase ▼", id="custom-sample-toggle",
                color="secondary", size="sm", disabled=True,
            ), width="auto"),
        ], className="mb-2"),

        # Filtering Breakdown collapse
        dbc.Collapse(
            html.Div(
                id="filter-chain",
                style={
                    "fontSize": "0.85rem",
                    "color": BOL_PALETTE["grey"],
                    "marginBottom": "0.5rem",
                    "minHeight": "1.2rem",
                },
            ),
            id="filter-breakdown-collapse",
            is_open=False,
        ),

        # Custom Filters collapse (includes map on the right)
        dbc.Collapse(
            dbc.Row([
                dbc.Col([
                    html.Div([
                        html.Span("Atlases režīms: ", id="slicer-mode-label-text", style={"fontSize": "0.8rem", "color": BOL_PALETTE["grey"]}),
                        dbc.Switch(
                            id="slicer-mode-switch",
                            label="",
                            value=False,
                            style={"display": "inline-block", "margin": "0 4px"},
                        ),
                        html.Span(id="slicer-mode-label", children="Vairāku atlase",
                                  style={"fontSize": "0.8rem", "color": BOL_PALETTE["navy"], "fontWeight": "600"}),
                        dbc.Tooltip(
                            "Vairāku atlase: ieslēdziet/izslēdziet atsevišķus filtrus. "
                            "Viena atlase: noklikšķinot filtru, pārējie tiek atcelti.",
                            id="slicer-mode-tooltip",
                            target="slicer-mode-switch",
                            placement="right",
                        ),
                    ], style={"marginBottom": "6px", "display": "flex", "alignItems": "center"}),
                    _build_epc_slicer(),
                    _build_era_slicer(),
                    _build_floor_slicer(),
                    _build_wall_slicer(),
                _build_type_slicer(),
                ], width="auto", style={"padding": "8px 0"}),
                dbc.Col([
                    # Map mode switcher row (kebab menu above map, right-aligned)
                    html.Div([
                        html.Span(
                            dbc.DropdownMenu(
                                label="⋮",
                                children=[
                                    dbc.DropdownMenuItem("Karte", header=True),
                                    dbc.DropdownMenuItem("Latvija", id="map-mode-latvia", active=True),
                                    dbc.DropdownMenuItem("Rīga", id="map-mode-riga"),
                                    dbc.DropdownMenuItem("Daugavpils", id="map-mode-daugavpils"),
                                    dbc.DropdownMenuItem(divider=True),
                                    dbc.DropdownMenuItem("Izmērs", header=True),
                                    dbc.DropdownMenuItem("Normāls", id="map-size-normal", active=True),
                                    dbc.DropdownMenuItem("Liels", id="map-size-large"),
                                ],
                                id="map-mode-menu",
                                size="sm",
                                toggle_style={
                                    "backgroundColor": "transparent",
                                    "color": BOL_PALETTE["teal"],
                                    "border": f"1px solid {BOL_PALETTE['teal']}",
                                    "borderRadius": "6px",
                                    "width": "28px", "height": "28px",
                                    "padding": "0", "fontSize": "1.1rem",
                                    "fontWeight": "bold",
                                    "display": "flex", "alignItems": "center",
                                    "justifyContent": "center",
                                    "lineHeight": "1",
                                },
                                toggle_class_name="no-caret",
                                align_end=True,
                            ),
                            title="Mainīt kartes skatu",
                        ),
                    ], style={"textAlign": "right", "marginBottom": "2px"}),
                    dcc.Graph(id="map-choropleth", config={"displayModeBar": False},
                              className="mb-0",
                              style={"marginTop": "0", "marginBottom": "0", "paddingBottom": "0",
                                     "width": "480px"}),
                    dcc.Store(id="map-selected-territory", data=None),
                    dcc.Store(id="map-mode-store", data="latvia"),
                    dcc.Store(id="map-size-store", data="normal"),
                    html.Div([
                        dbc.Button("Nav reģiona (N/A)", id="map-na-btn", size="sm",
                                   className="mt-1 me-2",
                                   style={"backgroundColor": "transparent",
                                          "color": BOL_PALETTE["teal"],
                                          "border": f"1px solid {BOL_PALETTE['teal']}",
                                          "fontSize": "0.82rem", "borderRadius": "12px",
                                          "padding": "0.25rem 0.6rem"},
                                   title="Rādīt ēkas bez reģiona informācijas"),
                        dbc.Button("Notīrīt kartes atlasi", id="map-clear-btn", size="sm",
                                   color="secondary", className="mt-1"),
                    ], style={"textAlign": "right"}),
                ], width="auto", style={"paddingLeft": "15px"}),
            ]),
            id="custom-filter-collapse",
            is_open=False,
            className="mb-1",
        ),
        dcc.Store(id="slicer-mode-store", data="multi"),

        # Plots collapse
        dbc.Collapse(
            html.Div([
                dbc.Checklist(
                    id="plot-checklist",
                    options=[
                        {"label": "EPC klašu sadalījums", "value": "epc_dist"},
                        {"label": "Būvniecības periodu sadalījums", "value": "era_dist"},
                        {"label": "Sienu materiālu sadalījums", "value": "wall_dist"},
                        {"label": "Stāvu sadalījums", "value": "floor_dist"},
                        {"label": "Primārās enerģijas sadalījums", "value": "primary_energy_dist"},
                        {"label": "Vidējā apkures enerģija", "value": "avg_energy"},
                    ],
                    value=["epc_dist", "era_dist", "avg_energy"],
                    inline=True,
                    style={"fontSize": "0.85rem", "marginBottom": "6px"},
                ),
                html.Div([
                    dbc.Switch(
                        id="chart-ref-toggle",
                        label="Rādīt pilnas izlases atsauci",
                        value=True,
                        style={"fontSize": "0.8rem", "display": "inline-block"},
                    ),
                    dbc.Tooltip(
                        "Kad ieslēgts, punktētas kontūras rāda pilnas izlases sadalījumu salīdzināšanai.",
                        id="chart-ref-tooltip",
                        target="chart-ref-toggle",
                        placement="right",
                    ),
                ], style={"marginBottom": "4px"}),
                dcc.Loading(
                    html.Div([
                        html.Div(id="epc-mini-chart", style={"flex": "0 1 340px", "minWidth": "260px", "maxWidth": "380px"}),
                        dbc.Tooltip("EPC klašu sadalījums filtrētajām ēkām.", id="epc-chart-tooltip", target="epc-mini-chart", placement="top"),
                        html.Div(id="era-mini-chart", style={"flex": "0 1 340px", "minWidth": "260px", "maxWidth": "380px"}),
                        dbc.Tooltip("Būvniecības periodu sadalījums filtrētajām ēkām.", id="era-chart-tooltip", target="era-mini-chart", placement="top"),
                        html.Div(id="wall-mini-chart", style={"flex": "0 1 340px", "minWidth": "260px", "maxWidth": "380px"}),
                        dbc.Tooltip("Sienu materiālu sadalījums filtrētajām ēkām.", id="wall-chart-tooltip", target="wall-mini-chart", placement="top"),
                        html.Div(id="floor-mini-chart", style={"flex": "0 1 340px", "minWidth": "260px", "maxWidth": "380px"}),
                        dbc.Tooltip("Virszemes stāvu sadalījums filtrētajām ēkām.", id="floor-chart-tooltip", target="floor-mini-chart", placement="top"),
                        html.Div(id="primary-energy-chart", style={"flex": "0 1 380px", "minWidth": "280px", "maxWidth": "420px"}),
                        dbc.Tooltip("Primārās neatjaunojamās enerģijas procentīļu sadalījums.", id="primary-energy-chart-tooltip", target="primary-energy-chart", placement="top"),
                        html.Div(id="energy-gauge-chart", style={"flex": "0 1 340px", "minWidth": "260px", "maxWidth": "380px"}),
                        dbc.Tooltip("Vidējā apkures enerģija filtrētajām ēkām salīdzinājumā ar pilnu izlasi.", id="energy-chart-tooltip", target="energy-gauge-chart", placement="top"),
                    ], style={"display": "flex", "flexWrap": "wrap", "gap": "8px"}),
                    type="circle",
                    color=BOL_PALETTE["teal"],
                ),
            ]),
            id="plots-collapse",
            is_open=False,
        ),

        # Maps panel collapse (viewable dot map — no filtering)
        dbc.Collapse(
            dbc.Card([
                html.Div([
                    dcc.Graph(
                        id="maps-dot-map",
                        config={"scrollZoom": True, "displayModeBar": False},
                        style={"height": "600px"},
                    ),
                    html.Div([
                        dbc.Button("◀", id="maps-page-prev", size="sm", color="secondary",
                                   className="me-1", disabled=True),
                        html.Span(id="maps-page-info",
                                  style={"fontSize": "0.8rem", "verticalAlign": "middle"}),
                        dbc.Button("▶", id="maps-page-next", size="sm", color="secondary",
                                   className="ms-1", disabled=True),
                    ], style={"textAlign": "center", "marginTop": "6px"}),
                ]),
            ], body=True, style={"padding": "10px"}),
            id="maps-collapse",
            is_open=False,
            className="mb-1",
        ),
        dcc.Store(id="maps-page-store", data=0),

        # Custom Sample collapse
        dbc.Collapse(
            dbc.Card([
                html.Div(
                    "Ielīmējiet kadastra apzīmējumus (14 ciparu numurus), lai filtrētu datu kopu. "
                    "Līdz 10 000 apzīmējumiem.",
                    id="custom-sample-help",
                    style={"fontSize": "0.75rem", "color": BOL_PALETTE["grey"], "marginBottom": "6px"},
                ),
                html.A(
                    "Rādīt pieņemtos formātus",
                    id="custom-sample-format-link",
                    style={"fontSize": "0.75rem", "color": BOL_PALETTE["teal"], "cursor": "pointer",
                           "textDecoration": "underline", "display": "block", "marginBottom": "4px"},
                ),
                dbc.Collapse(
                    html.Pre(
                        "• Ar komatu: 01001280293001, 01000580157004\n"
                        "• Ar semikolu: 01001280293001; 01000580157004\n"
                        "• Ar atstarpi: 01001280293001 01000580157004\n"
                        "• Ar tabulāciju (ielīmēts no Excel rindas)\n"
                        "• Pa vienai rindā (ielīmēts no Excel kolonnas)\n"
                        "• Katram apzīmējumam jābūt tieši 14 cipariem",
                        id="custom-sample-format-text",
                        style={"fontSize": "0.72rem", "color": BOL_PALETTE["grey"],
                               "backgroundColor": "#f8f8f8", "padding": "6px", "borderRadius": "4px",
                               "marginBottom": "6px", "whiteSpace": "pre-wrap"},
                    ),
                    id="custom-sample-format-collapse",
                    is_open=False,
                ),
                dcc.Textarea(
                    id="custom-sample-input",
                    placeholder="Ielīmējiet apzīmējumus šeit...\npiem. 01001280293001, 01000580157004",
                    style={"width": "100%", "height": "120px", "fontSize": "0.82rem",
                           "fontFamily": "monospace", "marginBottom": "8px"},
                ),
                html.Div([
                    dbc.Button("Ielādēt pielāgoto izlasi", id="custom-sample-load-btn",
                               size="sm", className="me-2",
                               style={"backgroundColor": BOL_PALETTE["teal"], "color": "#fff",
                                      "border": "none"}),
                    dbc.Button("Pievienot esošajam sarakstam", id="custom-sample-add-btn",
                               size="sm", className="me-2", disabled=True,
                               style={"backgroundColor": "transparent",
                                      "color": BOL_PALETTE["teal"],
                                      "border": f"1px solid {BOL_PALETTE['teal']}"}),
                    dbc.Button("Notīrīt pielāgoto izlasi", id="custom-sample-clear-btn",
                               color="outline-danger", size="sm", disabled=True),
                ], style={"marginBottom": "6px"}),
                # Result message area
                html.Div(id="custom-sample-result", style={"fontSize": "0.82rem", "marginTop": "4px"}),
                # Expandable invalid entries list
                dbc.Collapse(
                    html.Pre(
                        id="custom-sample-invalid-list",
                        style={"fontSize": "0.72rem", "maxHeight": "200px", "overflowY": "auto",
                               "backgroundColor": "#fff3cd", "padding": "6px", "borderRadius": "4px"},
                    ),
                    id="custom-sample-invalid-collapse",
                    is_open=False,
                ),
                # Confirm modal for clearing filters
                dbc.Modal([
                    dbc.ModalBody(
                        "Pielāgotas izlases ielāde notīrīs visus aktīvos filtrus. Turpināt?",
                        id="custom-sample-confirm-body",
                        style={"fontSize": "0.9rem"},
                    ),
                    dbc.ModalFooter([
                        dbc.Button("Turpināt", id="custom-sample-confirm-yes",
                                   style={"backgroundColor": BOL_PALETTE["teal"], "color": "#fff",
                                          "border": "none"}, className="me-2"),
                        dbc.Button("Atcelt", id="custom-sample-confirm-no",
                                   color="secondary"),
                    ]),
                ], id="custom-sample-confirm-modal", is_open=False, centered=True),
            ], body=True, style={"padding": "10px", "fontSize": "0.85rem"}),
            id="custom-sample-collapse",
            is_open=False,
            className="mb-1",
        ),
        dcc.Store(id="custom-sample-store", data=[]),

        # Column selector collapse (single panel — display columns)
        dbc.Collapse(
            dbc.Card([
                html.Div("Izvēlieties kolonnas rādīšanai tabulā.",
                         id="col-select-help",
                         style={"fontSize": "0.75rem", "color": BOL_PALETTE["grey"], "marginBottom": "6px"}),
                html.Div(
                    _build_column_picker(set(all_cols), picker_type="display", lang="lv"),
                    id="display-cols-container",
                ),
                # Hidden elements to keep callbacks happy
                html.Div([
                    dbc.Switch(id="dataset-mode-switch", value=True, style={"display": "none"}),
                    html.Span(id="dataset-mode-label", style={"display": "none"}),
                    _build_column_picker(set(all_cols), picker_type="load", lang="lv"),
                    dbc.Button("Update Dataset", id="update-dataset-btn",
                               color="secondary", size="sm", disabled=True,
                               style={"display": "none"}),
                ], style={"display": "none"}),
            ], body=True, style={"marginBottom": "1rem"}),
            id="col-selector-collapse",
            is_open=False,
        ),
        # Store for loaded columns (committed set — only changes on "Update Dataset" click)
        dcc.Store(id="loaded-columns-store", data=list(DEFAULT_VISIBLE)),
        dcc.Store(id="dataset-mode-store", data="full"),

        # AG Grid table (wrapped in loading spinner)
        dcc.Loading(
            html.Div(
                dag.AgGrid(
                    id="explorer-grid",
                    columnDefs=column_defs,
                    rowData=[],
                    dashGridOptions={
                        "pagination": True,
                        "paginationPageSize": 50,
                        "animateRows": True,
                        "rowSelection": "single",
                        "tooltipShowDelay": 0,
                        "domLayout": "normal",
                    },
                    defaultColDef={
                        "resizable": True,
                        "sortable": True,
                        "filter": True,
                    },
                    style={"height": "100%"},
                ),
                style={**CARD_STYLE, "height": "600px"},
            ),
            type="default",
            color=BOL_PALETTE["teal"],
            style={"minHeight": "200px"},
        ),

        # Below-table row: Download data (left) + Pagination (right)
        html.Div([
            dbc.Button("Lejupielādēt datus", id="download-data-btn", color="outline-secondary", size="sm"),
            dcc.Download(id="download-data-sink"),
            html.Div([
                # Page size selector (kebab menu)
                html.Span(
                    dbc.DropdownMenu(
                        label="⋮",
                        children=[
                            dbc.DropdownMenuItem("1 000", id="page-size-1000", active=True),
                            dbc.DropdownMenuItem("2 000", id="page-size-2000"),
                            dbc.DropdownMenuItem("5 000", id="page-size-5000"),
                            dbc.DropdownMenuItem("10 000", id="page-size-10000"),
                        ],
                        id="page-size-menu",
                        size="sm",
                        color="outline-secondary",
                        style={"display": "inline-block", "marginRight": "8px"},
                        toggle_style={
                            "fontSize": "1.1rem", "padding": "0.15rem 0.4rem",
                            "backgroundColor": "transparent",
                            "border": f"1px solid {BOL_PALETTE['grey']}",
                            "color": BOL_PALETTE["teal"],
                            "borderRadius": "6px",
                            "fontWeight": "bold",
                            "lineHeight": "1",
                        },
                        toggle_class_name="no-caret",
                    ),
                    title="Lapas izmērs / Page size",
                ),
                dbc.Button("← Iepriekšējie", id="page-prev-btn", color="outline-secondary",
                           size="sm", disabled=True, style={"marginRight": "8px"}),
                html.Span(id="page-info-label", children="1. lapa",
                          style={"fontSize": "0.82rem", "color": BOL_PALETTE["grey"],
                                 "verticalAlign": "middle", "marginRight": "8px"}),
                dbc.Button("Nākamie →", id="page-next-btn", color="outline-secondary",
                           size="sm", disabled=True),
            ], style={"display": "flex", "alignItems": "center"}),
        ], style={"display": "flex", "justifyContent": "space-between", "alignItems": "center",
                   "marginTop": "6px", "marginBottom": "8px"}),

        # Detail panel (row click → offcanvas)
        dbc.Offcanvas(
            html.Div(id="detail-panel-content"),
            id="detail-panel",
            title="Ēkas detaļas",
            placement="end",
            is_open=False,
            style={"width": "400px"},
        ),

        # Trigger initial data load after render
        dcc.Store(id="initial-load-trigger", data=True),
        # DuckDB aggregation results (full dataset mode only)
        dcc.Store(id="full-agg-store", data=None),
        # Pagination offset and page size
        dcc.Store(id="page-offset-store", data=0),
        dcc.Store(id="page-size-store", data=1000),

        # Download modal
        dbc.Modal([
            dbc.ModalHeader(dbc.ModalTitle("Lejupielādēt datus", id="download-modal-title")),
            dbc.ModalBody([
                # Format
                dbc.Label("Formāts", id="download-format-label", size="sm"),
                dbc.RadioItems(
                    id="download-format",
                    options=[
                        {"label": "CSV", "value": "csv"},
                        {"label": "Excel (XLSX)", "value": "xlsx"},
                    ],
                    value="csv",
                    inline=True,
                    className="mb-2",
                    style={"fontSize": "0.85rem"},
                ),
                # CSV separator (shown only for CSV)
                html.Div([
                    dbc.Label("CSV atdalītājs", id="download-sep-label", size="sm"),
                    dbc.RadioItems(
                        id="download-separator",
                        options=[
                            {"label": "; (semikols)", "value": ";"},
                            {"label": ", (komats)", "value": ","},
                            {"label": "TAB", "value": "\t"},
                        ],
                        value=";",
                        inline=True,
                        style={"fontSize": "0.85rem"},
                    ),
                ], id="download-sep-container", className="mb-2"),
                # Rows
                dbc.Label("Rindas", id="download-rows-label", size="sm"),
                dbc.RadioItems(
                    id="download-rows",
                    options=[
                        {"label": "Pašlaik filtrētās rindas", "value": "filtered"},
                        {"label": "Pilna datu kopa", "value": "all"},
                    ],
                    value="filtered",
                    inline=True,
                    className="mb-2",
                    style={"fontSize": "0.85rem"},
                ),
                # Columns
                dbc.Label("Kolonnas", id="download-cols-label", size="sm"),
                dbc.RadioItems(
                    id="download-cols-mode",
                    options=[
                        {"label": "Pašlaik redzamās kolonnas", "value": "visible"},
                        {"label": "Visas pieejamās kolonnas", "value": "all"},
                        {"label": "Pielāgota izvēle...", "value": "custom"},
                    ],
                    value="visible",
                    className="mb-2",
                    style={"fontSize": "0.85rem"},
                ),
                # Custom column picker (shown when "custom" selected)
                dbc.Collapse(
                    html.Div([
                        dbc.Checklist(
                            id="download-custom-cols",
                            options=[],
                            value=[],
                            style={"fontSize": "0.82rem", "maxHeight": "300px", "overflowY": "auto",
                                   "columns": "2", "columnGap": "20px"},
                        ),
                    ], id="download-col-picker-container"),
                    id="download-col-picker-collapse",
                    is_open=False,
                ),
            ]),
            dbc.ModalFooter([
                dcc.Loading(
                    html.Span(id="download-loading-indicator"),
                    type="circle", color=BOL_PALETTE["teal"],
                    style={"display": "inline-block", "marginRight": "10px"},
                ),
                dbc.Button("Lejupielādēt", id="download-execute-btn", disabled=False,
                          style={"backgroundColor": BOL_PALETTE["teal"], "color": "#fff",
                                 "border": "none"}),
            ]),
        ], id="download-modal", is_open=False, size="lg"),
    ])


# ---------------------------------------------------------------------------
# Callbacks
# ---------------------------------------------------------------------------

# Authoritative row count: reads virtualRowData directly in the browser
# Shows total dataset size or filtered count (from agg if truncated)
clientside_callback(
    """function(virtualRowData, aggData, lang) {
        if (!virtualRowData) return "Loading...";
        var label = (lang === "lv") ? " ēkas" : " buildings";
        if (aggData && aggData.total_count) {
            return aggData.total_count.toLocaleString() + label;
        }
        return virtualRowData.length.toLocaleString() + label;
    }""",
    Output("explorer-row-count", "children"),
    Input("explorer-grid", "virtualRowData"),
    Input("full-agg-store", "data"),
    State("lang-store", "data"),
)

# Enable panel buttons after 25-second loading period
@callback(
    Output("col-selector-toggle", "disabled"),
    Output("custom-filter-toggle", "disabled"),
    Output("filter-breakdown-toggle", "disabled"),
    Output("plots-toggle", "disabled"),
    Output("maps-toggle", "disabled"),
    Output("custom-sample-toggle", "disabled"),
    Output("panel-loading-msg", "style"),
    Input("panel-enable-timer", "n_intervals"),
)
def _enable_panels(n_intervals: int) -> tuple[bool, bool, bool, bool, bool, bool, dict]:
    if n_intervals < 1:
        return True, True, True, True, True, True, {"fontSize": "0.82rem", "color": "#6c757d",
                                                "fontStyle": "italic", "marginBottom": "6px"}
    return False, False, False, False, False, False, {"display": "none"}


@callback(
    Output("col-selector-collapse", "is_open"),
    Output("col-selector-toggle", "children"),
    Input("col-selector-toggle", "n_clicks"),
    State("lang-store", "data"),
    prevent_initial_call=True,
)
def _toggle_col_selector(n_clicks: int | None, lang: str | None) -> tuple[bool, str]:
    lang = lang or "lv"
    is_open = (n_clicks or 0) % 2 == 1
    return is_open, f"{t('btn.columns', lang)} {'\u25b2' if is_open else '\u25bc'}"


@callback(
    Output("custom-filter-collapse", "is_open"),
    Output("custom-filter-toggle", "children"),
    Input("custom-filter-toggle", "n_clicks"),
    State("lang-store", "data"),
    prevent_initial_call=True,
)
def _toggle_custom_filters(n_clicks: int | None, lang: str | None) -> tuple[bool, str]:
    lang = lang or "lv"
    is_open = (n_clicks or 0) % 2 == 1
    return is_open, f"{t('btn.custom_filters', lang)} {'\u25b2' if is_open else '\u25bc'}"



@callback(
    Output("plots-collapse", "is_open"),
    Output("plots-toggle", "children"),
    Input("plots-toggle", "n_clicks"),
    State("lang-store", "data"),
    prevent_initial_call=True,
)
def _toggle_plots(n_clicks: int | None, lang: str | None) -> tuple[bool, str]:
    lang = lang or "lv"
    is_open = (n_clicks or 0) % 2 == 1
    return is_open, f"{t('btn.plots', lang)} {'\u25b2' if is_open else '\u25bc'}"


@callback(
    Output("maps-collapse", "is_open"),
    Output("maps-toggle", "children"),
    Input("maps-toggle", "n_clicks"),
    State("lang-store", "data"),
    prevent_initial_call=True,
)
def _toggle_maps(n_clicks: int | None, lang: str | None) -> tuple[bool, str]:
    lang = lang or "lv"
    is_open = (n_clicks or 0) % 2 == 1
    return is_open, f"{t('btn.maps', lang)} {'▲' if is_open else '▼'}"


@callback(
    Output("filter-breakdown-collapse", "is_open"),
    Output("filter-breakdown-toggle", "children"),
    Input("filter-breakdown-toggle", "n_clicks"),
    State("lang-store", "data"),
    prevent_initial_call=True,
)
def _toggle_filter_breakdown(n_clicks: int | None, lang: str | None) -> tuple[bool, str]:
    lang = lang or "lv"
    is_open = (n_clicks or 0) % 2 == 1
    return is_open, f"{t('btn.filter_breakdown', lang)} {'\u25b2' if is_open else '\u25bc'}"


# Custom Sample panel toggle
@callback(
    Output("custom-sample-collapse", "is_open"),
    Output("custom-sample-toggle", "children"),
    Input("custom-sample-toggle", "n_clicks"),
    State("lang-store", "data"),
    prevent_initial_call=True,
)
def _toggle_custom_sample(n_clicks: int | None, lang: str | None) -> tuple[bool, str]:
    lang = lang or "lv"
    is_open = (n_clicks or 0) % 2 == 1
    return is_open, f"{t('btn.custom_sample', lang)} {'\u25b2' if is_open else '\u25bc'}"


# ---------------------------------------------------------------------------
# Maps panel: dot map with pagination
# ---------------------------------------------------------------------------
_MAPS_PAGE_SIZE = 10000


@callback(
    Output("maps-dot-map", "figure"),
    Output("maps-page-info", "children"),
    Output("maps-page-prev", "disabled"),
    Output("maps-page-next", "disabled"),
    Output("maps-page-store", "data"),
    Input("maps-collapse", "is_open"),
    Input("maps-page-prev", "n_clicks"),
    Input("maps-page-next", "n_clicks"),
    Input("filter-chain", "children"),
    State("maps-page-store", "data"),
    State("lang-store", "data"),
    # Filter stores — query DuckDB directly
    State("search-terms-store", "data"),
    State("search-mode", "data"),
    State("epc-slicer-store", "data"),
    State("era-slicer-store", "data"),
    State("floor-slicer-store", "data"),
    State("wall-slicer-store", "data"),
    State("type-slicer-store", "data"),
    State("map-selected-territory", "data"),
    State("custom-sample-store", "data"),
    prevent_initial_call=True,
)
def _render_maps_dot_map(
    is_open: bool,
    prev_clicks: int | None,
    next_clicks: int | None,
    filter_chain_children,
    current_page: int,
    lang: str | None,
    terms: list[str] | None,
    search_mode: str | None,
    epc_classes: list[str] | None,
    eras: list[str] | None,
    floors: list[str] | None,
    walls: list[str] | None,
    btypes: list[str] | None,
    map_territory: str | None,
    custom_sample: list[str] | None,
):
    from dash import ctx, no_update

    if not is_open:
        return no_update, no_update, no_update, no_update, no_update

    lang = lang or "lv"

    # Query DuckDB directly for ALL filtered buildings with coordinates
    cols_needed = [
        "KadastraApzimBuilding", "lat_4326", "lon_4326",
        "Street", "House", "Town_Parish",
        "construction_year", "BuildingGroundFloors",
        "epc_class_cert", "epc_class_georiga",
        "predicted_epc_class", "combined_epc_class",
        "combined_heating_kwh",
    ]
    rows_data, agg = _search_filter_duckdb(
        terms or [], search_mode or "any",
        epc_classes or list(EPC_CLASSES_DISPLAY) + ["N/A"],
        eras or list(ERA_BINS) + ["N/A"],
        walls or list(WALL_MATERIALS) + ["N/A"],
        cols_needed, map_territory, cols_needed,
        page_offset=0, page_size=999999999,
        custom_sample=custom_sample or [],
        floors=floors or list(FLOOR_GROUPS) + ["N/A"],
        btypes=btypes or list(BUILDING_TYPES),
    )

    # Filter to rows with valid coordinates
    rows_with_coords = []
    for r in rows_data:
        lat = r.get("lat_4326")
        lon = r.get("lon_4326")
        if lat is not None and lon is not None and lat != "" and lon != "":
            try:
                float(lat); float(lon)
                rows_with_coords.append(r)
            except (ValueError, TypeError):
                continue

    total = len(rows_with_coords)
    max_page = max(0, (total - 1) // _MAPS_PAGE_SIZE) if total > 0 else 0

    # Handle pagination
    triggered = ctx.triggered_id
    page = current_page or 0
    if triggered == "maps-page-next":
        page = min(page + 1, max_page)
    elif triggered == "maps-page-prev":
        page = max(page - 1, 0)
    elif triggered in ("maps-collapse", "filter-chain"):
        page = 0

    start = page * _MAPS_PAGE_SIZE
    end = min(start + _MAPS_PAGE_SIZE, total)
    page_rows = rows_with_coords[start:end]

    # Build Plotly Scattermapbox
    fl_label = "St\u0101vi" if lang == "lv" else "Floors"
    yr_label = "B\u016bvgads" if lang == "lv" else "Year"
    cert_label = "Sert." if lang == "lv" else "Cert"
    geo_label = "GeoR." if lang == "lv" else "GeoR"
    pred_label = "Progn." if lang == "lv" else "Pred"
    comb_label = "Komb." if lang == "lv" else "Comb"

    lats, lons, hover_texts, cadastre_ids, dot_colors = [], [], [], [], []
    default_color = "#999999"
    for r in page_rows:
        lats.append(float(r["lat_4326"]))
        lons.append(float(r["lon_4326"]))
        cadastre_ids.append(r.get("KadastraApzimBuilding", ""))
        epc_cls = r.get("combined_epc_class") or None
        dot_colors.append(EPC_PALETTE.get(epc_cls, default_color))
        # Hover text
        addr_parts = []
        for fld in ("Street", "House", "Town_Parish"):
            v = r.get(fld)
            if v and str(v) not in ("", "None", "nan"):
                addr_parts.append(str(v))
        addr = ", ".join(addr_parts) if addr_parts else "\u2014"
        yr = r.get("construction_year", "\u2014")
        if yr and yr != "\u2014":
            try:
                yr = int(float(yr))
            except (ValueError, TypeError):
                pass
        floors_val = r.get("BuildingGroundFloors")
        fl_str = str(int(float(floors_val))) if floors_val is not None and floors_val != "" else "\u2014"
        epc_cert = r.get("epc_class_cert") or "\u2014"
        epc_geo = r.get("epc_class_georiga") or "\u2014"
        epc_pred = r.get("predicted_epc_class") or "\u2014"
        epc_comb = r.get("combined_epc_class") or "\u2014"
        kwh = r.get("combined_heating_kwh")
        kwh_str = f"{float(kwh):.0f}" if kwh and kwh != "" else "\u2014"
        hover_texts.append(
            f"<b>{r.get('KadastraApzimBuilding', '')}</b><br>"
            f"{addr}<br>"
            f"{yr_label}: {yr} | {fl_label}: {fl_str}<br>"
            f"EPC {cert_label}: {epc_cert} | {geo_label}: {epc_geo}<br>"
            f"EPC {pred_label}: {epc_pred} | {comb_label}: {epc_comb}<br>"
            f"kWh/m\u00b2: {kwh_str}"
        )

    fig = go.Figure()
    if lats:
        fig.add_trace(go.Scattermapbox(
            lat=lats, lon=lons, mode="markers",
            marker=dict(size=12, color=dot_colors, opacity=0.75),
            text=hover_texts, hoverinfo="text",
            hoverlabel=dict(bgcolor="white", bordercolor="#ccc",
                            font=dict(size=11, color="#333")),
            customdata=cadastre_ids,
        ))

    geojson = _load_geojson()
    fig.update_layout(
        mapbox=dict(
            style="open-street-map",
            center=dict(lat=56.95, lon=24.1),
            zoom=6,
            layers=[{"source": geojson, "type": "line",
                     "color": "#555", "line": {"width": 1.5}}],
        ),
        margin=dict(l=0, r=0, t=0, b=0),
        showlegend=False,
        dragmode="pan",
    )

    # Page info
    if total == 0:
        info = "Nav koordin\u0101tu" if lang == "lv" else "No coordinates"
    else:
        info = f"{start + 1}\u2013{end} / {total}"

    return fig, info, page <= 0, page >= max_page, page


# Maps panel: click dot → open detail panel
@callback(
    Output("detail-panel", "is_open", allow_duplicate=True),
    Output("detail-panel-content", "children", allow_duplicate=True),
    Input("maps-dot-map", "clickData"),
    State("lang-store", "data"),
    prevent_initial_call=True,
)
def _maps_dot_click(click_data, lang):
    from dash import no_update
    lang = lang or "lv"
    if not click_data:
        return no_update, no_update
    point = click_data.get("points", [{}])[0]
    cadastre = point.get("customdata", "")
    if isinstance(cadastre, list):
        cadastre = cadastre[0] if cadastre else ""
    cadastre = str(cadastre)
    if not cadastre:
        return no_update, no_update
    con = _get_duckdb_con()
    df = con.execute(
        'SELECT * FROM buildings WHERE "KadastraApzimBuilding" = ? LIMIT 1',
        [cadastre],
    ).fetchdf()
    if df.empty:
        return no_update, no_update
    row = df.iloc[0].to_dict()
    rows = []
    for col, val in row.items():
        display = get_display_name(col, lang)
        if col in ("EnergoefektivKlase", "EnergoefektivKlase_georiga_pref",
                   "epc_class_cert", "epc_class_georiga", "combined_epc_class",
                   "predicted_epc_class") and val in EPC_PALETTE:
            val_el = html.Span(val, style={
                "backgroundColor": EPC_PALETTE[val], "color": "#FFFFFF",
                "padding": "2px 10px", "borderRadius": "4px", "fontWeight": "700",
            })
        elif isinstance(val, float):
            val_el = f"{val:.1f}"
        else:
            val_el = str(val) if val is not None else "\u2014"
        rows.append(html.Tr([html.Td(display, style={"fontWeight": "600"}), html.Td(val_el)]))
    return True, dbc.Table([html.Tbody(rows)], bordered=True, size="sm", style={"fontSize": "0.85rem"})


# Color Custom Sample button when custom sample is active
@callback(
    Output("custom-sample-toggle", "color"),
    Input("custom-sample-store", "data"),
)
def _color_custom_sample_btn(sample: list[str]) -> str:
    return "info" if sample else "secondary"


# Toggle format help inside custom sample panel
@callback(
    Output("custom-sample-format-collapse", "is_open"),
    Input("custom-sample-format-link", "n_clicks"),
    State("custom-sample-format-collapse", "is_open"),
    prevent_initial_call=True,
)
def _toggle_format_help(n_clicks: int | None, is_open: bool) -> bool:
    return not is_open


# Close confirm modal on cancel
@callback(
    Output("custom-sample-confirm-modal", "is_open", allow_duplicate=True),
    Input("custom-sample-confirm-no", "n_clicks"),
    prevent_initial_call=True,
)
def _close_confirm_modal(_n: int) -> bool:
    return False


def _parse_designations(text: str) -> tuple[list[str], list[str]]:
    """Parse pasted text into valid and invalid cadastral designations.

    Accepts comma, semicolon, space, tab, newline as separators.
    Valid designation: exactly 14 digits.
    Returns (valid_list, invalid_list).
    """
    import re
    # Split on any common separator
    tokens = re.split(r'[,;\s\t\n\r]+', text.strip())
    tokens = [t.strip() for t in tokens if t.strip()]
    valid = []
    invalid = []
    for tok in tokens:
        if re.fullmatch(r'\d{14}', tok):
            valid.append(tok)
        else:
            invalid.append(tok)
    return valid, invalid


# Main custom sample load/add/clear callback
@callback(
    Output("custom-sample-store", "data"),
    Output("custom-sample-result", "children"),
    Output("custom-sample-invalid-collapse", "is_open"),
    Output("custom-sample-invalid-list", "children"),
    Output("custom-sample-add-btn", "disabled"),
    Output("custom-sample-clear-btn", "disabled"),
    Output("custom-sample-input", "value"),
    Output("custom-sample-confirm-modal", "is_open"),
    # Reset other filters when loading new sample
    Output("epc-slicer-store", "data", allow_duplicate=True),
    Output("era-slicer-store", "data", allow_duplicate=True),
    Output("floor-slicer-store", "data", allow_duplicate=True),
    Output("wall-slicer-store", "data", allow_duplicate=True),
    Output("type-slicer-store", "data", allow_duplicate=True),
    Output("map-selected-territory", "data", allow_duplicate=True),
    Output("search-terms-store", "data", allow_duplicate=True),
    Input("custom-sample-load-btn", "n_clicks"),
    Input("custom-sample-add-btn", "n_clicks"),
    Input("custom-sample-clear-btn", "n_clicks"),
    Input("custom-sample-confirm-yes", "n_clicks"),
    State("custom-sample-input", "value"),
    State("custom-sample-store", "data"),
    State("lang-store", "data"),
    State("epc-slicer-store", "data"),
    State("era-slicer-store", "data"),
    State("floor-slicer-store", "data"),
    State("wall-slicer-store", "data"),
    State("type-slicer-store", "data"),
    State("map-selected-territory", "data"),
    State("search-terms-store", "data"),
    prevent_initial_call=True,
)
def _custom_sample_action(
    load_clicks: int | None, add_clicks: int | None, clear_clicks: int | None,
    confirm_clicks: int | None,
    text: str | None, current_sample: list[str], lang: str | None,
    epc_classes: list[str], eras: list[str], floors: list[str], walls: list[str],
    btypes: list[str],
    map_territory: str | None, search_terms: list[str],
) -> tuple:
    from dash import no_update
    lang = lang or "lv"
    triggered = ctx.triggered_id
    NO = no_update
    # 14 outputs total
    noop = (NO,) * 15

    if triggered == "custom-sample-clear-btn":
        return (
            [],  # clear store
            html.Span("✓", style={"color": "green"}),
            False, "",  # hide invalid list
            True, True,  # disable add/clear buttons
            "",  # clear textarea
            False,  # don't show confirm dialog
            # Don't reset other filters on clear
            NO, NO, NO, NO, NO, NO, NO,
        )

    # Check if filters are active (for load only)
    def _has_active_filters() -> bool:
        all_epc = len(EPC_CLASSES_DISPLAY) + 1
        all_eras_n = len(ERA_BINS) + 1
        all_floors_n = len(FLOOR_GROUPS) + 1
        all_walls_n = len(WALL_MATERIALS) + 1
        return (
            (epc_classes and len(epc_classes) < all_epc)
            or (eras and len(eras) < all_eras_n)
            or (floors and len(floors) < all_floors_n)
            or (walls and len(walls) < all_walls_n)
            or (btypes and len(btypes) < (len(BUILDING_TYPES) + 1))
            or bool(map_territory)
            or bool(search_terms)
        )

    if triggered == "custom-sample-load-btn":
        if _has_active_filters():
            # Show confirm dialog, don't proceed yet
            return (NO, NO, NO, NO, NO, NO, NO, True, NO, NO, NO, NO, NO, NO, NO)
        # Fall through to load logic below

    if triggered in ("custom-sample-load-btn", "custom-sample-confirm-yes", "custom-sample-add-btn"):
        if not text or not text.strip():
            return (NO, html.Span("⚠ " + ("No text pasted." if lang == "en" else "Nav ielīmēts teksts."),
                                   style={"color": "orange"}),
                    False, "", NO, NO, NO, False, NO, NO, NO, NO, NO, NO, NO)

        valid, invalid = _parse_designations(text)

        if not valid:
            return (NO,
                    html.Span("⚠ " + ("No valid designations found." if lang == "en" else "Nav atrasti derīgi apzīmējumi."),
                              style={"color": "red"}),
                    bool(invalid), "\n".join(invalid),
                    NO, NO, NO, False, NO, NO, NO, NO, NO, NO, NO)

        # Check against DuckDB
        con = _get_duckdb_con()
        placeholders = ", ".join("?" for _ in valid)
        found_rows = con.execute(
            f'SELECT DISTINCT "KadastraApzimBuilding" FROM buildings '
            f'WHERE "KadastraApzimBuilding" IN ({placeholders})',
            valid,
        ).fetchdf()
        found_set = set(found_rows["KadastraApzimBuilding"])
        not_found = [v for v in valid if v not in found_set]

        if triggered == "custom-sample-add-btn":
            existing = set(current_sample or [])
            new_matches = [v for v in valid if v in found_set and v not in existing]
            merged = list(existing | (set(valid) & found_set))
            msg = t("custom.result_added", lang).format(
                matched=len(new_matches), total=len(valid),
                grand_total=len(merged),
                not_found=len(not_found), invalid=len(invalid),
            )
            result_el = html.Div([
                html.Span("✓ ", style={"color": "green", "fontWeight": "bold"}),
                html.Pre(msg, style={"display": "inline", "whiteSpace": "pre-wrap", "margin": 0,
                                     "fontSize": "0.82rem"}),
            ])
            return (
                merged, result_el,
                bool(invalid), "\n".join(invalid) if invalid else "",
                False, False, "", False,
                NO, NO, NO, NO, NO, NO, NO,
            )
        else:
            # Load new sample (or confirmed load after dialog)
            matched = list(found_set)
            msg = t("custom.result_success", lang).format(
                matched=len(matched), total=len(valid),
                pct=round(100 * len(matched) / len(valid), 1) if valid else 0,
                not_found=len(not_found), invalid=len(invalid),
            )
            result_el = html.Div([
                html.Span("✓ ", style={"color": "green", "fontWeight": "bold"}),
                html.Pre(msg, style={"display": "inline", "whiteSpace": "pre-wrap", "margin": 0,
                                     "fontSize": "0.82rem"}),
            ])
            all_epc = list(EPC_CLASSES_DISPLAY) + ["N/A"]
            all_eras_list = list(ERA_BINS) + ["N/A"]
            all_floors_list = list(FLOOR_GROUPS) + ["N/A"]
            all_walls_list = list(WALL_MATERIALS) + ["N/A"]
            all_types_list = list(BUILDING_TYPES)
            return (
                matched, result_el,
                bool(invalid), "\n".join(invalid) if invalid else "",
                False, False, "", False,
                all_epc, all_eras_list, all_floors_list, all_walls_list, all_types_list, None, [],
            )

    return noop


# Color Custom Filters button teal when any slicer or map is active
@callback(
    Output("custom-filter-toggle", "color"),
    Input("epc-slicer-store", "data"),
    Input("era-slicer-store", "data"),
    Input("floor-slicer-store", "data"),
    Input("wall-slicer-store", "data"),
    Input("type-slicer-store", "data"),
    Input("map-selected-territory", "data"),
)
def _color_custom_filter_btn(epc: list[str], eras: list[str], floors: list[str], walls: list[str], btypes: list[str], map_sel: str | None) -> str:
    all_epc = len(EPC_CLASSES_DISPLAY) + 1  # +1 for N/A
    all_eras = len(ERA_BINS) + 1
    all_floors = len(FLOOR_GROUPS) + 1
    all_walls = len(WALL_MATERIALS) + 1
    all_types = len(BUILDING_TYPES)
    has_filter = (
        len(epc) < all_epc
        or len(eras) < all_eras
        or len(floors) < all_floors
        or len(walls) < all_walls
        or len(btypes) < all_types
        or bool(map_sel)
    )
    return "info" if has_filter else "secondary"


# Sync search mode switch → store
@callback(
    Output("search-mode", "data"),
    Output("search-mode-label", "children"),
    Input("search-mode-switch", "value"),
    Input("lang-store", "data"),
)
def _sync_search_mode(is_all: bool, lang: str | None) -> tuple[str, str]:
    lang = lang or "lv"
    mode = "all" if is_all else "any"
    return mode, t("search.all", lang) if is_all else t("search.any", lang)


# Sync slicer mode switch → store + label
@callback(
    Output("slicer-mode-store", "data"),
    Output("slicer-mode-label", "children"),
    Input("slicer-mode-switch", "value"),
    Input("lang-store", "data"),
)
def _sync_slicer_mode(is_single: bool, lang: str | None) -> tuple[str, str]:
    lang = lang or "lv"
    return ("single" if is_single else "multi"), (t("slicer.single", lang) if is_single else t("slicer.multi", lang))


# Sync dataset mode switch → label
@callback(
    Output("dataset-mode-label", "children"),
    Input("dataset-mode-switch", "value"),
)
def _sync_dataset_mode_label(is_full: bool) -> str:
    return "Full residential (380k)" if is_full else "EPC only (23k)"


# Hide row-count badge when filtering breakdown shows active filters
@callback(
    Output("explorer-row-count", "style"),
    Input("filter-chain", "children"),
    Input("filter-breakdown-collapse", "is_open"),
)
def _toggle_row_badge(chain_children: list | str | None, breakdown_open: bool) -> dict:
    has_active_filters = isinstance(chain_children, list) and len(chain_children) > 1
    # Hide only when breakdown panel is open AND has active filter steps
    hide = breakdown_open and has_active_filters
    base = {
        "backgroundColor": BOL_PALETTE["teal"], "color": "#FFFFFF",
        "padding": "0.3rem 0.8rem", "borderRadius": "12px",
        "fontSize": "0.9rem", "fontWeight": "600",
    }
    if hide:
        base["display"] = "none"
    return base


@callback(
    Output("explorer-grid", "columnDefs", allow_duplicate=True),
    Input({"type": "col-display", "block": ALL}, "value"),
    State("lang-store", "data"),
    prevent_initial_call=True,
)
def _update_columns(block_values: list[list[str]], lang: str | None) -> list[dict]:
    lang = lang or "lv"
    selected = [c for block in block_values for c in block]
    all_cols = list(EPC_TABLE_COLUMNS)
    try:
        con = _get_duckdb_con()
        schema = con.execute(
            "SELECT column_name, data_type FROM information_schema.columns WHERE table_name='buildings'"
        ).fetchall()
        dtypes = {name: dtype for name, dtype in schema}
    except Exception:
        dtypes = {}
    return _make_column_defs(selected, all_cols, dtypes, lang=lang)


# ---------------------------------------------------------------------------
# DuckDB query backend for full residential dataset (380k rows)
# ---------------------------------------------------------------------------
import duckdb as _duckdb
from pathlib import Path as _DuckPath

_DUCKDB_PATH = _DuckPath(__file__).resolve().parents[2] / "data" / "interim" / "dashboard_full_residential.duckdb"
_DUCKDB_CON: _duckdb.DuckDBPyConnection | None = None


def _get_duckdb_con() -> _duckdb.DuckDBPyConnection:
    """Get or create a read-only DuckDB connection (singleton)."""
    global _DUCKDB_CON
    if _DUCKDB_CON is None:
        _DUCKDB_CON = _duckdb.connect(str(_DUCKDB_PATH), read_only=True)
    return _DUCKDB_CON


def _search_filter_duckdb(
    terms: list[str], mode: str, epc_classes: list[str],
    eras: list[str], walls: list[str],
    loaded_cols: list[str], map_territory: str | None,
    selected_cols: list[str],
    page_offset: int = 0,
    page_size: int = 1000,
    custom_sample: list[str] | None = None,
    floors: list[str] | None = None,
    btypes: list[str] | None = None,
) -> tuple[list[dict], dict]:
    """Query DuckDB for full residential dataset with filters applied server-side."""
    con = _get_duckdb_con()

    # Always SELECT all columns — user can toggle column visibility in the grid
    all_db_cols = [row[0] for row in con.execute("SELECT column_name FROM information_schema.columns WHERE table_name='buildings'").fetchall()]
    keep = all_db_cols

    select_clause = ", ".join(f'"{c}"' for c in keep)

    # Build WHERE conditions
    conditions: list[str] = []
    params: list = []

    # Custom sample filter (always first priority)
    if custom_sample:
        placeholders = ", ".join("?" for _ in custom_sample)
        conditions.append(f'"KadastraApzimBuilding" IN ({placeholders})')
        params.extend(custom_sample)

    # Territory / neighbourhood filter
    if map_territory:
        if map_territory == "__NA__":
            conditions.append("gis_territory_name IS NULL")
        elif map_territory.startswith("__RIGA__:"):
            neighbourhood = map_territory[9:]
            conditions.append("apkaime_name = ?")
            params.append(neighbourhood)
        elif map_territory.startswith("__DGP__:"):
            neighbourhood = map_territory[8:]
            conditions.append("apkaime_name = ?")
            params.append(neighbourhood)
        else:
            conditions.append("gis_territory_name = ?")
            params.append(map_territory)

    # Era slicer (with N/A support)
    era_vals = [e for e in eras if e != "N/A"]
    era_na = "N/A" in eras
    all_eras_count = len(ERA_BINS) + 1  # +1 for N/A
    if eras and len(eras) < all_eras_count:
        if era_vals and era_na:
            placeholders = ", ".join("?" for _ in era_vals)
            conditions.append(f"(era_bin IN ({placeholders}) OR era_bin IS NULL)")
            params.extend(era_vals)
        elif era_vals:
            placeholders = ", ".join("?" for _ in era_vals)
            conditions.append(f"era_bin IN ({placeholders})")
            params.extend(era_vals)
        elif era_na:
            conditions.append("era_bin IS NULL")

    # Floor count slicer (with N/A support)
    floors = floors or []
    floor_vals = [f for f in floors if f != "N/A"]
    floor_na = "N/A" in floors
    all_floors_count = len(FLOOR_GROUPS) + 1
    if floors and len(floors) < all_floors_count:
        # Build SQL CASE expression to map raw values to groups
        range_parts: list[str] = []
        for fv in floor_vals:
            if fv == "10+":
                range_parts.append('"BuildingGroundFloors" >= 10')
            else:
                range_parts.append(f'"BuildingGroundFloors" = {int(fv)}')
        if range_parts and floor_na:
            conditions.append(f"({' OR '.join(range_parts)} OR \"BuildingGroundFloors\" IS NULL OR \"BuildingGroundFloors\" <= 0)")
        elif range_parts:
            conditions.append(f"({' OR '.join(range_parts)})")
        elif floor_na:
            conditions.append('("BuildingGroundFloors" IS NULL OR "BuildingGroundFloors" <= 0)')

    # Wall material slicer (with N/A support)
    wall_vals = [w for w in walls if w != "N/A"]
    wall_na = "N/A" in walls
    all_walls_count = len(WALL_MATERIALS) + 1
    if walls and len(walls) < all_walls_count:
        if wall_vals and wall_na:
            placeholders = ", ".join("?" for _ in wall_vals)
            conditions.append(f"(wall_material_grouped IN ({placeholders}) OR wall_material_grouped IS NULL)")
            params.extend(wall_vals)
        elif wall_vals:
            placeholders = ", ".join("?" for _ in wall_vals)
            conditions.append(f"wall_material_grouped IN ({placeholders})")
            params.extend(wall_vals)
        elif wall_na:
            conditions.append("wall_material_grouped IS NULL")

    # Building type slicer (no NULLs — all rows classified)
    btypes = btypes or []
    all_types_count = len(BUILDING_TYPES)
    if btypes and len(btypes) < all_types_count:
        placeholders = ", ".join("?" for _ in btypes)
        conditions.append(f"building_type IN ({placeholders})")
        params.extend(btypes)

    # EPC class slicer (with N/A support, uses combined_epc_class)
    epc_vals = [c for c in epc_classes if c != "N/A"]
    epc_na = "N/A" in epc_classes
    all_epc_count = len(EPC_CLASSES_DISPLAY) + 1
    if epc_classes and len(epc_classes) < all_epc_count:
        expanded = list(set(epc_vals) | ({"A+"} if "A" in epc_vals else set()))
        if expanded and epc_na:
            placeholders = ", ".join("?" for _ in expanded)
            conditions.append(f"(combined_epc_class IN ({placeholders}) OR combined_epc_class IS NULL)")
            params.extend(expanded)
        elif expanded:
            placeholders = ", ".join("?" for _ in expanded)
            conditions.append(f"combined_epc_class IN ({placeholders})")
            params.extend(expanded)
        elif epc_na:
            conditions.append("combined_epc_class IS NULL")

    # Text search (searches ALL text columns in DuckDB, not just displayed ones)
    if terms:
        text_conditions = []
        for term in terms:
            col_likes = [f'LOWER(CAST("{c}" AS VARCHAR)) LIKE ?' for c in all_db_cols]
            if col_likes:
                text_conditions.append(f"({' OR '.join(col_likes)})")
                params.extend([f"%{term.lower()}%"] * len(col_likes))

        if text_conditions:
            joiner = " AND " if mode == "all" else " OR "
            conditions.append(f"({joiner.join(text_conditions)})")

    where_clause = f" WHERE {' AND '.join(conditions)}" if conditions else ""

    # Get total count (for badge/info)
    count_query = f"SELECT COUNT(*) FROM buildings{where_clause}"
    total_count = con.execute(count_query, params).fetchone()[0]

    # Get limited rows for table display (ordered by cadastre nr for stable pagination)
    offset_clause = f" OFFSET {page_offset}" if page_offset > 0 else ""
    query = f"SELECT {select_clause} FROM buildings{where_clause} ORDER BY \"KadastraApzimBuilding\" LIMIT {page_size}{offset_clause}"
    df = con.execute(query, params).fetchdf()

    # Populate EnergoefektivKlase from combined_epc_class for grid display
    if "combined_epc_class" in df.columns and "EnergoefektivKlase" not in df.columns:
        df["EnergoefektivKlase"] = df["combined_epc_class"]

    # Get aggregations for plots (cheap GROUP BY queries)
    agg: dict = {"total_count": total_count}

    # EPC class distribution (combined)
    extra_filter = " AND combined_epc_class IS NOT NULL" if where_clause else " WHERE combined_epc_class IS NOT NULL"
    epc_agg = con.execute(
        f"SELECT combined_epc_class, COUNT(*) as cnt FROM buildings{where_clause}{extra_filter} GROUP BY combined_epc_class",
        params,
    ).fetchdf()
    agg["epc_dist"] = dict(zip(epc_agg["combined_epc_class"], epc_agg["cnt"])) if len(epc_agg) > 0 else {}
    agg["epc_dist"]["N/A"] = total_count - sum(agg["epc_dist"].values())

    # Era distribution
    extra_filter = " AND era_bin IS NOT NULL" if where_clause else " WHERE era_bin IS NOT NULL"
    era_agg = con.execute(
        f"SELECT era_bin, COUNT(*) as cnt FROM buildings{where_clause}{extra_filter} GROUP BY era_bin",
        params,
    ).fetchdf()
    agg["era_dist"] = dict(zip(era_agg["era_bin"], era_agg["cnt"])) if len(era_agg) > 0 else {}
    agg["era_dist"]["N/A"] = total_count - sum(agg["era_dist"].values())

    # Wall material distribution
    extra_filter = " AND wall_material_grouped IS NOT NULL" if where_clause else " WHERE wall_material_grouped IS NOT NULL"
    wall_agg = con.execute(
        f"SELECT wall_material_grouped, COUNT(*) as cnt FROM buildings{where_clause}{extra_filter} GROUP BY wall_material_grouped",
        params,
    ).fetchdf()
    agg["wall_dist"] = dict(zip(wall_agg["wall_material_grouped"], wall_agg["cnt"])) if len(wall_agg) > 0 else {}
    agg["wall_dist"]["N/A"] = total_count - sum(agg["wall_dist"].values())

    # Floor count distribution
    floor_q = f"SELECT CASE WHEN \"BuildingGroundFloors\" IS NULL OR \"BuildingGroundFloors\" <= 0 THEN 'N/A' WHEN \"BuildingGroundFloors\" >= 10 THEN '10+' ELSE CAST(CAST(\"BuildingGroundFloors\" AS INTEGER) AS VARCHAR) END as fg, COUNT(*) as cnt FROM buildings{where_clause} GROUP BY fg"
    floor_agg = con.execute(floor_q, params).fetchdf()
    agg["floor_dist"] = dict(zip(floor_agg["fg"], floor_agg["cnt"])) if len(floor_agg) > 0 else {}

    # Building type distribution
    type_extra = " AND building_type IS NOT NULL" if where_clause else " WHERE building_type IS NOT NULL"
    type_agg = con.execute(
        f"SELECT building_type, COUNT(*) as cnt FROM buildings{where_clause}{type_extra} GROUP BY building_type",
        params,
    ).fetchdf()
    agg["type_dist"] = dict(zip(type_agg["building_type"], type_agg["cnt"])) if len(type_agg) > 0 else {}
    agg["type_dist"]["N/A"] = total_count - sum(agg["type_dist"].values())

    # Primary energy percentile distribution (20 bins of 5%)
    pe_q = f"SELECT primary_energy_pctile FROM buildings{where_clause}" + (" AND" if where_clause else " WHERE") + " primary_energy_pctile IS NOT NULL"
    pe_rows = con.execute(pe_q, params).fetchall()
    pe_bins = [0] * 20
    for (p,) in pe_rows:
        idx = min(int(float(p) / 5.0), 19)
        pe_bins[idx] += 1
    agg["pe_pctile_dist"] = pe_bins

    # Average combined heating energy
    avg_q = f"SELECT AVG(combined_heating_kwh) FROM buildings{where_clause}"
    avg_result = con.execute(avg_q + " AND combined_heating_kwh IS NOT NULL" if where_clause else avg_q + " WHERE combined_heating_kwh IS NOT NULL", params).fetchone()
    agg["avg_heating"] = float(avg_result[0]) if avg_result and avg_result[0] is not None else None

    return df.to_dict("records"), agg


@callback(
    Output("explorer-grid", "rowData"),
    Output("full-agg-store", "data"),
    Output("page-prev-btn", "disabled"),
    Output("page-next-btn", "disabled"),
    Output("page-info-label", "children"),
    Input("search-terms-store", "data"),
    Input("search-mode", "data"),
    Input("epc-slicer-store", "data"),
    Input("era-slicer-store", "data"),
    Input("floor-slicer-store", "data"),
    Input("wall-slicer-store", "data"),
    Input("type-slicer-store", "data"),
    Input("initial-load-trigger", "data"),
    Input("map-selected-territory", "data"),
    Input("page-offset-store", "data"),
    Input("page-size-store", "data"),
    Input("custom-sample-store", "data"),
    State({"type": "col-display", "block": ALL}, "value"),
    Input("lang-store", "data"),
)
def _search_filter(
    terms: list[str], mode: str, epc_classes: list[str],
    eras: list[str], floors: list[str], walls: list[str], btypes: list[str],
    _trigger: bool,
    map_territory: str | None,
    page_offset: int,
    page_size: int,
    custom_sample: list[str],
    block_values: list[list[str]],
    lang: str | None,
) -> tuple[list[dict], dict | None, bool, bool, str]:
    lang = lang or "lv"
    page_size = page_size or 1000
    selected_cols = [c for block in block_values for c in block]
    rows, agg = _search_filter_duckdb(
        terms, mode, epc_classes, eras, walls,
        selected_cols, map_territory, selected_cols,
        page_offset=page_offset or 0, page_size=page_size,
        custom_sample=custom_sample or [],
        floors=floors or [],
        btypes=btypes or [],
    )
    # Compute pagination state
    offset = page_offset or 0
    total = agg.get("total_count", 0) if agg else 0
    page_num = offset // page_size + 1
    total_pages = max(1, (total + page_size - 1) // page_size)
    if total > page_size:
        label = t("page.of", lang).format(page=page_num, total=total_pages)
    else:
        label = t("page.buildings", lang).format(n=f"{total:,}")
    return rows, agg, offset <= 0, offset + page_size >= total, label


# ---------------------------------------------------------------------------
# Pagination: prev/next buttons update page-offset-store
# ---------------------------------------------------------------------------
@callback(
    Output("page-offset-store", "data"),
    Input("page-prev-btn", "n_clicks"),
    Input("page-next-btn", "n_clicks"),
    # Reset to page 0 when filters change
    Input("search-terms-store", "data"),
    Input("epc-slicer-store", "data"),
    Input("era-slicer-store", "data"),
    Input("floor-slicer-store", "data"),
    Input("wall-slicer-store", "data"),
    Input("type-slicer-store", "data"),
    Input("map-selected-territory", "data"),
    Input("custom-sample-store", "data"),
    State("page-offset-store", "data"),
    State("full-agg-store", "data"),
    State("page-size-store", "data"),
    prevent_initial_call=True,
)
def _paginate(
    prev_clicks: int | None, next_clicks: int | None,
    _terms: list, _epc: list, _eras: list, _floors: list, _walls: list, _btypes: list,
    _territory: str | None,
    _custom: list,
    current_offset: int, agg_data: dict | None, page_size: int,
) -> int:
    triggered = ctx.triggered_id
    total = agg_data.get("total_count", 0) if agg_data else 0
    page_size = page_size or 1000

    if triggered == "page-prev-btn":
        return max(0, (current_offset or 0) - page_size)
    elif triggered == "page-next-btn":
        new_offset = (current_offset or 0) + page_size
        return min(new_offset, max(0, total - 1))
    else:
        # Filter changed — reset to page 0
        return 0


# ---------------------------------------------------------------------------
# Page size selector
# ---------------------------------------------------------------------------
_PAGE_SIZE_IDS = {
    "page-size-1000": 1000,
    "page-size-2000": 2000,
    "page-size-5000": 5000,
    "page-size-10000": 10000,
}


@callback(
    Output("page-size-store", "data"),
    Output("page-size-1000", "active"),
    Output("page-size-2000", "active"),
    Output("page-size-5000", "active"),
    Output("page-size-10000", "active"),
    Input("page-size-1000", "n_clicks"),
    Input("page-size-2000", "n_clicks"),
    Input("page-size-5000", "n_clicks"),
    Input("page-size-10000", "n_clicks"),
    prevent_initial_call=True,
)
def _set_page_size(c1: int, c2: int, c3: int, c4: int) -> tuple[int, bool, bool, bool, bool]:
    triggered = ctx.triggered_id
    size = _PAGE_SIZE_IDS.get(triggered, 1000)
    return size, size == 1000, size == 2000, size == 5000, size == 10000


# Chip management: add term on Enter, remove on × click
@callback(
    Output("search-terms-store", "data"),
    Output("search-input", "value"),
    Input("search-input", "value"),
    Input({"type": "remove-chip", "index": ALL}, "n_clicks"),
    State("search-terms-store", "data"),
    prevent_initial_call=True,
)
def _manage_chips(
    input_val: str | None,
    remove_clicks: list[int | None],
    current_terms: list[str],
) -> tuple[list[str], str]:
    """Add or remove search chips."""
    triggered = ctx.triggered_id

    # Remove chip
    if isinstance(triggered, dict) and triggered.get("type") == "remove-chip":
        idx = triggered["index"]
        terms = [t for i, t in enumerate(current_terms) if i != idx]
        return terms, no_update

    # Add chip (input submitted)
    if input_val and input_val.strip():
        new_term = input_val.strip()
        if new_term not in current_terms:
            current_terms = current_terms + [new_term]
        return current_terms, ""

    return no_update, no_update


# Render chips from store
@callback(
    Output("search-chips", "children"),
    Input("search-terms-store", "data"),
)
def _render_chips(terms: list[str]) -> list:
    """Render search terms as removable chips."""
    if not terms:
        return []

    chip_style = {
        "display": "inline-flex",
        "alignItems": "center",
        "backgroundColor": BOL_PALETTE["teal"],
        "color": "#FFFFFF",
        "borderRadius": "12px",
        "padding": "2px 8px 2px 10px",
        "fontSize": "0.82rem",
        "marginRight": "4px",
        "whiteSpace": "nowrap",
    }
    x_style = {
        "cursor": "pointer",
        "marginLeft": "6px",
        "fontWeight": "bold",
        "fontSize": "0.9rem",
        "lineHeight": "1",
        "opacity": "0.8",
        "border": "none",
        "background": "none",
        "color": "#FFFFFF",
        "padding": "0 2px",
    }

    chips = []
    for i, term in enumerate(terms):
        chips.append(html.Span([
            term,
            html.Button(
                "\u00d7",
                id={"type": "remove-chip", "index": i},
                style=x_style,
                n_clicks=0,
            ),
        ], style=chip_style))
    return chips


@callback(
    Output("filter-chain", "children"),
    Input("explorer-grid", "filterModel"),
    Input("search-terms-store", "data"),
    Input("search-mode", "data"),
    Input("epc-slicer-store", "data"),
    Input("era-slicer-store", "data"),
    Input("floor-slicer-store", "data"),
    Input("wall-slicer-store", "data"),
    Input("type-slicer-store", "data"),
    Input("map-selected-territory", "data"),
    Input("custom-sample-store", "data"),
    Input("full-agg-store", "data"),
    Input("lang-store", "data"),
)
def _update_filter_chain(
    filter_model: dict | None,
    terms: list[str],
    mode: str,
    epc_classes: list[str],
    eras: list[str],
    floors: list[str],
    walls: list[str],
    btypes: list[str],
    map_territory: str | None,
    custom_sample: list[str],
    agg_data: dict | None,
    lang: str | None,
) -> list | str:
    """Compute step-by-step filter chain using DuckDB aggregate data."""
    lang = lang or "lv"
    has_search = bool(terms)
    has_col_filters = bool(filter_model)
    has_custom_sample = bool(custom_sample)
    # Include N/A in the count of "all" options
    all_epc_count = len(EPC_CLASSES_DISPLAY) + 1  # +1 for N/A
    all_era_count = len(ERA_BINS) + 1
    all_floor_count = len(FLOOR_GROUPS) + 1
    all_wall_count = len(WALL_MATERIALS) + 1
    all_type_count = len(BUILDING_TYPES) + 1
    has_epc_filter = bool(epc_classes) and len(epc_classes) < all_epc_count
    has_era_filter = bool(eras) and len(eras) < all_era_count
    has_floor_filter = bool(floors) and len(floors) < all_floor_count
    has_wall_filter = bool(walls) and len(walls) < all_wall_count
    has_type_filter = bool(btypes) and len(btypes) < all_type_count
    has_map_filter = bool(map_territory)

    if not has_search and not has_col_filters and not has_epc_filter and not has_era_filter and not has_floor_filter and not has_wall_filter and not has_type_filter and not has_map_filter and not has_custom_sample:
        return [html.Span(t("filter.no_active", lang), style={
            "fontSize": "0.82rem", "color": BOL_PALETTE["grey"], "fontStyle": "italic",
        })]

    # Get total from DuckDB
    con = _get_duckdb_con()
    total = con.execute("SELECT COUNT(*) FROM buildings").fetchone()[0]
    filtered_total = agg_data.get("total_count", total) if agg_data else total

    # Compute step-by-step reductions using DuckDB
    steps: list[tuple[str, int]] = []
    conditions: list[str] = []
    params: list = []

    def _current_count() -> int:
        if not conditions:
            return total
        q = f"SELECT COUNT(*) FROM buildings WHERE {' AND '.join(conditions)}"
        return con.execute(q, params).fetchone()[0]

    # Custom sample filter (always first)
    if has_custom_sample:
        before = _current_count()
        placeholders = ", ".join("?" for _ in custom_sample)
        conditions.append(f'"KadastraApzimBuilding" IN ({placeholders})')
        params.extend(custom_sample)
        after = _current_count()
        removed = before - after
        if removed > 0:
            steps.append((t("filter.custom_step", lang) + f" ({len(custom_sample)})", removed))

    if has_epc_filter:
        before = _current_count()
        # Build EPC condition
        epc_vals = [c for c in epc_classes if c != "N/A"]
        epc_na = "N/A" in epc_classes
        if epc_vals and epc_na:
            conditions.append(f"(combined_epc_class IN ({','.join('?' for _ in epc_vals)}) OR combined_epc_class IS NULL)")
            params.extend(epc_vals)
        elif epc_vals:
            conditions.append(f"combined_epc_class IN ({','.join('?' for _ in epc_vals)})")
            params.extend(epc_vals)
        elif epc_na:
            conditions.append("combined_epc_class IS NULL")
        after = _current_count()
        removed = before - after
        if removed > 0:
            steps.append((f"{t('filter.epc_step', lang)} = {', '.join(epc_classes)}", removed))

    if has_era_filter:
        before = _current_count()
        era_vals = [e for e in eras if e != "N/A"]
        era_na = "N/A" in eras
        if era_vals and era_na:
            conditions.append(f"(era_bin IN ({','.join('?' for _ in era_vals)}) OR era_bin IS NULL)")
            params.extend(era_vals)
        elif era_vals:
            conditions.append(f"era_bin IN ({','.join('?' for _ in era_vals)})")
            params.extend(era_vals)
        elif era_na:
            conditions.append("era_bin IS NULL")
        after = _current_count()
        removed = before - after
        if removed > 0:
            steps.append((f"{t('filter.era_step', lang)} = {', '.join(eras)}", removed))

    if has_floor_filter:
        before = _current_count()
        floor_vals = [f for f in floors if f != "N/A"]
        floor_na = "N/A" in floors
        range_parts: list[str] = []
        for fv in floor_vals:
            if fv == "10+":
                range_parts.append('"BuildingGroundFloors" >= 10')
            else:
                range_parts.append(f'"BuildingGroundFloors" = {int(fv)}')
        if range_parts and floor_na:
            conditions.append(f"({' OR '.join(range_parts)} OR \"BuildingGroundFloors\" IS NULL OR \"BuildingGroundFloors\" <= 0)")
        elif range_parts:
            conditions.append(f"({' OR '.join(range_parts)})")
        elif floor_na:
            conditions.append('("BuildingGroundFloors" IS NULL OR "BuildingGroundFloors" <= 0)')
        after = _current_count()
        removed = before - after
        if removed > 0:
            steps.append((f"{t('filter.floor_step', lang)} = {', '.join(floors)}", removed))

    if has_wall_filter:
        before = _current_count()
        wall_vals = [w for w in walls if w != "N/A"]
        wall_na = "N/A" in walls
        if wall_vals and wall_na:
            conditions.append(f"(wall_material_grouped IN ({','.join('?' for _ in wall_vals)}) OR wall_material_grouped IS NULL)")
            params.extend(wall_vals)
        elif wall_vals:
            conditions.append(f"wall_material_grouped IN ({','.join('?' for _ in wall_vals)})")
            params.extend(wall_vals)
        elif wall_na:
            conditions.append("wall_material_grouped IS NULL")
        after = _current_count()
        removed = before - after
        if removed > 0:
            steps.append((f"{t('filter.wall_step', lang)} = {', '.join(walls)}", removed))

    if has_type_filter:
        before = _current_count()
        placeholders = ','.join('?' for _ in btypes)
        conditions.append(f"building_type IN ({placeholders})")
        params.extend(btypes)
        after = _current_count()
        removed = before - after
        if removed > 0:
            steps.append((f"{t('filter.type_step', lang)} = {', '.join(btypes)}", removed))

    if has_map_filter:
        before = _current_count()
        if map_territory == "__NA__":
            conditions.append("gis_territory_name IS NULL")
        elif map_territory.startswith("__RIGA__:"):
            neighbourhood = map_territory[9:]
            conditions.append("apkaime_name = ?")
            params.append(neighbourhood)
        elif map_territory.startswith("__DGP__:"):
            neighbourhood = map_territory[8:]
            conditions.append("apkaime_name = ?")
            params.append(neighbourhood)
        else:
            conditions.append("gis_territory_name = ?")
            params.append(map_territory)
        after = _current_count()
        removed = before - after
        if removed > 0:
            if map_territory == "__NA__":
                label = t("filter.no_region", lang)
            elif map_territory.startswith("__RIGA__:"):
                label = map_territory[9:]
            elif map_territory.startswith("__DGP__:"):
                label = map_territory[8:]
            else:
                label = map_territory
            steps.append((f"{t('filter.map_step', lang)} = {label}", removed))

    if has_search:
        terms_str = " & ".join(f'"{term}"' for term in terms) if mode == "all" else " | ".join(f'"{term}"' for term in terms)
        before = _current_count()
        removed = before - filtered_total
        if removed > 0:
            steps.append((f"{t('filter.search_step', lang)} {terms_str}", removed))

    # Build pill-style visual chain
    pill_base: dict = {
        "display": "inline-block",
        "padding": "0.15rem 0.5rem",
        "borderRadius": "10px",
        "fontSize": "0.82rem",
        "marginRight": "0.25rem",
    }
    arrow = html.Span(
        " \u2192 ",
        style={"color": BOL_PALETTE["grey"], "fontSize": "0.9rem", "marginRight": "0.25rem"},
    )

    if not steps:
        return [html.Span(t("filter.no_active", lang), style={
            "fontSize": "0.82rem", "color": BOL_PALETTE["grey"], "fontStyle": "italic",
        })]

    # Starting count
    parts: list = [html.Span(
        f"{total:,} {t('filter.total', lang)}",
        style={
            **pill_base,
            "backgroundColor": BOL_PALETTE["navy"],
            "color": "#FFFFFF",
            "fontWeight": "600",
        },
    )]

    for label, removed in steps:
        parts.append(arrow)
        text = f"{label}: \u2212{removed:,}"
        parts.append(html.Span(
            text,
            style={
                **pill_base,
                "backgroundColor": "#E8E8EE",
                "color": BOL_PALETTE["navy"],
            },
        ))

    parts.append(arrow)
    parts.append(html.Span(
        f"{filtered_total:,} {t('filter.remaining', lang)}",
        style={
            **pill_base,
            "backgroundColor": BOL_PALETTE["teal"],
            "color": "#FFFFFF",
            "fontWeight": "600",
        },
    ))

    return parts


# ---------------------------------------------------------------------------
# EPC Slicer callbacks
# ---------------------------------------------------------------------------
@callback(
    Output("epc-slicer-store", "data"),
    Input({"type": "epc-slicer", "index": ALL}, "n_clicks"),
    Input("epc-slicer-all", "n_clicks"),
    State("epc-slicer-store", "data"),
    State("slicer-mode-store", "data"),
    prevent_initial_call=True,
)
def _toggle_epc_slicer(
    cls_clicks: list[int], all_clicks: int, current: list[str], mode: str,
) -> list[str]:
    """Toggle EPC class selection on/off."""
    triggered = ctx.triggered_id
    if triggered == "epc-slicer-all":
        return list(EPC_CLASSES_DISPLAY) + ["N/A"]
    if isinstance(triggered, dict) and triggered.get("type") == "epc-slicer":
        cls = triggered["index"]
        all_options = list(EPC_CLASSES_DISPLAY) + ["N/A"]
        if mode == "single":
            return [cls]
        if cls in current:
            new = [c for c in current if c != cls]
            return new if new else all_options
        else:
            return current + [cls]
    return current


# Update slicer button styles to reflect selection
@callback(
    Output({"type": "epc-slicer", "index": ALL}, "style"),
    Input("epc-slicer-store", "data"),
)
def _update_slicer_styles(selected: list[str]) -> list[dict]:
    """Dim unselected EPC class buttons (including N/A)."""
    styles = []
    all_buttons = list(EPC_CLASSES_DISPLAY) + ["N/A"]
    for cls in all_buttons:
        active = cls in selected
        bg = EPC_PALETTE.get(cls, "#BDBDBD")
        styles.append({
            "backgroundColor": bg if active else "#E0E0E5",
            "color": "#FFFFFF" if active else "#999",
            "border": f"2px solid {bg}" if active else "2px solid transparent",
            "borderRadius": "16px",
            "padding": "4px 14px" if cls != "N/A" else "4px 12px",
            "marginRight": "4px",
            "fontWeight": "600" if cls != "N/A" else "500",
            "fontSize": "0.85rem",
            "cursor": "pointer",
            "opacity": "1" if active else "0.5",
        })
    return styles


# ---------------------------------------------------------------------------
# Era Slicer callbacks
# ---------------------------------------------------------------------------
@callback(
    Output("era-slicer-store", "data"),
    Input({"type": "era-slicer", "index": ALL}, "n_clicks"),
    Input("era-slicer-all", "n_clicks"),
    State("era-slicer-store", "data"),
    State("slicer-mode-store", "data"),
    prevent_initial_call=True,
)
def _toggle_era_slicer(
    era_clicks: list[int], all_clicks: int, current: list[str], mode: str,
) -> list[str]:
    """Toggle era selection on/off."""
    triggered = ctx.triggered_id
    if triggered == "era-slicer-all":
        return list(ERA_BINS) + ["N/A"]
    if isinstance(triggered, dict) and triggered.get("type") == "era-slicer":
        era = triggered["index"]
        all_options = list(ERA_BINS) + ["N/A"]
        if mode == "single":
            return [era]
        if era in current:
            new = [e for e in current if e != era]
            return new if new else all_options
        else:
            return current + [era]
    return current


@callback(
    Output({"type": "era-slicer", "index": ALL}, "style"),
    Input("era-slicer-store", "data"),
)
def _update_era_styles(selected: list[str]) -> list[dict]:
    styles = []
    all_buttons = list(ERA_BINS) + ["N/A"]
    for era in all_buttons:
        active = era in selected
        bg = BOL_PALETTE["accent1"] if era != "N/A" else "#BDBDBD"
        styles.append({
            "backgroundColor": bg if active else "#E0E0E5",
            "color": "#FFFFFF" if active else "#999",
            "border": f"2px solid {bg}" if active else "2px solid transparent",
            "borderRadius": "16px",
            "padding": "4px 12px",
            "marginRight": "4px",
            "fontWeight": "500",
            "fontSize": "0.8rem",
            "cursor": "pointer",
            "opacity": "1" if active else "0.5",
        })
    return styles


# ---------------------------------------------------------------------------
# Floor Slicer callbacks
# ---------------------------------------------------------------------------
@callback(
    Output("floor-slicer-store", "data"),
    Input({"type": "floor-slicer", "index": ALL}, "n_clicks"),
    Input("floor-slicer-all", "n_clicks"),
    State("floor-slicer-store", "data"),
    State("slicer-mode-store", "data"),
    prevent_initial_call=True,
)
def _toggle_floor_slicer(
    floor_clicks: list[int], all_clicks: int, current: list[str], mode: str,
) -> list[str]:
    triggered = ctx.triggered_id
    if triggered == "floor-slicer-all":
        return list(FLOOR_GROUPS) + ["N/A"]
    if isinstance(triggered, dict) and triggered.get("type") == "floor-slicer":
        fg = triggered["index"]
        all_options = list(FLOOR_GROUPS) + ["N/A"]
        if mode == "single":
            return [fg]
        if fg in current:
            new = [f for f in current if f != fg]
            return new if new else all_options
        else:
            return current + [fg]
    return current


@callback(
    Output({"type": "floor-slicer", "index": ALL}, "style"),
    Input("floor-slicer-store", "data"),
)
def _update_floor_styles(selected: list[str]) -> list[dict]:
    styles = []
    all_buttons = list(FLOOR_GROUPS) + ["N/A"]
    for fg in all_buttons:
        active = fg in selected
        bg = BOL_PALETTE["accent1"] if fg != "N/A" else "#BDBDBD"
        styles.append({
            "backgroundColor": bg if active else "#E0E0E5",
            "color": "#FFFFFF" if active else "#999",
            "border": f"2px solid {bg}" if active else "2px solid transparent",
            "borderRadius": "16px",
            "padding": "4px 12px",
            "marginRight": "4px",
            "fontWeight": "500",
            "fontSize": "0.8rem",
            "cursor": "pointer",
            "opacity": "1" if active else "0.5",
        })
    return styles


# ---------------------------------------------------------------------------
# Wall Material Slicer callbacks
# ---------------------------------------------------------------------------
@callback(
    Output("wall-slicer-store", "data"),
    Input({"type": "wall-slicer", "index": ALL}, "n_clicks"),
    Input("wall-slicer-all", "n_clicks"),
    State("wall-slicer-store", "data"),
    State("slicer-mode-store", "data"),
    prevent_initial_call=True,
)
def _toggle_wall_slicer(
    wall_clicks: list[int], all_clicks: int, current: list[str], mode: str,
) -> list[str]:
    triggered = ctx.triggered_id
    if triggered == "wall-slicer-all":
        return list(WALL_MATERIALS) + ["N/A"]
    if isinstance(triggered, dict) and triggered.get("type") == "wall-slicer":
        mat = triggered["index"]
        all_options = list(WALL_MATERIALS) + ["N/A"]
        if mode == "single":
            return [mat]
        if mat in current:
            new = [m for m in current if m != mat]
            return new if new else all_options
        else:
            return current + [mat]
    return current


@callback(
    Output({"type": "wall-slicer", "index": ALL}, "style"),
    Input("wall-slicer-store", "data"),
)
def _update_wall_styles(selected: list[str]) -> list[dict]:
    styles = []
    all_buttons = list(WALL_MATERIALS) + ["N/A"]
    for mat in all_buttons:
        active = mat in selected
        bg = WALL_COLORS.get(mat, "#BDBDBD")
        styles.append({
            "backgroundColor": bg if active else "#E0E0E5",
            "color": "#FFFFFF" if active else "#999",
            "border": f"2px solid {bg}" if active else "2px solid transparent",
            "borderRadius": "16px",
            "padding": "4px 12px",
            "marginRight": "4px",
            "fontWeight": "500",
            "fontSize": "0.8rem",
            "cursor": "pointer",
            "opacity": "1" if active else "0.5",
        })
    return styles


# ---------------------------------------------------------------------------
# Building Type Slicer callbacks
# ---------------------------------------------------------------------------
@callback(
    Output("type-slicer-store", "data"),
    Input({"type": "type-slicer", "index": ALL}, "n_clicks"),
    Input("type-slicer-all", "n_clicks"),
    State("type-slicer-store", "data"),
    State("slicer-mode-store", "data"),
    prevent_initial_call=True,
)
def _toggle_type_slicer(
    type_clicks: list[int], all_clicks: int, current: list[str], mode: str,
) -> list[str]:
    triggered = ctx.triggered_id
    if triggered == "type-slicer-all":
        return list(BUILDING_TYPES)
    if isinstance(triggered, dict) and triggered.get("type") == "type-slicer":
        bt = triggered["index"]
        all_options = list(BUILDING_TYPES)
        if mode == "single":
            return [bt]
        if bt in current:
            new = [b for b in current if b != bt]
            return new if new else all_options
        else:
            return current + [bt]
    return current


@callback(
    Output({"type": "type-slicer", "index": ALL}, "style"),
    Input("type-slicer-store", "data"),
)
def _update_type_styles(selected: list[str]) -> list[dict]:
    styles = []
    all_buttons = list(BUILDING_TYPES)
    for bt in all_buttons:
        active = bt in selected
        bg = BOL_PALETTE["accent1"]
        styles.append({
            "backgroundColor": bg if active else "#E0E0E5",
            "color": "#FFFFFF" if active else "#999",
            "border": f"2px solid {bg}" if active else "2px solid transparent",
            "borderRadius": "16px",
            "padding": "4px 12px",
            "marginRight": "4px",
            "fontWeight": "500",
            "fontSize": "0.8rem",
            "cursor": "pointer",
            "opacity": "1" if active else "0.5",
        })
    return styles


# ---------------------------------------------------------------------------
# Mini EPC distribution chart (horizontal bars, A on top)
# ---------------------------------------------------------------------------

# Precompute full-sample EPC counts for reference markers
_FULL_EPC_COUNTS: dict[str, int] = {}


def _get_full_epc_counts() -> dict[str, int]:
    if not _FULL_EPC_COUNTS:
        con = _get_duckdb_con()
        rows = con.execute("SELECT combined_epc_class, COUNT(*) FROM buildings WHERE combined_epc_class IS NOT NULL GROUP BY combined_epc_class").fetchall()
        for cls, cnt in rows:
            _FULL_EPC_COUNTS[cls] = int(cnt)
        total = con.execute("SELECT COUNT(*) FROM buildings").fetchone()[0]
        _FULL_EPC_COUNTS["N/A"] = int(total) - sum(_FULL_EPC_COUNTS.values())
    return _FULL_EPC_COUNTS


@callback(
    Output("epc-mini-chart", "children"),
    Output("epc-mini-chart", "style"),
    Input("explorer-grid", "virtualRowData"),
    Input("plot-checklist", "value"),
    Input("chart-ref-toggle", "value"),
    Input("full-agg-store", "data"),
    Input("plots-collapse", "is_open"),
    Input("lang-store", "data"),
)
def _update_mini_chart(virtual_data: list[dict] | None, plots: list[str] | None, show_ref: bool, agg_data: dict | None, panel_open: bool, lang: str | None) -> tuple:
    """Show a minimalistic horizontal bar chart of EPC class distribution."""
    lang = lang or "lv"
    if not panel_open or not plots or "epc_dist" not in plots:
        return html.Div(), _PLOT_STYLE_HIDDEN
    if not virtual_data and not agg_data:
        return html.Div(), _PLOT_STYLE_HIDDEN

    # Use DuckDB aggregates if available (full dataset mode)
    if agg_data and "epc_dist" in agg_data:
        counts = {k: v for k, v in agg_data["epc_dist"].items()}
    else:
        counts = {}
        for row in virtual_data:
            cls = row.get("combined_epc_class", "") or row.get("EnergoefektivKlase", "") or row.get("predicted_epc_class", "")
            if cls in EPC_PALETTE:
                counts[cls] = counts.get(cls, 0) + 1

    full_counts = _get_full_epc_counts()
    total = sum(counts.values()) or 1
    full_max = max(full_counts.values()) if full_counts else 1
    filt_max = max(counts.values()) if counts else 1
    # Use full_max when showing reference, filt_max otherwise
    scale_max = full_max if show_ref else filt_max

    bars = []
    for cls in list(EPC_CLASSES_DISPLAY) + ["N/A"]:
        n = counts.get(cls, 0)
        fn = full_counts.get(cls, 0)
        pct = n / total * 100
        bar_w = n / scale_max * 100 if scale_max > 0 else 0

        if show_ref:
            ref_w = fn / full_max * 100 if full_max > 0 else 0
            inner_w = f"{max(bar_w / ref_w * 100, 0.5):.1f}%" if ref_w > 0 else "0%"
            bar_el = html.Div(
                html.Div(style={
                    "height": "14px", "width": inner_w,
                    "backgroundColor": EPC_PALETTE.get(cls, "#ccc"),
                    "borderRadius": "3px", "transition": "width 0.3s", "minWidth": "2px",
                }),
                style={
                    "height": "14px", "width": f"{max(ref_w, 0.5):.1f}%",
                    "border": f"1px dashed {BOL_PALETTE['grey']}",
                    "borderRadius": "3px", "flexShrink": "0", "flexGrow": "0",
                    "flexBasis": f"{max(ref_w, 0.5):.1f}%",
                },
            )
        else:
            bar_el = html.Div(style={
                "height": "14px", "width": f"{max(bar_w, 0.5):.1f}%",
                "backgroundColor": EPC_PALETTE.get(cls, "#ccc"),
                "borderRadius": "3px", "transition": "width 0.3s", "minWidth": "2px",
            })
        bars.append(
            html.Div([
                html.Span(cls, style={
                    "width": "18px", "fontWeight": "700", "fontSize": "0.75rem",
                    "color": BOL_PALETTE["navy"], "textAlign": "center", "flexShrink": "0",
                }),
                html.Div(bar_el, style={"flex": "1", "minWidth": "0"}),
                html.Span(
                    f" {n:,} ({pct:.1f}%)",
                    style={"fontSize": "0.72rem", "color": BOL_PALETTE["navy"],
                           "marginLeft": "6px", "whiteSpace": "nowrap"},
                ),
            ], style={"display": "flex", "alignItems": "center", "gap": "4px", "marginBottom": "1px"})
        )

    return html.Div([
        html.Div(t("plot.epc_label", lang), style={
            "fontSize": "0.75rem", "fontWeight": "400", "color": BOL_PALETTE["grey"],
            "marginBottom": "2px",
        }),
        html.Div(bars, style={"display": "flex", "flexDirection": "column", "justifyContent": "space-evenly", "flex": "1"}),
    ], style={
        "padding": "6px 10px",
        "backgroundColor": BOL_PALETTE["bg"],
        "borderRadius": "6px",
        "marginBottom": "6px",
        "height": "210px",
        "display": "flex", "flexDirection": "column",
        "overflow": "hidden",
    }), _PLOT_STYLE_VISIBLE


def _build_dist_chart(
    categories: list[str],
    counts: dict[str, int],
    full_counts: dict[str, int],
    color_map: dict[str, str],
    show_ref: bool,
    label: str,
) -> html.Div:
    """Generic horizontal bar chart for categorical distributions."""
    total = sum(counts.values()) or 1
    full_max = max(full_counts.values()) if full_counts else 1
    filt_max = max(counts.values()) if counts else 1
    scale_max = full_max if show_ref else filt_max

    bars = []
    for cat in categories:
        n = counts.get(cat, 0)
        fn = full_counts.get(cat, 0)
        pct = n / total * 100
        bar_w = n / scale_max * 100 if scale_max > 0 else 0
        color = color_map.get(cat, "#999")

        if show_ref and fn > 0:
            ref_w = fn / full_max * 100
            inner_w = f"{max(bar_w / ref_w * 100, 0.5):.1f}%" if ref_w > 0 else "0%"
            bar_el = html.Div(
                html.Div(style={
                    "height": "14px", "width": inner_w,
                    "backgroundColor": color, "borderRadius": "3px",
                    "transition": "width 0.3s", "minWidth": "2px",
                }),
                style={
                    "height": "14px", "width": f"{max(ref_w, 0.5):.1f}%",
                    "border": f"1px dashed {BOL_PALETTE['grey']}",
                    "borderRadius": "3px", "flexShrink": "0", "flexGrow": "0",
                    "flexBasis": f"{max(ref_w, 0.5):.1f}%",
                },
            )
        else:
            bar_el = html.Div(style={
                "height": "14px", "width": f"{max(bar_w, 0.5):.1f}%",
                "backgroundColor": color, "borderRadius": "3px",
                "transition": "width 0.3s", "minWidth": "2px",
            })

        # Truncate long labels
        short = cat[:12] + ".." if len(cat) > 14 else cat
        bars.append(
            html.Div([
                html.Span(short, title=cat, style={
                    "width": "80px", "fontWeight": "600", "fontSize": "0.72rem",
                    "color": BOL_PALETTE["navy"], "flexShrink": "0",
                    "overflow": "hidden", "textOverflow": "ellipsis", "whiteSpace": "nowrap",
                }),
                html.Div(bar_el, style={"flex": "1", "minWidth": "0"}),
                html.Span(
                    f" {n:,} ({pct:.1f}%)",
                    style={"fontSize": "0.72rem", "color": BOL_PALETTE["navy"],
                           "marginLeft": "6px", "whiteSpace": "nowrap"},
                ),
            ], style={"display": "flex", "alignItems": "center", "gap": "4px", "marginBottom": "1px"})
        )

    return html.Div([
        html.Div(label, style={
            "fontSize": "0.75rem", "fontWeight": "400", "color": BOL_PALETTE["grey"],
            "marginBottom": "2px",
        }),
        html.Div(bars, style={"display": "flex", "flexDirection": "column", "justifyContent": "space-evenly", "flex": "1"}),
    ], style={
        "padding": "6px 10px",
        "backgroundColor": BOL_PALETTE["bg"],
        "borderRadius": "6px",
        "marginBottom": "6px",
        "height": "210px",
        "display": "flex", "flexDirection": "column",
        "overflow": "hidden",
    })


# Precompute full-sample era and wall counts
_FULL_ERA_COUNTS: dict[str, int] = {}
_FULL_WALL_COUNTS: dict[str, int] = {}


def _get_full_era_counts() -> dict[str, int]:
    if not _FULL_ERA_COUNTS:
        con = _get_duckdb_con()
        rows = con.execute("SELECT era_bin, COUNT(*) FROM buildings WHERE era_bin IS NOT NULL GROUP BY era_bin").fetchall()
        for era, cnt in rows:
            _FULL_ERA_COUNTS[era] = int(cnt)
        total = con.execute("SELECT COUNT(*) FROM buildings").fetchone()[0]
        _FULL_ERA_COUNTS["N/A"] = int(total) - sum(_FULL_ERA_COUNTS.values())
    return _FULL_ERA_COUNTS


def _get_full_wall_counts() -> dict[str, int]:
    if not _FULL_WALL_COUNTS:
        con = _get_duckdb_con()
        rows = con.execute("SELECT wall_material_grouped, COUNT(*) FROM buildings WHERE wall_material_grouped IS NOT NULL GROUP BY wall_material_grouped").fetchall()
        for mat, cnt in rows:
            _FULL_WALL_COUNTS[mat] = int(cnt)
        total = con.execute("SELECT COUNT(*) FROM buildings").fetchone()[0]
        _FULL_WALL_COUNTS["N/A"] = int(total) - sum(_FULL_WALL_COUNTS.values())
    return _FULL_WALL_COUNTS


# Era color map (use accent1 for all)
ERA_COLORS: dict[str, str] = {era: BOL_PALETTE["accent1"] for era in ERA_BINS}
ERA_COLORS["N/A"] = "#999"


@callback(
    Output("era-mini-chart", "children"),
    Output("era-mini-chart", "style"),
    Input("explorer-grid", "virtualRowData"),
    Input("plot-checklist", "value"),
    Input("chart-ref-toggle", "value"),
    Input("full-agg-store", "data"),
    Input("plots-collapse", "is_open"),
    Input("lang-store", "data"),
)
def _update_era_chart(virtual_data: list[dict] | None, plots: list[str] | None, show_ref: bool, agg_data: dict | None, panel_open: bool, lang: str | None) -> tuple:
    lang = lang or "lv"
    if not panel_open or not plots or "era_dist" not in plots:
        return html.Div(), _PLOT_STYLE_HIDDEN
    if not virtual_data and not agg_data:
        return html.Div(), _PLOT_STYLE_HIDDEN
    if agg_data and "era_dist" in agg_data:
        counts = {k: v for k, v in agg_data["era_dist"].items()}
    else:
        counts = {}
        for row in virtual_data:
            era = row.get("era_bin", "")
            if era in ERA_COLORS:
                counts[era] = counts.get(era, 0) + 1
    return _build_dist_chart(list(ERA_BINS) + ["N/A"], counts, _get_full_era_counts(), ERA_COLORS, show_ref, t("plot.era_label", lang)), _PLOT_STYLE_VISIBLE


@callback(
    Output("wall-mini-chart", "children"),
    Output("wall-mini-chart", "style"),
    Input("explorer-grid", "virtualRowData"),
    Input("plot-checklist", "value"),
    Input("chart-ref-toggle", "value"),
    Input("full-agg-store", "data"),
    Input("plots-collapse", "is_open"),
    Input("lang-store", "data"),
)
def _update_wall_chart(virtual_data: list[dict] | None, plots: list[str] | None, show_ref: bool, agg_data: dict | None, panel_open: bool, lang: str | None) -> tuple:
    lang = lang or "lv"
    if not panel_open or not plots or "wall_dist" not in plots:
        return html.Div(), _PLOT_STYLE_HIDDEN
    if not virtual_data and not agg_data:
        return html.Div(), _PLOT_STYLE_HIDDEN
    if agg_data and "wall_dist" in agg_data:
        counts = {k: v for k, v in agg_data["wall_dist"].items()}
    else:
        counts = {}
        for row in virtual_data:
            mat = row.get("wall_material_grouped", "")
            if mat in WALL_COLORS:
                counts[mat] = counts.get(mat, 0) + 1
    return _build_dist_chart(list(WALL_MATERIALS) + ["N/A"], counts, _get_full_wall_counts(), WALL_COLORS, show_ref, t("plot.wall_label", lang)), _PLOT_STYLE_VISIBLE


# Precompute full-sample floor counts
_FULL_FLOOR_COUNTS: dict[str, int] = {}


def _get_full_floor_counts() -> dict[str, int]:
    if not _FULL_FLOOR_COUNTS:
        con = _get_duckdb_con()
        rows = con.execute(
            'SELECT CASE WHEN "BuildingGroundFloors" IS NULL OR "BuildingGroundFloors" <= 0 THEN \'N/A\' '
            'WHEN "BuildingGroundFloors" >= 10 THEN \'10+\' '
            'ELSE CAST(CAST("BuildingGroundFloors" AS INTEGER) AS VARCHAR) END as fg, COUNT(*) '
            'FROM buildings GROUP BY fg'
        ).fetchall()
        for fg, cnt in rows:
            _FULL_FLOOR_COUNTS[fg] = int(cnt)
    return _FULL_FLOOR_COUNTS


FLOOR_COLORS: dict[str, str] = {fg: BOL_PALETTE["accent1"] for fg in FLOOR_GROUPS}


# Precomputed full-sample primary energy percentile bin counts (20 bins of 5%)
_FULL_PE_COUNTS: list[int] | None = None


def _get_full_pe_counts() -> list[int]:
    global _FULL_PE_COUNTS
    if _FULL_PE_COUNTS is None:
        con = _get_duckdb_con()
        n_bins = 20
        bin_size = 100.0 / n_bins
        _FULL_PE_COUNTS = [0] * n_bins
        rows = con.execute(
            "SELECT primary_energy_pctile FROM buildings WHERE primary_energy_pctile IS NOT NULL"
        ).fetchall()
        for (p,) in rows:
            idx = min(int(float(p) / bin_size), n_bins - 1)
            _FULL_PE_COUNTS[idx] += 1
    return _FULL_PE_COUNTS
FLOOR_COLORS["N/A"] = "#999"


@callback(
    Output("floor-mini-chart", "children"),
    Output("floor-mini-chart", "style"),
    Input("explorer-grid", "virtualRowData"),
    Input("plot-checklist", "value"),
    Input("chart-ref-toggle", "value"),
    Input("full-agg-store", "data"),
    Input("plots-collapse", "is_open"),
    Input("lang-store", "data"),
)
def _update_floor_chart(virtual_data: list[dict] | None, plots: list[str] | None, show_ref: bool, agg_data: dict | None, panel_open: bool, lang: str | None) -> tuple:
    lang = lang or "lv"
    if not panel_open or not plots or "floor_dist" not in plots:
        return html.Div(), _PLOT_STYLE_HIDDEN
    if not virtual_data and not agg_data:
        return html.Div(), _PLOT_STYLE_HIDDEN
    if agg_data and "floor_dist" in agg_data:
        counts = {k: v for k, v in agg_data["floor_dist"].items()}
    else:
        counts = {}
        for row in (virtual_data or []):
            fg = _floor_group(row.get("BuildingGroundFloors"))
            counts[fg] = counts.get(fg, 0) + 1
    return _build_dist_chart(list(FLOOR_GROUPS) + ["N/A"], counts, _get_full_floor_counts(), FLOOR_COLORS, show_ref, t("plot.floor_label", lang)), _PLOT_STYLE_VISIBLE


# ---------------------------------------------------------------------------
# Primary energy percentile distribution chart
# ---------------------------------------------------------------------------


@callback(
    Output("primary-energy-chart", "children"),
    Output("primary-energy-chart", "style"),
    Input("explorer-grid", "virtualRowData"),
    Input("plot-checklist", "value"),
    Input("chart-ref-toggle", "value"),
    Input("full-agg-store", "data"),
    Input("plots-collapse", "is_open"),
    Input("lang-store", "data"),
)
def _update_primary_energy_chart(virtual_data: list[dict] | None, plots: list[str] | None, show_ref: bool, agg_data: dict | None, panel_open: bool, lang: str | None) -> tuple:
    lang = lang or "lv"
    if not panel_open or not plots or "primary_energy_dist" not in plots:
        return html.Div(), _PLOT_STYLE_HIDDEN

    pctile_col = "primary_energy_pctile"

    # Use precomputed aggregation from full filtered dataset (not just visible page)
    n_bins = 20
    bin_size = 100.0 / n_bins
    if agg_data and "pe_pctile_dist" in agg_data:
        bin_counts = list(agg_data["pe_pctile_dist"])
    else:
        # Fallback: count from virtual_data (only current page)
        bin_counts = [0] * n_bins
        for row in (virtual_data or []):
            v = row.get(pctile_col)
            if v is None or v == "":
                continue
            try:
                idx = min(int(float(v) / bin_size), n_bins - 1)
                bin_counts[idx] += 1
            except (ValueError, TypeError):
                continue

    total = sum(bin_counts)
    if total == 0:
        return html.Div(
            "Nav datu" if lang == "lv" else "No data",
            style={"fontSize": "0.8rem", "color": BOL_PALETTE["grey"], "padding": "10px"},
        ), _PLOT_STYLE_VISIBLE

    # Full-sample reference counts
    ref_counts: list[int] | None = None
    ref_total = 0
    if show_ref:
        ref_counts = _get_full_pe_counts()
        ref_total = sum(ref_counts) if ref_counts else 0

    # 95% binomial CI on each bin count: count ± 1.96*sqrt(count*(1-p))
    # where p = count/total
    import math
    ci_half = [0.0] * n_bins
    for i in range(n_bins):
        k = bin_counts[i]
        if total > 1 and k > 0:
            p_hat = k / total
            ci_half[i] = 1.96 * math.sqrt(k * (1 - p_hat))

    max_count = max(bin_counts) if bin_counts else 1
    if ref_counts and show_ref:
        # Scale ref to same total for visual comparison
        scale = total / ref_total if ref_total > 0 else 1
        ref_scaled = [c * scale for c in ref_counts]
        max_count = max(max_count, max(ref_scaled) if ref_scaled else 0)
    else:
        ref_scaled = None

    bars = []
    for i in range(n_bins):
        pct_start = i * bin_size
        pct_end = (i + 1) * bin_size
        count = bin_counts[i]
        bar_w = count / max_count * 100 if max_count > 0 else 0
        color = "#2E7D32" if i < 3 else "#BDBDBD"
        pct_of_total = count / total * 100 if total > 0 else 0

        label = f"{pct_start:.0f}-{pct_end:.0f}%"

        # Build bar area: main bar first, then reference/CI overlaid on top
        bar_children: list = []

        # Main bar (bottom layer)
        bar_children.append(html.Div(style={
            "position": "absolute", "top": "0", "left": "0",
            "height": "12px", "width": f"{max(bar_w, 0.5):.1f}%",
            "backgroundColor": color, "borderRadius": "3px",
            "transition": "width 0.3s", "minWidth": "2px",
        }))

        # Reference bar (dashed outline, on top of main bar so always visible)
        if ref_scaled and show_ref:
            ref_w = ref_scaled[i] / max_count * 100 if max_count > 0 else 0
            bar_children.append(html.Div(style={
                "position": "absolute", "top": "0", "left": "0",
                "height": "12px", "width": f"{max(ref_w, 0.5):.1f}%",
                "border": f"1.5px dashed {BOL_PALETTE['navy']}",
                "borderRadius": "3px", "boxSizing": "border-box",
                "zIndex": "2",
            }))

        # CI whisker (black line on top, always visible)
        if ci_half[i] > 0 and total >= 30:
            ci_lo_w = max(0, (count - ci_half[i]) / max_count * 100)
            ci_hi_w = min(100, (count + ci_half[i]) / max_count * 100)
            bar_children.append(html.Div(style={
                "position": "absolute", "top": "4px",
                "left": f"{ci_lo_w:.1f}%",
                "height": "3px",
                "width": f"{max(ci_hi_w - ci_lo_w, 0.5):.1f}%",
                "backgroundColor": "#333333", "borderRadius": "1px",
                "zIndex": "3",
            }))

        bars.append(
            html.Div([
                html.Span(label, style={
                    "width": "55px", "fontWeight": "600", "fontSize": "0.70rem",
                    "color": BOL_PALETTE["navy"], "flexShrink": "0",
                }),
                html.Div(
                    bar_children,
                    style={"flex": "1", "minWidth": "0", "position": "relative", "height": "12px"},
                ),
                html.Span(
                    f" {count:,} ({pct_of_total:.1f}%)",
                    style={"fontSize": "0.70rem", "color": BOL_PALETTE["navy"],
                           "marginLeft": "4px", "whiteSpace": "nowrap"},
                ),
            ], style={"display": "flex", "alignItems": "center", "gap": "3px", "marginBottom": "0px"})
        )

    # EU taxonomy annotation
    top15_count = sum(bin_counts[:3])
    top15_pct = top15_count / total * 100 if total > 0 else 0
    annotations: list = [html.Div(
        f"{'ES taksonomija top 15%' if lang == 'lv' else 'EU Taxonomy top 15%'}: "
        f"{top15_count:,} ({top15_pct:.1f}%)",
        style={"fontSize": "0.72rem", "color": "#2E7D32", "fontWeight": "600",
               "marginTop": "4px", "borderTop": f"1px solid {BOL_PALETTE['grey']}",
               "paddingTop": "3px"},
    )]

    # CI legend
    if total >= 30:
        ci_note = "95% TI" if lang == "lv" else "95% CI"
        annotations.append(html.Div([
            html.Span("— ", style={"color": "#333333", "fontWeight": "bold"}),
            html.Span(ci_note, style={"fontSize": "0.68rem", "color": BOL_PALETTE["grey"]}),
        ], style={"marginTop": "2px"}))

    title = "Primārās enerģijas procentīļu sadalījums" if lang == "lv" else "Primary Energy Percentile Distribution"

    return html.Div([
        html.Div(title, style={
            "fontSize": "0.75rem", "fontWeight": "400", "color": BOL_PALETTE["grey"],
            "marginBottom": "2px",
        }),
        html.Div(bars, style={"display": "flex", "flexDirection": "column", "justifyContent": "space-evenly", "flex": "1"}),
        *annotations,
    ], style={
        "padding": "6px 10px",
        "backgroundColor": BOL_PALETTE["bg"],
        "borderRadius": "6px",
        "marginBottom": "6px",
        "display": "flex", "flexDirection": "column",
    }), _PLOT_STYLE_VISIBLE


# Precompute full-sample average energy
_FULL_AVG_ENERGY: float | None = None


def _get_full_avg_energy() -> float:
    global _FULL_AVG_ENERGY
    if _FULL_AVG_ENERGY is None:
        try:
            con = _get_duckdb_con()
            result = con.execute("SELECT AVG(combined_heating_kwh) FROM buildings WHERE combined_heating_kwh IS NOT NULL").fetchone()
            _FULL_AVG_ENERGY = float(result[0]) if result and result[0] is not None else 120.0
        except Exception:
            _FULL_AVG_ENERGY = 120.0
    return _FULL_AVG_ENERGY


@callback(
    Output("energy-gauge-chart", "children"),
    Output("energy-gauge-chart", "style"),
    Input("explorer-grid", "virtualRowData"),
    Input("plot-checklist", "value"),
    Input("full-agg-store", "data"),
    Input("plots-collapse", "is_open"),
    Input("lang-store", "data"),
)
def _update_energy_gauge(virtual_data: list[dict] | None, plots: list[str] | None, agg_data: dict | None, panel_open: bool, lang: str | None) -> tuple:
    lang = lang or "lv"
    if not panel_open or not plots or "avg_energy" not in plots:
        return html.Div(), _PLOT_STYLE_HIDDEN
    if not virtual_data and not agg_data:
        return html.Div(), _PLOT_STYLE_HIDDEN

    # Try combined_heating_kwh first, fall back to EnergijaApkurei
    if agg_data and "avg_heating" in agg_data:
        avg = agg_data["avg_heating"]
    else:
        values = [row.get("combined_heating_kwh") or row.get("EnergijaApkurei")
                  for row in (virtual_data or [])
                  if (row.get("combined_heating_kwh") or row.get("EnergijaApkurei")) is not None]
        if not values:
            return html.Div(), _PLOT_STYLE_HIDDEN
        avg = sum(values) / len(values)

    if avg is None:
        return html.Div(
            html.Span(t("gauge.na", lang), style={
                "fontSize": "0.9rem", "color": BOL_PALETTE["grey"], "fontStyle": "italic",
            }),
            style={"display": "flex", "alignItems": "center", "justifyContent": "center", "height": "210px"},
        ), _PLOT_STYLE_VISIBLE

    full_avg = _get_full_avg_energy()

    fig = go.Figure(go.Indicator(
        mode="gauge+number+delta",
        value=avg,
        delta={"reference": full_avg, "valueformat": ".1f", "suffix": " kWh/m\u00b2", "increasing": {"color": "#D84315"}, "decreasing": {"color": "#2E7D32"}},
        number={"suffix": " kWh/m\u00b2", "valueformat": ".1f"},
        title={"text": ""},
        domain={"y": [0, 1]},
        gauge={
            "axis": {"range": [0, 300], "tickwidth": 1},
            "bar": {"color": "rgba(0,0,0,0)"},  # invisible bar — value shown by steps
            "steps": [
                {"range": [0, min(avg, 40)], "color": EPC_PALETTE["A"]},
                {"range": [0, 40] if avg < 40 else [min(avg, 40), min(avg, 60)], "color": EPC_PALETTE["A"] if avg <= 40 else EPC_PALETTE["B"]},
            ],
            "bgcolor": BOL_PALETTE["bg"],
            "threshold": {
                "line": {"color": BOL_PALETTE["navy"], "width": 3},
                "thickness": 0.8,
                "value": full_avg,
            },
        },
    ))

    # Build gauge steps: fill up to avg with saturated color, rest with transparent
    epc_ranges = [(0, 40, "A"), (40, 60, "B"), (60, 80, "C"), (80, 100, "D"), (100, 150, "E"), (150, 300, "F")]
    steps = []
    for lo, hi, cls in epc_ranges:
        hex_color = EPC_PALETTE[cls].lstrip("#")
        r, g, b = int(hex_color[:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16)
        if avg >= hi:
            # Fully filled
            steps.append({"range": [lo, hi], "color": f"rgba({r},{g},{b},0.85)"})
        elif avg > lo:
            # Partially filled
            steps.append({"range": [lo, avg], "color": f"rgba({r},{g},{b},0.85)"})
            steps.append({"range": [avg, hi], "color": f"rgba({r},{g},{b},0.08)"})
        else:
            # Not reached
            steps.append({"range": [lo, hi], "color": f"rgba({r},{g},{b},0.08)"})
    fig.data[0].gauge.steps = steps
    fig.update_layout(
        height=230, margin={"t": 20, "b": 15, "l": 18, "r": 30},
        paper_bgcolor=BOL_PALETTE["bg"], font={"color": BOL_PALETTE["navy"]},
        annotations=[{
            "text": t("gauge.title", lang),
            "x": 0.5, "y": 1.08, "xref": "paper", "yref": "paper",
            "showarrow": False,
            "font": {"size": 12, "color": BOL_PALETTE["grey"]},
        }],
    )
    return dcc.Graph(figure=fig, config={"displayModeBar": False}, style={"height": "210px", "overflow": "hidden"}), _PLOT_STYLE_VISIBLE


# ---------------------------------------------------------------------------
# Detail panel (row click → offcanvas)
# ---------------------------------------------------------------------------

@callback(
    Output("detail-panel", "is_open"),
    Output("detail-panel-content", "children"),
    Input("explorer-grid", "selectedRows"),
    State("lang-store", "data"),
    prevent_initial_call=True,
)
def _show_detail(selected: list[dict] | None, lang: str | None) -> tuple[bool, html.Div]:
    lang = lang or "lv"
    if not selected:
        return False, html.Div()
    row = selected[0]
    rows = []
    for col, val in row.items():
        display = get_display_name(col, lang)
        # EPC class → color badge
        if col in ("EnergoefektivKlase", "EnergoefektivKlase_georiga_pref",
                   "epc_class_cert", "epc_class_georiga", "combined_epc_class",
                   "predicted_epc_class") and val in EPC_PALETTE:
            val_el = html.Span(
                val,
                style={
                    "backgroundColor": EPC_PALETTE[val],
                    "color": "#FFFFFF",
                    "padding": "2px 10px",
                    "borderRadius": "4px",
                    "fontWeight": "700",
                },
            )
        elif isinstance(val, float):
            val_el = f"{val:.1f}"
        else:
            val_el = str(val) if val is not None else "—"
        rows.append(html.Tr([html.Td(display, style={"fontWeight": "600"}), html.Td(val_el)]))
    return True, dbc.Table(
        [html.Tbody(rows)],
        bordered=True,
        size="sm",
        style={"fontSize": "0.85rem"},
    )


# Hide language toggle buttons when detail panel is open (they overlap X button)
@callback(
    Output("lang-toggle-container", "style"),
    Input("detail-panel", "is_open"),
)
def _toggle_lang_buttons(panel_open: bool) -> dict:
    base = {"position": "fixed", "top": "10px", "right": "20px", "zIndex": "9999"}
    if panel_open:
        return {**base, "display": "none"}
    return base


# ---------------------------------------------------------------------------
# CSV export
# ---------------------------------------------------------------------------

# Open download modal
@callback(
    Output("download-modal", "is_open"),
    Input("download-data-btn", "n_clicks"),
    prevent_initial_call=True,
)
def _open_download_modal(_n: int) -> bool:
    return True


# Show/hide CSV separator option
@callback(
    Output("download-sep-container", "style"),
    Input("download-format", "value"),
)
def _toggle_csv_sep(fmt: str) -> dict:
    return {} if fmt == "csv" else {"display": "none"}


# Show/hide custom column picker
@callback(
    Output("download-col-picker-collapse", "is_open"),
    Output("download-custom-cols", "options"),
    Output("download-custom-cols", "value"),
    Input("download-cols-mode", "value"),
    State({"type": "col-display", "block": ALL}, "value"),
    State("lang-store", "data"),
)
def _toggle_download_col_picker(mode: str, block_values: list[list[str]], lang: str | None) -> tuple[bool, list, list]:
    from dash import no_update
    if mode != "custom":
        return False, no_update, no_update
    lang = lang or "lv"
    visible = [c for block in block_values for c in block]
    con = _get_duckdb_con()
    all_cols = [r[0] for r in con.execute(
        "SELECT column_name FROM information_schema.columns WHERE table_name='buildings'"
    ).fetchall()]
    options = [{"label": get_display_name(c, lang), "value": c} for c in all_cols]
    return True, options, visible


# Execute download
@callback(
    Output("download-data-sink", "data"),
    Output("download-modal", "is_open", allow_duplicate=True),
    Output("download-loading-indicator", "children"),
    Input("download-execute-btn", "n_clicks"),
    State("download-format", "value"),
    State("download-separator", "value"),
    State("download-rows", "value"),
    State("download-cols-mode", "value"),
    State({"type": "col-display", "block": ALL}, "value"),
    State("download-custom-cols", "value"),
    State("search-terms-store", "data"),
    State("search-mode", "data"),
    State("epc-slicer-store", "data"),
    State("era-slicer-store", "data"),
    State("floor-slicer-store", "data"),
    State("wall-slicer-store", "data"),
    State("type-slicer-store", "data"),
    State("map-selected-territory", "data"),
    State("custom-sample-store", "data"),
    State("lang-store", "data"),
    prevent_initial_call=True,
)
def _execute_download(
    _n: int, fmt: str, separator: str, row_scope: str, col_mode: str,
    block_values: list[list[str]], custom_cols: list[str] | None,
    terms: list[str], mode: str, epc_classes: list[str],
    eras: list[str], floors: list[str], walls: list[str], btypes: list[str],
    map_territory: str | None,
    custom_sample: list[str], lang: str | None,
) -> tuple:
    import io
    from dash import no_update
    lang = lang or "lv"

    # Determine columns
    if col_mode == "all":
        con = _get_duckdb_con()
        cols = [r[0] for r in con.execute(
            "SELECT column_name FROM information_schema.columns WHERE table_name='buildings'"
        ).fetchall()]
    elif col_mode == "custom" and custom_cols:
        cols = custom_cols
    else:  # visible
        cols = [c for block in block_values for c in block]

    if not cols:
        return no_update, no_update

    # Determine rows
    if row_scope == "all":
        rows, _ = _search_filter_duckdb(
            [], "any", list(EPC_CLASSES_DISPLAY) + ["N/A"],
            list(ERA_BINS) + ["N/A"], list(WALL_MATERIALS) + ["N/A"],
            cols, None, cols, page_offset=0, page_size=999999999,
            floors=list(FLOOR_GROUPS) + ["N/A"],
            btypes=list(BUILDING_TYPES),
        )
    else:
        rows, _ = _search_filter_duckdb(
            terms, mode, epc_classes, eras, walls,
            cols, map_territory, cols, page_offset=0, page_size=999999999,
            custom_sample=custom_sample or [],
            floors=floors or [],
            btypes=btypes or [],
        )

    if not rows:
        return no_update, no_update, ""

    import pandas as pd
    df = pd.DataFrame(rows)
    # Keep only requested columns (in order)
    available = [c for c in cols if c in df.columns]
    df = df[available]

    # Force cadastre numbers to be treated as text in Excel (prevent scientific notation)
    if "KadastraApzimBuilding" in df.columns:
        if fmt == "csv":
            df["KadastraApzimBuilding"] = '="' + df["KadastraApzimBuilding"].astype(str) + '"'

    if fmt == "xlsx":
        buf = io.BytesIO()
        df.to_excel(buf, index=False, engine="openpyxl")
        buf.seek(0)
        return dcc.send_bytes(buf.getvalue(), "epc_data.xlsx"), False, ""
    else:
        # UTF-8 BOM for Excel compatibility with Latvian characters
        csv_bytes = df.to_csv(index=False, sep=separator).encode("utf-8-sig")
        return dcc.send_bytes(csv_bytes, "epc_data.csv"), False, ""


# ---------------------------------------------------------------------------
# "Update Dataset" button: enable when load selections change, commit on click
# ---------------------------------------------------------------------------

@callback(
    Output("update-dataset-btn", "disabled"),
    Output("update-dataset-btn", "color"),
    Input({"type": "col-load", "block": ALL}, "value"),
    Input("loaded-columns-store", "data"),
    Input("dataset-mode-switch", "value"),
    State("dataset-mode-store", "data"),
)
def _enable_update_btn(load_blocks: list[list[str]], current_loaded: list[str],
                       switch_val: bool, committed_mode: str) -> tuple[bool, str]:
    proposed = sorted(c for block in load_blocks for c in block)
    cols_unchanged = proposed == sorted(current_loaded or [])
    mode_unchanged = ("full" if switch_val else "epc") == (committed_mode or "epc")
    unchanged = cols_unchanged and mode_unchanged
    return unchanged, "secondary" if unchanged else "info"


@callback(
    Output("loaded-columns-store", "data"),
    Output("explorer-grid", "filterModel"),
    Output("dataset-mode-store", "data"),
    Input("update-dataset-btn", "n_clicks"),
    State({"type": "col-load", "block": ALL}, "value"),
    State("explorer-grid", "filterModel"),
    State("dataset-mode-switch", "value"),
    prevent_initial_call=True,
)
def _commit_loaded_columns(_n: int, load_blocks: list[list[str]],
                           current_filters: dict | None,
                           full_mode: bool) -> tuple[list[str], dict, str]:
    new_cols = set(c for block in load_blocks for c in block)
    # Remove filters for columns no longer in the loaded set
    clean_filters = {}
    if current_filters:
        for col, filt in current_filters.items():
            if col in new_cols:
                clean_filters[col] = filt
    mode = "full" if full_mode else "epc"
    return list(new_cols), clean_filters, mode


@callback(
    Output("display-cols-container", "children", allow_duplicate=True),
    Input("loaded-columns-store", "data"),
    State("lang-store", "data"),
    prevent_initial_call=True,
)
def _rebuild_display_panel(loaded_cols: list[str], lang: str | None) -> html.Div:
    """Rebuild the Display Columns checklist — show columns available in DuckDB."""
    lang = lang or "lv"
    try:
        con = _get_duckdb_con()
        db_cols = set(r[0] for r in con.execute(
            "SELECT column_name FROM information_schema.columns WHERE table_name='buildings'"
        ).fetchall())
    except Exception:
        db_cols = set(EPC_TABLE_COLUMNS)
    return _build_column_picker(db_cols, picker_type="display", lang=lang)


# ---------------------------------------------------------------------------
# Map Filters — Latvia / Riga / Daugavpils choropleth
# ---------------------------------------------------------------------------
from pathlib import Path as _Path
import numpy as _np

_GEO_ROOT = _Path(__file__).resolve().parents[2] / "data" / "raw" / "geo"
_GEOJSON_PATH = _GEO_ROOT / "Latvia" / "admin_territories" / "latvia_territories_4326.geojson"
_RIGA_GEOJSON_PATH = _GEO_ROOT / "Riga" / "apkaimes_4326.geojson"
_DGP_GEOJSON_PATH = _GEO_ROOT / "Daugavpils" / "apkaimes_daugavpils_4326.geojson"

_LATVIA_GEOJSON: dict | None = None
_RIGA_GEOJSON: dict | None = None
_DGP_GEOJSON: dict | None = None
_DGP_BUILDING_NEIGHBOURHOOD: dict[str, str] | None = None  # cadastre → neighbourhood


def _load_geojson() -> dict:
    global _LATVIA_GEOJSON
    if _LATVIA_GEOJSON is None:
        with open(_GEOJSON_PATH, encoding="utf-8") as f:
            _LATVIA_GEOJSON = json.load(f)
    return _LATVIA_GEOJSON


def _load_riga_geojson() -> dict:
    global _RIGA_GEOJSON
    if _RIGA_GEOJSON is None:
        with open(_RIGA_GEOJSON_PATH, encoding="utf-8") as f:
            _RIGA_GEOJSON = json.load(f)
    return _RIGA_GEOJSON


def _load_dgp_geojson() -> dict:
    global _DGP_GEOJSON
    if _DGP_GEOJSON is None:
        with open(_DGP_GEOJSON_PATH, encoding="utf-8") as f:
            _DGP_GEOJSON = json.load(f)
    return _DGP_GEOJSON


def _load_dgp_building_neighbourhood() -> dict[str, str]:
    """One-time spatial join: assign Daugavpils buildings to neighbourhoods via KOORD_X/Y."""
    global _DGP_BUILDING_NEIGHBOURHOOD
    if _DGP_BUILDING_NEIGHBOURHOOD is not None:
        return _DGP_BUILDING_NEIGHBOURHOOD
    import geopandas as _gpd
    from shapely.geometry import Point as _Point

    # Load neighbourhood polygons in EPSG:3059
    polys = _gpd.read_file(str(_GEO_ROOT / "Daugavpils" / "apkaimes_daugavpils.gpkg"))
    polys = polys.rename(columns={"neighborhood": "NOSAUKUMS"})
    polys = polys.to_crs(epsg=3059) if polys.crs != "EPSG:3059" else polys

    # Load Daugavpils building coords from DuckDB
    con = _get_duckdb_con()
    rows = con.execute(
        "SELECT KadastraApzimBuilding, KOORD_X, KOORD_Y FROM buildings "
        "WHERE gis_territory_name = 'Daugavpils pilsēta' AND KOORD_X IS NOT NULL AND KOORD_Y IS NOT NULL"
    ).fetchall()
    if not rows:
        _DGP_BUILDING_NEIGHBOURHOOD = {}
        return _DGP_BUILDING_NEIGHBOURHOOD

    pts = _gpd.GeoDataFrame(
        {"cadastre": [r[0] for r in rows]},
        geometry=[_Point(r[1], r[2]) for r in rows],
        crs="EPSG:3059",
    )
    joined = _gpd.sjoin(pts, polys[["NOSAUKUMS", "geometry"]], how="left", predicate="within")
    result = {}
    for _, row in joined.iterrows():
        if row.get("NOSAUKUMS") and not (isinstance(row["NOSAUKUMS"], float) and _np.isnan(row["NOSAUKUMS"])):
            result[str(row["cadastre"])] = row["NOSAUKUMS"]
    _DGP_BUILDING_NEIGHBOURHOOD = result
    return _DGP_BUILDING_NEIGHBOURHOOD


# Background color from theme
_BG_COLOR = BOL_PALETTE.get("bg", "#F5F5F5")


@callback(
    Output("map-choropleth", "figure"),
    Input("explorer-grid", "virtualRowData"),
    Input("map-selected-territory", "data"),
    Input("lang-store", "data"),
    Input("map-mode-store", "data"),
    Input("map-size-store", "data"),
)
def _update_map(virtual_data: list[dict] | None, selected: str | None, lang: str | None, map_mode: str | None, map_size: str | None) -> go.Figure:
    lang = lang or "lv"
    _height = 560 if map_size == "large" else 280
    map_mode = map_mode or "latvia"

    if map_mode == "riga":
        sel = selected[9:] if selected and selected.startswith("__RIGA__:") else None
        return _render_city_map(_load_riga_geojson(), sel, lang,
                                territory_filter="Rīgas pilsēta",
                                use_apkaime_col=True,
                                lon_range=[23.9, 24.35], lat_range=[56.85, 57.09],
                                zmin=70, zmax=108, height=_height)
    elif map_mode == "daugavpils":
        sel = selected[8:] if selected and selected.startswith("__DGP__:") else None
        return _render_city_map(_load_dgp_geojson(), sel, lang,
                                territory_filter="Daugavpils pilsēta",
                                use_apkaime_col=True,
                                lon_range=[26.38, 26.68], lat_range=[55.81, 55.95],
                                zmin=None, zmax=None, height=_height)
    else:
        return _render_latvia_map(selected, lang, height=_height)


def _render_latvia_map(selected: str | None, lang: str, height: int = 280) -> go.Figure:
    geojson = _load_geojson()
    names = [f["properties"]["NOSAUKUMS"] for f in geojson["features"]]

    # Compute avg heating energy per territory from FULL (unfiltered) DuckDB dataset
    con = _get_duckdb_con()
    rows = con.execute(
        "SELECT gis_territory_name, AVG(combined_heating_kwh), COUNT(*) "
        "FROM buildings WHERE gis_territory_name IS NOT NULL AND combined_heating_kwh IS NOT NULL "
        "GROUP BY gis_territory_name"
    ).fetchall()
    avg_map: dict[str, float] = {r[0]: float(r[1]) for r in rows}
    count_map: dict[str, int] = {r[0]: int(r[2]) for r in rows}

    # Build per-territory data
    z_vals = []
    hover_texts = []
    line_widths = []
    line_colors = []
    for name in names:
        avg = avg_map.get(name)
        n = count_map.get(name, 0)
        if avg is not None:
            avg_label = "Vid." if lang == "lv" else "Avg"
            hover_texts.append(f"<b>{name}</b><br>{avg_label}: {avg:.1f} kWh/m²/yr<br>n={n}")
        else:
            no_data = "Nav EPC datu" if lang == "lv" else "No EPC data"
            hover_texts.append(f"<b>{name}</b><br>{no_data}")
        z_vals.append(avg)
        line_widths.append(0.5)
        line_colors.append(BOL_PALETTE["navy"])

    # Base choropleth (all regions)
    fig = go.Figure(go.Choropleth(
        geojson=geojson,
        locations=names,
        featureidkey="properties.NOSAUKUMS",
        z=[v if v is not None else 0 for v in z_vals],
        text=hover_texts,
        hoverinfo="text",
        colorscale="RdYlGn_r",
        zmin=68,
        zmax=94,
        marker_line_width=line_widths,
        marker_line_color=line_colors,
        showscale=False,
    ))

    # Overlay selected region in blue
    if selected:
        sel_idx = names.index(selected) if selected in names else None
        if sel_idx is not None:
            fig.add_trace(go.Choropleth(
                geojson=geojson,
                locations=[selected],
                featureidkey="properties.NOSAUKUMS",
                z=[1],
                colorscale=[[0, BOL_PALETTE["teal"]], [1, BOL_PALETTE["teal"]]],
                showscale=False,
                hoverinfo="text",
                text=[hover_texts[sel_idx]],
                marker_line_width=1,
                marker_line_color=BOL_PALETTE["navy"],
            ))

    fig.update_geos(
        visible=False,
        bgcolor=_BG_COLOR,
        projection_type="mercator",
        lonaxis_range=[20.5, 28.5],
        lataxis_range=[55.5, 58.2],
    )
    fig.update_layout(
        margin=dict(t=0, b=0, l=0, r=0),
        paper_bgcolor=_BG_COLOR,
        plot_bgcolor=_BG_COLOR,
        height=height,
        dragmode=False,
        uirevision="map-stable",
    )
    return fig


def _render_city_map(
    geojson: dict, selected: str | None, lang: str,
    territory_filter: str, use_apkaime_col: bool,
    lon_range: list[float], lat_range: list[float],
    zmin: float | None, zmax: float | None,
    height: int = 280,
) -> go.Figure:
    """Render a neighbourhood-level choropleth for a city."""
    names = [f["properties"]["NOSAUKUMS"] for f in geojson["features"]]
    con = _get_duckdb_con()

    if use_apkaime_col:
        # Riga: apkaime_name column exists
        rows = con.execute(
            "SELECT apkaime_name, AVG(combined_heating_kwh), COUNT(*) "
            "FROM buildings WHERE gis_territory_name = ? AND apkaime_name IS NOT NULL "
            "AND combined_heating_kwh IS NOT NULL GROUP BY apkaime_name",
            [territory_filter],
        ).fetchall()
    else:
        # Daugavpils: use spatial join lookup
        dgp_map = _load_dgp_building_neighbourhood()
        if dgp_map:
            cadastres = list(dgp_map.keys())
            placeholders = ", ".join(["?"] * len(cadastres))
            all_rows = con.execute(
                f"SELECT KadastraApzimBuilding, combined_heating_kwh FROM buildings "
                f"WHERE KadastraApzimBuilding IN ({placeholders}) AND combined_heating_kwh IS NOT NULL",
                cadastres,
            ).fetchall()
            # Aggregate by neighbourhood
            from collections import defaultdict
            agg: dict[str, list[float]] = defaultdict(list)
            for cad, kwh in all_rows:
                nb = dgp_map.get(str(cad))
                if nb:
                    agg[nb].append(float(kwh))
            rows = [(nb, sum(vals) / len(vals), len(vals)) for nb, vals in agg.items()]
        else:
            rows = []

    avg_map = {r[0]: float(r[1]) for r in rows}
    count_map = {r[0]: int(r[2]) for r in rows}

    z_vals = []
    hover_texts = []
    for name in names:
        avg = avg_map.get(name)
        n = count_map.get(name, 0)
        if avg is not None:
            avg_label = "Vid." if lang == "lv" else "Avg"
            hover_texts.append(f"<b>{name}</b><br>{avg_label}: {avg:.1f} kWh/m²/yr<br>n={n}")
        else:
            no_data = "Nav EPC datu" if lang == "lv" else "No EPC data"
            hover_texts.append(f"<b>{name}</b><br>{no_data}")
        z_vals.append(avg)

    # Auto-calibrate if zmin/zmax not provided
    valid_z = [v for v in z_vals if v is not None]
    if zmin is None and valid_z:
        zmin = min(valid_z) - 2
    if zmax is None and valid_z:
        zmax = max(valid_z) + 2

    fig = go.Figure(go.Choropleth(
        geojson=geojson,
        locations=names,
        featureidkey="properties.NOSAUKUMS",
        z=[v if v is not None else 0 for v in z_vals],
        text=hover_texts,
        hoverinfo="text",
        colorscale="RdYlGn_r",
        zmin=zmin or 0,
        zmax=zmax or 200,
        marker_line_width=0.5,
        marker_line_color=BOL_PALETTE["navy"],
        showscale=False,
    ))

    if selected and selected in names:
        sel_idx = names.index(selected)
        fig.add_trace(go.Choropleth(
            geojson=geojson,
            locations=[selected],
            featureidkey="properties.NOSAUKUMS",
            z=[1],
            colorscale=[[0, BOL_PALETTE["teal"]], [1, BOL_PALETTE["teal"]]],
            showscale=False,
            hoverinfo="text",
            text=[hover_texts[sel_idx]],
            marker_line_width=1,
            marker_line_color=BOL_PALETTE["navy"],
        ))

    fig.update_geos(
        visible=False,
        bgcolor=_BG_COLOR,
        projection_type="mercator",
        lonaxis_range=lon_range,
        lataxis_range=lat_range,
    )
    fig.update_layout(
        margin=dict(t=0, b=0, l=0, r=0),
        paper_bgcolor=_BG_COLOR,
        plot_bgcolor=_BG_COLOR,
        height=height,
        dragmode=False,
        uirevision="map-stable",
    )
    return fig


@callback(
    Output("map-mode-store", "data"),
    Output("map-selected-territory", "data", allow_duplicate=True),
    Output("map-mode-latvia", "active"),
    Output("map-mode-riga", "active"),
    Output("map-mode-daugavpils", "active"),
    Input("map-mode-latvia", "n_clicks"),
    Input("map-mode-riga", "n_clicks"),
    Input("map-mode-daugavpils", "n_clicks"),
    prevent_initial_call=True,
)
def _set_map_mode(_lv: int | None, _riga: int | None, _dgp: int | None) -> tuple[str, None, bool, bool, bool]:
    trigger = ctx.triggered_id
    if trigger == "map-mode-riga":
        return "riga", None, False, True, False
    elif trigger == "map-mode-daugavpils":
        return "daugavpils", None, False, False, True
    return "latvia", None, True, False, False


@callback(
    Output("map-size-store", "data"),
    Output("map-size-normal", "active"),
    Output("map-size-large", "active"),
    Output("map-choropleth", "style"),
    Input("map-size-normal", "n_clicks"),
    Input("map-size-large", "n_clicks"),
    prevent_initial_call=True,
)
def _set_map_size(_normal: int | None, _large: int | None) -> tuple[str, bool, bool, dict]:
    trigger = ctx.triggered_id
    base = {"marginTop": "0", "marginBottom": "0", "paddingBottom": "0"}
    if trigger == "map-size-large":
        return "large", False, True, {**base, "width": "960px"}
    return "normal", True, False, {**base, "width": "480px"}


@callback(
    Output("map-selected-territory", "data"),
    Input("map-choropleth", "clickData"),
    Input("map-clear-btn", "n_clicks"),
    Input("map-na-btn", "n_clicks"),
    State("map-mode-store", "data"),
    prevent_initial_call=True,
)
def _handle_map_click(click_data: dict | None, _clear: int | None, _na: int | None, map_mode: str | None) -> str | None:
    trigger = ctx.triggered_id
    if trigger == "map-clear-btn":
        return None
    if trigger == "map-na-btn":
        return "__NA__"
    if click_data and "points" in click_data:
        pts = click_data["points"]
        if pts and "location" in pts[0]:
            loc = pts[0]["location"]
            # Encode map mode in the selection value
            if map_mode == "riga":
                return f"__RIGA__:{loc}"
            elif map_mode == "daugavpils":
                return f"__DGP__:{loc}"
            return loc
    return no_update


@callback(
    Output("map-na-btn", "style"),
    Input("map-selected-territory", "data"),
)
def _style_map_na_btn(selected: str | None) -> dict:
    base = {
        "fontSize": "0.82rem", "borderRadius": "12px",
        "padding": "0.25rem 0.6rem",
    }
    if selected == "__NA__":
        base.update({"backgroundColor": BOL_PALETTE["teal"], "color": "#FFFFFF",
                      "borderColor": BOL_PALETTE["teal"]})
    else:
        base.update({"backgroundColor": "transparent", "color": BOL_PALETTE["teal"],
                      "border": f"1px solid {BOL_PALETTE['teal']}"})
    return base


# Integrate map selection into the main filter chain
# The map-selected-territory store needs to feed into _search_filter
# Add it as an additional Input there


# ---------------------------------------------------------------------------
# Language toggle — update all static text when lang-store changes
# ---------------------------------------------------------------------------
@callback(
    Output("explorer-heading", "children"),
    Output("col-selector-toggle", "children", allow_duplicate=True),
    Output("custom-filter-toggle", "children", allow_duplicate=True),
    Output("filter-breakdown-toggle", "children", allow_duplicate=True),
    Output("plots-toggle", "children", allow_duplicate=True),
    Output("maps-toggle", "children", allow_duplicate=True),
    Output("custom-sample-toggle", "children", allow_duplicate=True),
    Output("search-input", "placeholder"),
    Output("download-data-btn", "children"),
    Output("page-prev-btn", "children"),
    Output("page-next-btn", "children"),
    Output("map-na-btn", "children"),
    Output("map-clear-btn", "children"),
    Output("detail-panel", "title"),
    Output("panel-loading-msg", "children"),
    Output("explorer-grid", "columnDefs"),
    # Tooltips
    Output("search-tooltip", "children"),
    Output("search-mode-tooltip", "children"),
    Output("slicer-mode-tooltip", "children"),
    Output("chart-ref-tooltip", "children"),
    Output("epc-chart-tooltip", "children"),
    Output("era-chart-tooltip", "children"),
    Output("wall-chart-tooltip", "children"),
    Output("energy-chart-tooltip", "children"),
    # Labels
    Output("search-match-label", "children"),
    Output("col-select-help", "children"),
    Output("slicer-mode-label-text", "children"),
    Output("epc-slicer-label", "children"),
    Output("era-slicer-label", "children"),
    Output("floor-slicer-label", "children"),
    Output("wall-slicer-label", "children"),
    Output("epc-slicer-all", "children"),
    Output("era-slicer-all", "children"),
    Output("floor-slicer-all", "children"),
    Output("wall-slicer-all", "children"),
    # Wall material button labels
    Output({"type": "wall-slicer", "index": "Wood"}, "children"),
    Output({"type": "wall-slicer", "index": "Brick and stone"}, "children"),
    Output({"type": "wall-slicer", "index": "Concrete"}, "children"),
    Output({"type": "wall-slicer", "index": "Lightweight concrete"}, "children"),
    Output({"type": "wall-slicer", "index": "Metal and glass"}, "children"),
    Output({"type": "wall-slicer", "index": "Other"}, "children"),
    # Type slicer labels
    Output("type-slicer-label", "children"),
    Output("type-slicer-all", "children"),
    Output({"type": "type-slicer", "index": "Residential_Individual"}, "children"),
    Output({"type": "type-slicer", "index": "Residential_Apartment"}, "children"),
    # Plot checklist + ref toggle
    Output("plot-checklist", "options"),
    Output("chart-ref-toggle", "label"),
    # Column picker rebuild
    Output("display-cols-container", "children"),
    # Custom sample panel text
    Output("custom-sample-help", "children"),
    Output("custom-sample-format-link", "children"),
    Output("custom-sample-input", "placeholder"),
    Output("custom-sample-load-btn", "children"),
    Output("custom-sample-add-btn", "children"),
    Output("custom-sample-clear-btn", "children"),
    Output("custom-sample-format-text", "children"),
    # Download modal
    Output("download-modal-title", "children"),
    Output("download-format-label", "children"),
    Output("download-sep-label", "children"),
    Output("download-rows-label", "children"),
    Output("download-cols-label", "children"),
    Output("download-execute-btn", "children"),
    Input("lang-store", "data"),
    State("col-selector-collapse", "is_open"),
    State("custom-filter-collapse", "is_open"),
    State("filter-breakdown-collapse", "is_open"),
    State("plots-collapse", "is_open"),
    State("maps-collapse", "is_open"),
    State("custom-sample-collapse", "is_open"),
    State({"type": "col-display", "block": ALL}, "value"),
    prevent_initial_call=True,
)
def _update_language(
    lang: str | None,
    cols_open: bool, filters_open: bool, breakdown_open: bool, plots_open: bool,
    maps_open: bool, custom_sample_open: bool,
    block_values: list[list[str]],
) -> tuple:
    lang = lang or "lv"
    arrow_cols = "\u25b2" if cols_open else "\u25bc"
    arrow_filt = "\u25b2" if filters_open else "\u25bc"
    arrow_bd = "\u25b2" if breakdown_open else "\u25bc"
    arrow_pl = "\u25b2" if plots_open else "\u25bc"
    arrow_maps = "\u25b2" if maps_open else "\u25bc"
    arrow_cs = "\u25b2" if custom_sample_open else "\u25bc"
    # Rebuild column defs with new language
    visible = [c for block in block_values for c in block]
    all_cols = list(EPC_TABLE_COLUMNS)
    try:
        con = _get_duckdb_con()
        db_cols = set(r[0] for r in con.execute(
            "SELECT column_name FROM information_schema.columns WHERE table_name='buildings'"
        ).fetchall())
        all_cols = [c for c in all_cols if c in db_cols]
    except Exception:
        pass
    col_defs = _make_column_defs(visible, all_cols, lang=lang)

    # Plot checklist options
    plot_opts = [
        {"label": t("plot.checklist.epc", lang), "value": "epc_dist"},
        {"label": t("plot.checklist.era", lang), "value": "era_dist"},
        {"label": t("plot.checklist.wall", lang), "value": "wall_dist"},
        {"label": t("plot.checklist.avg_energy", lang), "value": "avg_energy"},
        {"label": t("plot.checklist.floor", lang), "value": "floor_dist"},
        {"label": t("plot.checklist.primary_energy", lang), "value": "primary_energy_dist"},
    ]

    # Rebuild column picker with new language
    col_picker = _build_column_picker(set(all_cols), picker_type="display", lang=lang, selected=set(visible))

    # Wall material button labels
    wall_labels = [WALL_MATERIAL_DISPLAY[m].get(lang, m) for m in WALL_MATERIALS]

    slicer_all = t("slicer.all", lang)

    return (
        t("nav.explorer", lang),
        f"{t('btn.columns', lang)} {arrow_cols}",
        f"{t('btn.custom_filters', lang)} {arrow_filt}",
        f"{t('btn.filter_breakdown', lang)} {arrow_bd}",
        f"{t('btn.plots', lang)} {arrow_pl}",
        f"{t('btn.maps', lang)} {arrow_maps}",
        f"{t('btn.custom_sample', lang)} {arrow_cs}",
        t("search.placeholder", lang),
        t("btn.download_data", lang),
        t("btn.prev_page", lang),
        t("btn.next_page", lang),
        t("btn.no_region", lang),
        t("btn.clear_map", lang),
        t("detail.building_details", lang),
        t("panel.loading", lang),
        col_defs,
        # Tooltips
        t("tooltip.search", lang),
        t("tooltip.search_mode", lang),
        t("tooltip.slicer_mode", lang),
        t("tooltip.ref_line", lang),
        t("tooltip.epc_chart", lang),
        t("tooltip.era_chart", lang),
        t("tooltip.wall_chart", lang),
        t("tooltip.energy_chart", lang),
        # Labels
        t("search.match_label", lang),
        t("cols.select_help", lang),
        t("slicer.mode_label", lang),
        t("slicer.epc_label", lang),
        t("slicer.era_label", lang),
        t("slicer.floor_label", lang),
        t("slicer.wall_label", lang),
        slicer_all,
        slicer_all,
        slicer_all,
        slicer_all,
        # Wall material buttons
        *wall_labels,
        # Type slicer labels
        t("slicer.type_label", lang),
        slicer_all,
        BUILDING_TYPE_DISPLAY["Residential_Individual"].get(lang, "Individual"),
        BUILDING_TYPE_DISPLAY["Residential_Apartment"].get(lang, "Apartment"),
        # Plot checklist + ref toggle
        plot_opts,
        t("plot.ref_label", lang),
        # Column picker
        col_picker,
        # Custom sample panel
        t("custom.help", lang),
        t("custom.format_help_link", lang),
        t("custom.placeholder", lang),
        t("custom.load_btn", lang),
        t("custom.add_btn", lang),
        t("custom.clear_btn", lang),
        t("custom.format_help", lang),
        # Download modal
        t("download.title", lang),
        t("download.format", lang),
        t("download.separator", lang),
        t("download.rows", lang),
        t("download.cols", lang),
        t("download.btn", lang),
    )
