"""
bol_style.py — Bank of Latvia (Latvijas Banka) visual styling utilities.

Provides a unified colour palette and style functions for matplotlib and plotly
charts used in reports and the working paper.

Palette extracted from official PPTX template:
    _additional_data_temp/BoL_chart_template/BoL_chart_template.pptx
    Theme scheme: LB_PTT_2022_2604-3
"""

from __future__ import annotations

from typing import Any

# ---------------------------------------------------------------------------
# BoL Corporate Palette (from PPTX theme1.xml)
# ---------------------------------------------------------------------------
BOL_PALETTE = {
    "navy":         "#282850",   # dk1 — primary dark
    "gold":         "#CBAC88",   # lt1 — warm accent
    "accent1":      "#444780",   # blue-purple
    "accent2":      "#CBAC88",   # gold (same as lt1)
    "teal":         "#489E9E",   # accent3
    "blue":         "#2878A1",   # accent4 — deep blue
    "grey":         "#7F7F85",   # accent5
    "rose":         "#D34F73",   # accent6
    "bg":           "#F0F0F5",   # lt2 — background
    "link":         "#79B9FC",   # hyperlink
    "link_visited": "#246391",   # followed hyperlink
}

# Ordered accent list for chart series (6 colours, good contrast)
BOL_ACCENT_CYCLE = [
    BOL_PALETTE["navy"],
    BOL_PALETTE["teal"],
    BOL_PALETTE["rose"],
    BOL_PALETTE["blue"],
    BOL_PALETTE["gold"],
    BOL_PALETTE["grey"],
]

# ---------------------------------------------------------------------------
# EPC Class Palette (energy semantics: F=worst(red) → A=best(green))
# Matches EPC_CLASS_COLORS in plot_style.py.  P16-S1 palette change.
# ---------------------------------------------------------------------------
EPC_PALETTE = {
    "F": "#d73027",   # red (worst)
    "E": "#f46d43",   # orange
    "D": "#fee08b",   # light amber
    "C": "#d9ef8b",   # yellow-green
    "B": "#a6d96a",   # light green
    "A": "#1a9641",   # dark green (best)
    "A+": "#1B5E20",  # deep green (merged with A for modeling)
}

# Vivid dashboard palette — matches AG-Grid table badges (user preference)
DASHBOARD_EPC_PALETTE = {
    "F": "#B71C1C",   # deep red
    "E": "#D84315",   # burnt orange
    "D": "#EF6C00",   # orange
    "C": "#F9A825",   # amber
    "B": "#558B2F",   # olive green
    "A": "#2E7D32",   # green
    "A+": "#1B5E20",  # deep green
}

# Canonical display order (worst → best for bar charts)
EPC_CLASSES = ["F", "E", "D", "C", "B", "A"]

# Reverse order (best → worst) for contexts where A should come first
EPC_CLASSES_AZ = ["A", "B", "C", "D", "E", "F"]

# ---------------------------------------------------------------------------
# Font defaults
# ---------------------------------------------------------------------------
BOL_FONT_HEADING = "Lora"
BOL_FONT_BODY = "Open Sans"


# ---------------------------------------------------------------------------
# Matplotlib style helper
# ---------------------------------------------------------------------------
def apply_bol_style() -> None:
    """Apply BoL visual defaults to matplotlib's rcParams.

    Call once at the start of a plotting script. Safe to call repeatedly.
    """
    import matplotlib.pyplot as plt

    plt.rcParams.update({
        # Fonts
        "font.family":        "sans-serif",
        "font.sans-serif":    [BOL_FONT_BODY, "DejaVu Sans", "Arial"],
        "font.size":          11,
        "axes.titlesize":     13,
        "axes.labelsize":     11,

        # Colours
        "axes.prop_cycle":    plt.cycler("color", BOL_ACCENT_CYCLE),
        "axes.facecolor":     "#FFFFFF",
        "figure.facecolor":   "#FFFFFF",
        "axes.edgecolor":     BOL_PALETTE["grey"],
        "axes.labelcolor":    BOL_PALETTE["navy"],
        "xtick.color":        BOL_PALETTE["navy"],
        "ytick.color":        BOL_PALETTE["navy"],
        "text.color":         BOL_PALETTE["navy"],

        # Grid
        "axes.grid":          True,
        "grid.alpha":         0.3,
        "grid.color":         BOL_PALETTE["grey"],
        "grid.linestyle":     "--",

        # Legend
        "legend.frameon":     True,
        "legend.framealpha":  0.9,
        "legend.edgecolor":   BOL_PALETTE["grey"],

        # Figure
        "figure.dpi":         150,
        "savefig.dpi":        300,
        "savefig.bbox":       "tight",
    })


# ---------------------------------------------------------------------------
# Plotly style helper
# ---------------------------------------------------------------------------
def bol_plotly_template() -> dict[str, Any]:
    """Return a Plotly layout template dict with BoL styling.

    Usage::

        import plotly.graph_objects as go
        fig = go.Figure(layout=bol_plotly_template())
    """
    return {
        "font": {
            "family": f"{BOL_FONT_BODY}, sans-serif",
            "size": 12,
            "color": BOL_PALETTE["navy"],
        },
        "title": {
            "font": {
                "family": f"{BOL_FONT_HEADING}, serif",
                "size": 16,
                "color": BOL_PALETTE["navy"],
            },
        },
        "colorway": BOL_ACCENT_CYCLE,
        "paper_bgcolor": "#FFFFFF",
        "plot_bgcolor": "#FFFFFF",
        "xaxis": {
            "gridcolor": "#E0E0E5",
            "linecolor": BOL_PALETTE["grey"],
            "title_font_color": BOL_PALETTE["navy"],
        },
        "yaxis": {
            "gridcolor": "#E0E0E5",
            "linecolor": BOL_PALETTE["grey"],
            "title_font_color": BOL_PALETTE["navy"],
        },
    }
