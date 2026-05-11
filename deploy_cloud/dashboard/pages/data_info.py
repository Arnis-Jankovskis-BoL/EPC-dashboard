"""Data Documentation page — per-column cards with stats, sourcing, and distributions."""

from __future__ import annotations

import base64
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from dash import html, dcc, Input, Output, State, callback, no_update, ctx
import dash_bootstrap_components as dbc

from dashboard.theme import BOL_PALETTE

_NAVY = BOL_PALETTE["navy"]
_TEAL = BOL_PALETTE["teal"]
_GOLD = BOL_PALETTE["gold"]
_BG = BOL_PALETTE["bg"]

# ---------------------------------------------------------------------------
# Column metadata: (column_name, display_name_en, display_name_lv,
#                    source, description_en, description_lv, col_type)
# col_type: "numeric" | "categorical" | "binary"
# ---------------------------------------------------------------------------
COLUMNS = [
    ("construction_year", "Construction Year", "Būvniecības gads",
     "EPC + GeoRiga + Cadaster",
     "Year the building was constructed or first put into use. Cleaned from free-text "
     "fields via 13-step cascade (century references, decade ranges, typos). "
     "Strongest predictor of energy performance after postal code.",
     "Ēkas celtniecības vai nodošanas ekspluatācijā gads. Attīrīts no brīvā teksta "
     "laukiem ar 13 soļu kaskādi. Spēcīgākais enerģijas patēriņa prognozētājs pēc pasta indeksa.",
     "numeric"),

    ("postal_code_clean", "Postal Code", "Pasta indekss",
     "EPC + Cadaster",
     "Cleaned postal code (LV-XXXX format). Acts as a spatial proxy capturing local "
     "building stock characteristics, climate zone, and socioeconomic conditions. "
     "Top SHAP feature (mean |SHAP| = 0.25).",
     "Attīrītais pasta indekss (LV-XXXX). Kalpo kā telpiskais aizstājējs, kas uztver "
     "vietējā ēku fonda, klimata zonas un sociālekonomiskos raksturlielumus.",
     "numeric"),

    ("ReferencesPlatiba", "Reference Floor Area (m²)", "Atsauces platība (m²)",
     "EPC certificate",
     "Reference heated floor area per ISO 52000-1:2020. Used for EPC class threshold "
     "determination (3 area bands in post-2022 regulations).",
     "Atsauces apsildāmā stāva platība pēc ISO 52000-1:2020. Izmantota EPC klases "
     "sliekšņu noteikšanai.",
     "numeric"),

    ("ReferencesTilpums", "Reference Volume (m³)", "Atsauces tilpums (m³)",
     "EPC certificate + Cadaster",
     "Reference heated volume. Gap-filled from Cadaster 'Būvtilpums' for buildings "
     "without EPC data. SHAP rank #8.",
     "Atsauces apsildāmais tilpums. Aizpildīts no Kadastra 'Būvtilpums' ēkām bez EPC.",
     "numeric"),

    ("apartment_count", "Apartment Count", "Dzīvokļu skaits",
     "Cadaster",
     "Number of apartments in the building (from Cadaster registry). "
     "Strong predictor — large apartment buildings have different energy profiles.",
     "Dzīvokļu skaits ēkā (no Kadastra reģistra). Spēcīgs prognozētājs.",
     "numeric"),

    ("volume_to_area_ratio", "Volume/Area Ratio", "Tilpuma/platības attiecība",
     "Derived",
     "Ratio of reference volume to reference area. Proxy for average ceiling height "
     "and building compactness. SHAP rank #3.",
     "Atsauces tilpuma un platības attiecība. Aizstājējs vidējam griestu augstumam.",
     "numeric"),

    ("BuildingArea", "Building Total Area (m²)", "Ēkas kopējā platība (m²)",
     "Cadaster",
     "Total building area including non-heated spaces (from State Land Service Cadastre).",
     "Ēkas kopējā platība, ieskaitot neapsildāmās telpas (no VZD Kadastra).",
     "numeric"),

    ("BuildingGroundFloors", "Ground Floors", "Virszemes stāvi",
     "Cadaster",
     "Number of above-ground floors (from Cadastre registry).",
     "Virszemes stāvu skaits (no Kadastra reģistra).",
     "numeric"),

    ("Sienas (vertikālā konstrukcija)", "Wall Material", "Sienu materiāls",
     "EPC certificate",
     "Wall construction material category (e.g., brick, panel, wood). "
     "Categorical feature — Soviet-era panel buildings have distinctive energy profiles.",
     "Sienu konstrukcijas materiāla kategorija. Padomju paneļu ēkām raksturīgi enerģijas profili.",
     "categorical"),

    ("wall_material_grouped", "Wall Material (Grouped)", "Sienu materiāls (grupēts)",
     "Derived from EPC",
     "Grouped wall material into major categories: brick, panel, wood, gas silicate, other.",
     "Grupēts sienu materiāls galvenajās kategorijās.",
     "categorical"),

    ("Jumta nesošā konstrukcija", "Roof Structure", "Jumta nesošā konstrukcija",
     "EPC certificate",
     "Roof load-bearing structure type (e.g., reinforced concrete, wood).",
     "Jumta nesošās konstrukcijas tips.",
     "categorical"),

    ("era_bin", "Construction Era", "Celtniecības ēra",
     "Derived from construction_year",
     "Regulation-based era bins: Pre-1945, 1946-1960, 1961-1990, 1991-2002, "
     "2003-2014, 2015-2020, 2021+. Reflects actual Latvian building regulation periods.",
     "Regulējuma ēras: pirms 1945, 1946-1960, 1961-1990, 1991-2002, 2003-2014, "
     "2015-2020, 2021+.",
     "categorical"),

    ("building_type", "Building Type", "Ēkas tips",
     "Derived from BuildingUseKindId",
     "Residential_Individual (houses) or Residential_Apartment (multi-apartment buildings).",
     "Residential_Individual (mājas) vai Residential_Apartment (daudzdzīvokļu ēkas).",
     "categorical"),

    ("renovation_dummy", "Renovation Flag", "Renovācijas pazīme",
     "EPC + ALTUM",
     "Binary: 1 if the building has a recorded renovation year, 0 otherwise.",
     "Binārā: 1 ja ēkai ir reģistrēts renovācijas gads, 0 citādi.",
     "binary"),

    ("district_heating_flag", "District Heating", "Centralizētā apkure",
     "EPC + Cadaster",
     "Binary: 1 if connected to district heating network, 0 for individual heating.",
     "Binārā: 1 ja pieslēgta centralizētajai apkurei.",
     "binary"),

    ("elem_year_ceiling", "Ceiling Element Year", "Griesti — elementa gads",
     "Cadaster",
     "Year of the ceiling/floor slab element (from Cadastre element data). "
     "Partial renovation indicator — buildings with newer ceilings may have been renovated.",
     "Griestu/pārseguma elementa gads (no Kadastra). Daļējas renovācijas indikators.",
     "numeric"),

    ("elem_year_roof_covering", "Roof Covering Year", "Jumta segums — elementa gads",
     "Cadaster",
     "Year of the roof covering element. Indicates potential roof renovation.",
     "Jumta seguma elementa gads. Norāda iespējamu jumta renovāciju.",
     "numeric"),

    ("wwr_archetype", "Window-Wall Ratio Archetype", "Logu-sienu attiecības arhetips",
     "Derived",
     "Estimated window-to-wall ratio archetype based on building era and type. "
     "Proxy for thermal envelope quality. SHAP rank #7.",
     "Aplēstais logu-sienu attiecības arhetips pēc ēras un tipa.",
     "numeric"),

    ("depreciation_group", "Depreciation Group", "Nolietojuma grupa",
     "Cadaster",
     "Building condition group V1-V5 (Very good to Critical). "
     "Based on Cabinet Regulation No. 116, Annex 3.",
     "Ēkas stāvokļa grupa V1-V5 (Ļoti labs līdz Kritisks).",
     "categorical"),

    ("csp_income_eur", "Territory Income (EUR)", "Teritorijas ienākumi (EUR)",
     "CSP (MIV020)",
     "Average net monthly income in the building's administrative territory. "
     "Higher income areas tend to have better-maintained, more energy-efficient buildings.",
     "Vidējie neto mēneša ienākumi ēkas administratīvajā teritorijā.",
     "numeric"),

    ("csp_density_per_km2", "Population Density", "Iedzīvotāju blīvums",
     "CSP (IRD062)",
     "Population density (people/km²) in the building's territory. "
     "Urban areas show different energy profiles than rural ones.",
     "Iedzīvotāju blīvums (cilv./km²) ēkas teritorijā.",
     "numeric"),
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_data() -> pd.DataFrame:
    """Load model_tree_ready.parquet once."""
    path = Path("data/interim/model_tree_ready.parquet")
    if not path.exists():
        return pd.DataFrame()
    return pd.read_parquet(path)


def _make_histogram(series: pd.Series, name: str) -> go.Figure:
    """Create a Plotly histogram for a numeric column."""
    clean = series.dropna()
    if len(clean) == 0:
        return go.Figure()

    fig = go.Figure()
    fig.add_trace(go.Histogram(
        x=clean, nbinsx=50,
        marker_color=_NAVY, marker_line_color="white", marker_line_width=0.5,
        opacity=0.85,
    ))
    fig.update_layout(
        height=250, margin=dict(l=40, r=20, t=30, b=40),
        plot_bgcolor="white", paper_bgcolor="white",
        xaxis_title=name, yaxis_title="Count",
        font=dict(size=11),
    )
    return fig


def _make_bar_chart(series: pd.Series, name: str) -> go.Figure:
    """Create a Plotly bar chart for a categorical column."""
    counts = series.dropna().value_counts().head(15)
    if len(counts) == 0:
        return go.Figure()

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=counts.index.astype(str), y=counts.values,
        marker_color=_NAVY, marker_line_color="white", marker_line_width=0.5,
        opacity=0.85,
    ))
    fig.update_layout(
        height=250, margin=dict(l=40, r=20, t=30, b=60),
        plot_bgcolor="white", paper_bgcolor="white",
        xaxis_title=name, yaxis_title="Count",
        xaxis_tickangle=-45,
        font=dict(size=11),
    )
    return fig


def _stat_row(label: str, value: str) -> html.Tr:
    return html.Tr([
        html.Td(label, style={"fontWeight": "600", "paddingRight": "12px",
                               "fontSize": "0.82rem", "color": "#555"}),
        html.Td(value, style={"fontSize": "0.82rem"}),
    ])


def _column_card(col_name: str, display_en: str, display_lv: str,
                 source: str, desc_en: str, desc_lv: str, col_type: str,
                 series: pd.Series, lang: str) -> html.Div:
    """Build a single column documentation card."""
    display = display_lv if lang == "lv" else display_en
    desc = desc_lv if lang == "lv" else desc_en

    n_total = len(series)
    n_na = int(series.isna().sum())
    pct_na = 100 * n_na / n_total if n_total > 0 else 0

    stats_rows = [
        _stat_row("Source" if lang == "en" else "Avots", source),
        _stat_row("Type" if lang == "en" else "Datu tips",
                  {"numeric": "Numeric", "categorical": "Categorical", "binary": "Binary"}.get(col_type, col_type)),
        _stat_row("N" if lang == "en" else "Ieraksti", f"{n_total:,}"),
        _stat_row("NA" if lang == "en" else "Trūkst", f"{n_na:,} ({pct_na:.1f}%)"),
    ]

    if col_type == "numeric":
        clean = pd.to_numeric(series, errors="coerce").dropna()
        if len(clean) > 0:
            stats_rows.extend([
                _stat_row("Mean" if lang == "en" else "Vidējais", f"{clean.mean():.1f}"),
                _stat_row("Median" if lang == "en" else "Mediāna", f"{clean.median():.1f}"),
                _stat_row("Std" if lang == "en" else "Std", f"{clean.std():.1f}"),
                _stat_row("Min", f"{clean.min():.1f}"),
                _stat_row("Max", f"{clean.max():.1f}"),
            ])
        fig = _make_histogram(clean, display)
    elif col_type == "binary":
        counts = series.dropna().value_counts()
        for val, cnt in counts.items():
            stats_rows.append(_stat_row(str(val), f"{cnt:,} ({100*cnt/n_total:.1f}%)"))
        fig = _make_bar_chart(series.dropna().astype(str), display)
    else:
        n_unique = series.nunique()
        stats_rows.append(_stat_row("Unique" if lang == "en" else "Unikāli", f"{n_unique:,}"))
        top3 = series.dropna().value_counts().head(3)
        for val, cnt in top3.items():
            stats_rows.append(_stat_row(str(val), f"{cnt:,}"))
        fig = _make_bar_chart(series, display)

    return html.Div([
        html.H5(display, style={"color": _NAVY, "marginBottom": "6px", "fontSize": "1rem"}),
        html.P(desc, style={"fontSize": "0.82rem", "color": "#555", "marginBottom": "8px"}),
        html.Table(stats_rows, style={"marginBottom": "10px"}),
        dcc.Graph(figure=fig, config={"displayModeBar": False},
                  style={"marginBottom": "0px"}),
    ], style={
        "backgroundColor": "white", "borderRadius": "8px", "padding": "16px",
        "marginBottom": "16px", "boxShadow": "0 1px 3px rgba(0,0,0,0.08)",
        "border": f"1px solid {BOL_PALETTE.get('grey', '#ddd')}",
    })


# ---------------------------------------------------------------------------
# Layout
# ---------------------------------------------------------------------------

def layout() -> html.Div:
    """Return the Data Documentation page layout."""
    return html.Div([
        dcc.Store(id="data-info-loaded", data=False),
        html.Div(id="data-info-content", style={"padding": "24px", "maxWidth": "900px"}),
    ])


def register_callbacks(app):
    """Register data info page callbacks."""

    @app.callback(
        Output("data-info-content", "children"),
        Input("data-info-loaded", "data"),
        Input("lang-store", "data"),
    )
    def _render_data_info(loaded, lang):
        lang = lang or "lv"

        # Load data
        df = _load_data()
        if df.empty:
            return html.P("Data not available." if lang == "en" else "Dati nav pieejami.")

        title = "Datu dokumentācija" if lang == "lv" else "Data Documentation"
        subtitle = ("Galveno pazīmju apraksts, avoti un sadalījumi." if lang == "lv"
                     else "Key feature descriptions, sources, and distributions.")

        cards = []
        for col_name, disp_en, disp_lv, source, desc_en, desc_lv, ctype in COLUMNS:
            if col_name not in df.columns:
                continue
            cards.append(
                _column_card(col_name, disp_en, disp_lv, source, desc_en, desc_lv,
                             ctype, df[col_name], lang)
            )

        return html.Div([
            html.H3(title, style={"color": _NAVY, "marginBottom": "4px"}),
            html.P(subtitle, style={"fontSize": "0.9rem", "color": "#666", "marginBottom": "20px"}),
            html.Div(cards),
        ])
