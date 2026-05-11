import os
import sys
from pathlib import Path

_DEPLOY_ROOT = Path(__file__).resolve().parent
if str(_DEPLOY_ROOT) not in sys.path:
    sys.path.insert(0, str(_DEPLOY_ROOT))

from dash import Dash
import dash_bootstrap_components as dbc

from dashboard.layout import build_layout, register_routing

app = Dash(
    __name__,
    assets_folder=str(_DEPLOY_ROOT / "dashboard" / "assets"),
    external_stylesheets=[dbc.themes.BOOTSTRAP],
    suppress_callback_exceptions=True,
)
app.title = "EPC Explorer - Bank of Latvia"

app.layout = build_layout()
register_routing(app)

server = app.server

if __name__ == "__main__":
    app.run(debug=False, port=8050)
