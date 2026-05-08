"""EPC Explorer — Dash application entry point."""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure project root is importable
_PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from dash import Dash
import dash_bootstrap_components as dbc

from dashboard.layout import build_layout, register_routing

app = Dash(
    __name__,
    external_stylesheets=[dbc.themes.BOOTSTRAP],
    suppress_callback_exceptions=True,
)
app.title = "EPC Explorer — Bank of Latvia"

app.layout = build_layout()
register_routing(app)

if __name__ == "__main__":
    app.run(debug=True, port=8050)
