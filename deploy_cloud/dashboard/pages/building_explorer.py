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
from dashboard.i18n import t

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


def _build_column_picker(available_cols: set[str], picker_type: str = "display", lang: str = "en") -> html.Div:
    """Build a grouped column picker with labelled blocks.
    
    picker_type: "load" for data loading panel, "display" for table visibility panel.
    """
    blocks = []
    for label, cols in COLUMN_BLOCKS:
        valid_cols = [c for c in cols if c in available_cols]
        if not valid_cols:
            continue
        blocks.append(html.Div([
            html.Div(label, style={
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
                value=[c for c in valid_cols if c in DEFAULT_VISIBLE],
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
            cd["cellStyle"] = {"textAlign": "center"}
            cd["headerClass"] = "ag-header-cell-center"
        # EPC class → small colored badge via JS renderer
        if col in ("EnergoefektivKlase", "EnergoefektivKlase_georiga_pref", "combined_epc_class", "predicted_epc_class"):
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


# ---------------------------------------------------------------------------
# Slicer builders
# ---------------------------------------------------------------------------

def _build_epc_slicer() -> html.Div:
    return html.Div([
        html.Span("EPC Class: ", style={"fontSize": "0.85rem", "color": BOL_PALETTE["grey"], "marginRight": "6px"}),
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
        html.Button("All", id="epc-slicer-all", n_clicks=0, style={
            "backgroundColor": BOL_PALETTE["navy"], "color": "#FFF", "border": "2px solid transparent",
            "borderRadius": "16px", "padding": "4px 14px", "marginLeft": "8px", "fontWeight": "600",
            "fontSize": "0.85rem", "cursor": "pointer",
        }),
    ], style={"marginBottom": "0.5rem", "display": "flex", "alignItems": "center"})


def _build_era_slicer() -> html.Div:
    return html.Div([
        html.Span("Era: ", style={"fontSize": "0.85rem", "color": BOL_PALETTE["grey"], "marginRight": "6px"}),
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
        html.Button("All", id="era-slicer-all", n_clicks=0, style={
            "backgroundColor": BOL_PALETTE["navy"], "color": "#FFF", "border": "2px solid transparent",
            "borderRadius": "16px", "padding": "4px 14px", "marginLeft": "8px", "fontWeight": "600",
            "fontSize": "0.8rem", "cursor": "pointer",
        }),
    ], style={"marginBottom": "0.5rem", "display": "flex", "alignItems": "center", "flexWrap": "wrap"})


def _build_wall_slicer() -> html.Div:
    return html.Div([
        html.Span("Wall: ", style={"fontSize": "0.85rem", "color": BOL_PALETTE["grey"], "marginRight": "6px"}),
        *[html.Button(mat, id={"type": "wall-slicer", "index": mat}, n_clicks=0, style={
            "backgroundColor": WALL_COLORS[mat], "color": "#FFF", "border": "2px solid transparent",
            "borderRadius": "16px", "padding": "4px 12px", "marginRight": "4px", "fontWeight": "500",
            "fontSize": "0.8rem", "cursor": "pointer",
        }) for mat in WALL_MATERIALS],
        html.Button("N/A", id={"type": "wall-slicer", "index": "N/A"}, n_clicks=0, style={
            "backgroundColor": "#BDBDBD", "color": "#FFF", "border": "2px solid transparent",
            "borderRadius": "16px", "padding": "4px 12px", "marginRight": "4px", "fontWeight": "500",
            "fontSize": "0.8rem", "cursor": "pointer",
        }),
        html.Button("All", id="wall-slicer-all", n_clicks=0, style={
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
                        "Type a search term and press Enter to add it as a filter chip. "
                        "Add multiple terms — use the Any/All toggle below to control matching.",
                        target="search-box-container",
                        placement="top",
                    ),
                    # AND/OR toggle
                    html.Div(
                        [
                            html.Span("Match: ", style={"fontSize": "0.8rem", "color": BOL_PALETTE["grey"], "marginRight": "4px"}),
                            dbc.Switch(
                                id="search-mode-switch",
                                label="",
                                value=False,
                                style={"display": "inline-block", "margin": "0 4px"},
                            ),
                            html.Span(id="search-mode-label", children="Any",
                                      style={"fontSize": "0.8rem", "fontWeight": "600", "color": BOL_PALETTE["navy"]}),
                            dbc.Tooltip(
                                "Any: show buildings matching at least one search term. "
                                "All: show only buildings matching every search term.",
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
                    children=f"{len(df):,} buildings shown",
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
        dcc.Store(id="wall-slicer-store", data=list(WALL_MATERIALS) + ["N/A"]),

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
                "Grafiki \u25bc", id="plots-toggle",
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
                        html.Span("Selection mode: ", style={"fontSize": "0.8rem", "color": BOL_PALETTE["grey"]}),
                        dbc.Switch(
                            id="slicer-mode-switch",
                            label="",
                            value=False,
                            style={"display": "inline-block", "margin": "0 4px"},
                        ),
                        html.Span(id="slicer-mode-label", children="Multi-select",
                                  style={"fontSize": "0.8rem", "color": BOL_PALETTE["navy"], "fontWeight": "600"}),
                        dbc.Tooltip(
                            "Multi-select: toggle individual filters on/off. "
                            "Single-select: clicking a filter deselects all others.",
                            target="slicer-mode-switch",
                            placement="right",
                        ),
                    ], style={"marginBottom": "6px", "display": "flex", "alignItems": "center"}),
                    _build_epc_slicer(),
                    _build_era_slicer(),
                    _build_wall_slicer(),
                ], width="auto", style={"padding": "8px 0"}),
                dbc.Col([
                    dcc.Graph(id="map-choropleth", config={"displayModeBar": False},
                              className="mb-0",
                              style={"marginTop": "0", "marginBottom": "0", "paddingBottom": "0",
                                     "width": "480px"}),
                    dcc.Store(id="map-selected-territory", data=None),
                    html.Div([
                        dbc.Button("Nav reģiona (N/A)", id="map-na-btn", size="sm",
                                   color="outline-info", className="mt-1 me-2",
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
                        "When ON, dashed outlines show the full-sample distribution "
                        "for comparison. Turn OFF for a simple bar chart.",
                        target="chart-ref-toggle",
                        placement="right",
                    ),
                ], style={"marginBottom": "4px"}),
                dcc.Loading(
                    html.Div([
                        html.Div(id="epc-mini-chart", style={"flex": "0 1 340px", "minWidth": "260px", "maxWidth": "380px"}),
                        dbc.Tooltip("EPC class distribution of filtered buildings. Dashed = full sample.", target="epc-mini-chart", placement="top"),
                        html.Div(id="era-mini-chart", style={"flex": "0 1 340px", "minWidth": "260px", "maxWidth": "380px"}),
                        dbc.Tooltip("Construction era distribution of filtered buildings.", target="era-mini-chart", placement="top"),
                        html.Div(id="wall-mini-chart", style={"flex": "0 1 340px", "minWidth": "260px", "maxWidth": "380px"}),
                        dbc.Tooltip("Wall material distribution of filtered buildings.", target="wall-mini-chart", placement="top"),
                        html.Div(id="energy-gauge-chart", style={"flex": "0 1 340px", "minWidth": "260px", "maxWidth": "380px"}),
                        dbc.Tooltip("Average heating energy of filtered buildings vs full sample (black marker).", target="energy-gauge-chart", placement="top"),
                    ], style={"display": "flex", "flexWrap": "wrap", "gap": "8px"}),
                    type="circle",
                    color=BOL_PALETTE["teal"],
                ),
            ]),
            id="plots-collapse",
            is_open=False,
        ),

        # Column selector collapse (single panel — display columns)
        dbc.Collapse(
            dbc.Card([
                html.Div("Select columns to show in the table.",
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

        # Below-table row: Export CSV (left) + Pagination (right)
        html.Div([
            dbc.Button("Eksportēt CSV", id="export-csv-btn", color="outline-secondary", size="sm"),
            html.Div([
                dbc.Button("← Iepriekšējie 5 000", id="page-prev-btn", color="outline-secondary",
                           size="sm", disabled=True, style={"marginRight": "8px"}),
                html.Span(id="page-info-label", children="1. lapa",
                          style={"fontSize": "0.82rem", "color": BOL_PALETTE["grey"],
                                 "verticalAlign": "middle", "marginRight": "8px"}),
                dbc.Button("Nākamie 5 000 →", id="page-next-btn", color="outline-secondary",
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
        # Pagination offset
        dcc.Store(id="page-offset-store", data=0),
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
    Output("panel-loading-msg", "style"),
    Input("panel-enable-timer", "n_intervals"),
)
def _enable_panels(n_intervals: int) -> tuple[bool, bool, bool, bool, dict]:
    if n_intervals < 1:
        return True, True, True, True, {"fontSize": "0.82rem", "color": "#6c757d",
                                                "fontStyle": "italic", "marginBottom": "6px"}
    return False, False, False, False, {"display": "none"}


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


# Color Custom Filters button teal when any slicer or map is active
@callback(
    Output("custom-filter-toggle", "color"),
    Input("epc-slicer-store", "data"),
    Input("era-slicer-store", "data"),
    Input("wall-slicer-store", "data"),
    Input("map-selected-territory", "data"),
)
def _color_custom_filter_btn(epc: list[str], eras: list[str], walls: list[str], map_sel: str | None) -> str:
    all_epc = len(EPC_CLASSES_DISPLAY) + 1  # +1 for N/A
    all_eras = len(ERA_BINS) + 1
    all_walls = len(WALL_MATERIALS) + 1
    has_filter = (
        len(epc) < all_epc
        or len(eras) < all_eras
        or len(walls) < all_walls
        or bool(map_sel)
    )
    return "info" if has_filter else "secondary"


# Sync search mode switch → store
@callback(
    Output("search-mode", "data"),
    Output("search-mode-label", "children"),
    Input("search-mode-switch", "value"),
    State("lang-store", "data"),
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
    State("lang-store", "data"),
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
    Output("explorer-grid", "columnDefs"),
    Input({"type": "col-display", "block": ALL}, "value"),
)
def _update_columns(block_values: list[list[str]]) -> list[dict]:
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
    return _make_column_defs(selected, all_cols, dtypes)


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

    # Territory filter
    if map_territory:
        if map_territory == "__NA__":
            conditions.append("gis_territory_name IS NULL")
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
    query = f"SELECT {select_clause} FROM buildings{where_clause} ORDER BY \"KadastraApzimBuilding\" LIMIT 5000{offset_clause}"
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
    Input("wall-slicer-store", "data"),
    Input("initial-load-trigger", "data"),
    Input("map-selected-territory", "data"),
    Input("page-offset-store", "data"),
    State({"type": "col-display", "block": ALL}, "value"),
    State("lang-store", "data"),
)
def _search_filter(
    terms: list[str], mode: str, epc_classes: list[str],
    eras: list[str], walls: list[str], _trigger: bool,
    map_territory: str | None,
    page_offset: int,
    block_values: list[list[str]],
    lang: str | None,
) -> tuple[list[dict], dict | None, bool, bool, str]:
    lang = lang or "lv"
    selected_cols = [c for block in block_values for c in block]
    rows, agg = _search_filter_duckdb(
        terms, mode, epc_classes, eras, walls,
        selected_cols, map_territory, selected_cols,
        page_offset=page_offset or 0,
    )
    # Compute pagination state
    offset = page_offset or 0
    total = agg.get("total_count", 0) if agg else 0
    page_num = offset // 5000 + 1
    total_pages = max(1, (total + 4999) // 5000)
    if total > 5000:
        label = t("page.of", lang).format(page=page_num, total=total_pages)
    else:
        label = t("page.buildings", lang).format(n=f"{total:,}")
    return rows, agg, offset <= 0, offset + 5000 >= total, label


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
    Input("wall-slicer-store", "data"),
    Input("map-selected-territory", "data"),
    State("page-offset-store", "data"),
    State("full-agg-store", "data"),
    prevent_initial_call=True,
)
def _paginate(
    prev_clicks: int | None, next_clicks: int | None,
    _terms: list, _epc: list, _eras: list, _walls: list, _territory: str | None,
    current_offset: int, agg_data: dict | None,
) -> int:
    triggered = ctx.triggered_id
    total = agg_data.get("total_count", 0) if agg_data else 0

    if triggered == "page-prev-btn":
        return max(0, (current_offset or 0) - 5000)
    elif triggered == "page-next-btn":
        new_offset = (current_offset or 0) + 5000
        return min(new_offset, max(0, total - 1))
    else:
        # Filter changed — reset to page 0
        return 0


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
    Input("wall-slicer-store", "data"),
    Input("map-selected-territory", "data"),
    Input("full-agg-store", "data"),
    State("lang-store", "data"),
)
def _update_filter_chain(
    filter_model: dict | None,
    terms: list[str],
    mode: str,
    epc_classes: list[str],
    eras: list[str],
    walls: list[str],
    map_territory: str | None,
    agg_data: dict | None,
    lang: str | None,
) -> list | str:
    """Compute step-by-step filter chain using DuckDB aggregate data."""
    lang = lang or "lv"
    has_search = bool(terms)
    has_col_filters = bool(filter_model)
    # Include N/A in the count of "all" options
    all_epc_count = len(EPC_CLASSES_DISPLAY) + 1  # +1 for N/A
    all_era_count = len(ERA_BINS) + 1
    all_wall_count = len(WALL_MATERIALS) + 1
    has_epc_filter = bool(epc_classes) and len(epc_classes) < all_epc_count
    has_era_filter = bool(eras) and len(eras) < all_era_count
    has_wall_filter = bool(walls) and len(walls) < all_wall_count
    has_map_filter = bool(map_territory)

    if not has_search and not has_col_filters and not has_epc_filter and not has_era_filter and not has_wall_filter and not has_map_filter:
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
            steps.append((f"EPC = {', '.join(epc_classes)}", removed))

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
            steps.append((f"Era = {', '.join(eras)}", removed))

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
            steps.append((f"Wall = {', '.join(walls)}", removed))

    if has_map_filter:
        before = _current_count()
        if map_territory == "__NA__":
            conditions.append("gis_territory_name IS NULL")
        else:
            conditions.append("gis_territory_name = ?")
            params.append(map_territory)
        after = _current_count()
        removed = before - after
        if removed > 0:
            label = "No region (N/A)" if map_territory == "__NA__" else map_territory
            steps.append((f"Map = {label}", removed))

    if has_search:
        terms_str = " & ".join(f'"{t}"' for t in terms) if mode == "all" else " | ".join(f'"{t}"' for t in terms)
        before = _current_count()
        removed = before - filtered_total
        if removed > 0:
            steps.append((f"search {terms_str}", removed))

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
    State("plots-collapse", "is_open"),
    State("lang-store", "data"),
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
    State("plots-collapse", "is_open"),
    State("lang-store", "data"),
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
    State("plots-collapse", "is_open"),
    State("lang-store", "data"),
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
    State("plots-collapse", "is_open"),
    State("lang-store", "data"),
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
    prevent_initial_call=True,
)
def _show_detail(selected: list[dict] | None) -> tuple[bool, html.Div]:
    if not selected:
        return False, html.Div()
    row = selected[0]
    rows = []
    for col, val in row.items():
        display = get_display_name(col)
        # EPC class → color badge
        if col in ("EnergoefektivKlase", "EnergoefektivKlase_georiga_pref") and val in EPC_PALETTE:
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


# ---------------------------------------------------------------------------
# CSV export
# ---------------------------------------------------------------------------

@callback(
    Output("explorer-grid", "csvExportParams"),
    Output("explorer-grid", "exportDataAsCsv"),
    Input("export-csv-btn", "n_clicks"),
    prevent_initial_call=True,
)
def _export_csv(_n: int) -> tuple[dict, bool]:
    return {"columnSeparator": ";"}, True


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
    Output("display-cols-container", "children"),
    Input("loaded-columns-store", "data"),
    State("lang-store", "data"),
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
# Map Filters — Latvia region choropleth
# ---------------------------------------------------------------------------
from pathlib import Path as _Path
import numpy as _np

_GEOJSON_PATH = _Path(__file__).resolve().parents[2] / "data" / "raw" / "geo" / "Latvia" / "admin_territories" / "latvia_territories_4326.geojson"
_LATVIA_GEOJSON: dict | None = None


def _load_geojson() -> dict:
    global _LATVIA_GEOJSON
    if _LATVIA_GEOJSON is None:
        with open(_GEOJSON_PATH, encoding="utf-8") as f:
            _LATVIA_GEOJSON = json.load(f)
    return _LATVIA_GEOJSON


# Background color from theme
_BG_COLOR = BOL_PALETTE.get("bg", "#F5F5F5")


@callback(
    Output("map-choropleth", "figure"),
    Input("explorer-grid", "virtualRowData"),
    Input("map-selected-territory", "data"),
    State("lang-store", "data"),
)
def _update_map(virtual_data: list[dict] | None, selected: str | None, lang: str | None) -> go.Figure:
    lang = lang or "lv"
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
        colorscale="YlOrRd",
        zmin=50,
        zmax=200,
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
        height=280,
        dragmode=False,
        uirevision="map-stable",
    )
    return fig


@callback(
    Output("map-selected-territory", "data"),
    Input("map-choropleth", "clickData"),
    Input("map-clear-btn", "n_clicks"),
    Input("map-na-btn", "n_clicks"),
    prevent_initial_call=True,
)
def _handle_map_click(click_data: dict | None, _clear: int | None, _na: int | None) -> str | None:
    trigger = ctx.triggered_id
    if trigger == "map-clear-btn":
        return None
    if trigger == "map-na-btn":
        return "__NA__"
    if click_data and "points" in click_data:
        pts = click_data["points"]
        if pts and "location" in pts[0]:
            return pts[0]["location"]
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
    Output("search-input", "placeholder"),
    Output("export-csv-btn", "children"),
    Output("page-prev-btn", "children"),
    Output("page-next-btn", "children"),
    Output("map-na-btn", "children"),
    Output("map-clear-btn", "children"),
    Output("detail-panel", "title"),
    Output("panel-loading-msg", "children"),
    Output("explorer-grid", "columnDefs"),
    Input("lang-store", "data"),
    State("col-selector-collapse", "is_open"),
    State("custom-filter-collapse", "is_open"),
    State("filter-breakdown-collapse", "is_open"),
    State("plots-collapse", "is_open"),
    State({"type": "col-display", "block": ALL}, "value"),
    prevent_initial_call=True,
)
def _update_language(
    lang: str | None,
    cols_open: bool, filters_open: bool, breakdown_open: bool, plots_open: bool,
    block_values: list[list[str]],
) -> tuple:
    lang = lang or "lv"
    arrow_cols = "\u25b2" if cols_open else "\u25bc"
    arrow_filt = "\u25b2" if filters_open else "\u25bc"
    arrow_bd = "\u25b2" if breakdown_open else "\u25bc"
    arrow_pl = "\u25b2" if plots_open else "\u25bc"
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
    return (
        t("nav.explorer", lang),
        f"{t('btn.columns', lang)} {arrow_cols}",
        f"{t('btn.custom_filters', lang)} {arrow_filt}",
        f"{t('btn.filter_breakdown', lang)} {arrow_bd}",
        f"{t('btn.plots', lang)} {arrow_pl}",
        t("search.placeholder", lang),
        t("btn.export_csv", lang),
        t("btn.prev_page", lang),
        t("btn.next_page", lang),
        t("btn.no_region", lang),
        t("btn.clear_map", lang),
        t("detail.building_details", lang),
        t("panel.loading", lang),
        col_defs,
    )
