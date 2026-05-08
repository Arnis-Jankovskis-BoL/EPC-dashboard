"""Dashboard theme — BOL corporate palette + layout styles."""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure project root is on sys.path for imports
_PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from utils.bol_style import (
    BOL_PALETTE,
    BOL_ACCENT_CYCLE,
    DASHBOARD_EPC_PALETTE as EPC_PALETTE,
    EPC_CLASSES,
    BOL_FONT_BODY,
    BOL_FONT_HEADING,
    bol_plotly_template,
)

# ---------------------------------------------------------------------------
# Layout style dicts (passed as Dash `style=` props)
# ---------------------------------------------------------------------------
SIDEBAR_STYLE: dict[str, str | int] = {
    "position": "fixed",
    "top": 0,
    "left": 0,
    "bottom": 0,
    "width": "250px",
    "padding": "2rem 1.5rem",
    "backgroundColor": BOL_PALETTE["navy"],
    "color": "#FFFFFF",
    "overflowY": "auto",
}

CONTENT_STYLE: dict[str, str | int] = {
    "marginLeft": "250px",
    "padding": "2rem",
    "backgroundColor": BOL_PALETTE["bg"],
    "minHeight": "100vh",
}

CARD_STYLE: dict[str, str] = {
    "backgroundColor": "#FFFFFF",
    "borderRadius": "8px",
    "boxShadow": "0 1px 3px rgba(0,0,0,0.12)",
    "padding": "1.5rem",
    "marginBottom": "1rem",
}

# Active nav link colors
NAV_LINK_ACTIVE = {"backgroundColor": BOL_PALETTE["gold"], "color": BOL_PALETTE["navy"]}
NAV_LINK_NORMAL = {"color": "#FFFFFF"}
