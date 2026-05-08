import os
import sys
from pathlib import Path

_DEPLOY_ROOT = Path(__file__).resolve().parent
if str(_DEPLOY_ROOT) not in sys.path:
    sys.path.insert(0, str(_DEPLOY_ROOT))

from dash import Dash, html, dcc, Input, Output, State, callback, no_update
import dash_bootstrap_components as dbc

from dashboard.layout import build_layout, register_routing

app = Dash(
    __name__,
    assets_folder=str(_DEPLOY_ROOT / "dashboard" / "assets"),
    external_stylesheets=[dbc.themes.BOOTSTRAP],
    suppress_callback_exceptions=True,
)
app.title = "EPC Explorer - Bank of Latvia"

# Password-protected layout for cloud deployment
_PASSWORD = "esg2026"

app.layout = html.Div([
    dcc.Store(id="auth-store", data=False, storage_type="session"),
    html.Div(id="app-container"),
])


@callback(
    Output("app-container", "children"),
    Input("auth-store", "data"),
)
def _render_page(authenticated: bool):
    if authenticated:
        return build_layout()
    return html.Div([
        html.Div([
            html.H3("EPC Building Explorer", style={
                "color": "#003366", "marginBottom": "1rem",
            }),
            html.P("Loading dashboard resources...", style={
                "color": "#666", "marginBottom": "1.5rem",
            }),
            dbc.Progress(
                value=100, striped=True, animated=True,
                style={"marginBottom": "1.5rem", "height": "8px"},
            ),
            html.Hr(),
            html.P("Please enter access code to continue:", style={
                "fontWeight": "600", "marginBottom": "0.5rem",
            }),
            dbc.Input(
                id="password-input", type="password",
                placeholder="Access code",
                style={"maxWidth": "250px", "marginBottom": "0.75rem"},
            ),
            dbc.Button("Enter", id="password-submit", color="primary", size="sm"),
            html.Div(id="password-error", style={"color": "red", "marginTop": "0.5rem", "fontSize": "0.85rem"}),
        ], style={
            "maxWidth": "400px", "margin": "15vh auto", "padding": "2rem",
            "textAlign": "center", "border": "1px solid #ddd", "borderRadius": "8px",
            "backgroundColor": "#fafafa",
        }),
    ])


@callback(
    Output("auth-store", "data"),
    Output("password-error", "children"),
    Input("password-submit", "n_clicks"),
    State("password-input", "value"),
    prevent_initial_call=True,
)
def _check_password(n_clicks, password):
    if password == _PASSWORD:
        return True, ""
    return False, "Incorrect access code."


register_routing(app)
server = app.server

if __name__ == "__main__":
    app.run(debug=False, port=8050)
