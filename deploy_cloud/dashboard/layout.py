"""Main layout — sidebar + content area with page routing."""

from __future__ import annotations

from dash import Dash, Input, Output, dcc, html
import dash_bootstrap_components as dbc

from dashboard.theme import (
    BOL_PALETTE,
    SIDEBAR_STYLE,
    CONTENT_STYLE,
    NAV_LINK_ACTIVE,
    NAV_LINK_NORMAL,
)

# ---------------------------------------------------------------------------
# Navigation items: (label, href, icon)
# ---------------------------------------------------------------------------
NAV_ITEMS = [
    ("Ēku pārlūks", "/", "🏠"),
    ("Dati", "/data", "📋"),
    ("Modeļa info", "/model-info", "📊"),
]


def _sidebar() -> html.Div:
    """Build the fixed dark sidebar."""
    nav_links = []
    for label, href, icon in NAV_ITEMS:
        # Building Explorer is always the active page (single-page app)
        is_home = href == "/"
        nav_links.append(
            dbc.NavLink(
                f"{icon}  {label}",
                href=href,
                id=f"nav-{href.strip('/') or 'home'}",
                style={
                    "color": "#FFFFFF",
                    "borderRadius": "6px",
                    "marginBottom": "4px",
                    "padding": "0.6rem 1rem",
                },
                active=is_home,
            )
        )

    return html.Div(
        [
            html.H4(
                "EPC pārlūks",
                id="sidebar-title",
                style={
                    "color": BOL_PALETTE["gold"],
                    "fontWeight": "bold",
                    "marginBottom": "0.3rem",
                },
            ),
            html.Hr(style={"borderColor": "rgba(255,255,255,0.2)"}),
            dbc.Nav(nav_links, vertical=True, pills=True),
        ],
        style=SIDEBAR_STYLE,
    )


def build_layout() -> html.Div:
    """Return the top-level app layout."""
    lang_toggle = html.Div([
        dcc.Store(id="lang-store", data="lv", storage_type="session"),
        html.Button("LV", id="lang-btn-lv", n_clicks=0, style={
            "padding": "0.2rem 0.5rem", "fontSize": "0.8rem", "borderRadius": "10px",
            "border": "1px solid #008080", "backgroundColor": "#008080", "color": "#fff",
            "cursor": "pointer", "marginRight": "4px",
        }),
        html.Button("EN", id="lang-btn-en", n_clicks=0, style={
            "padding": "0.2rem 0.5rem", "fontSize": "0.8rem", "borderRadius": "10px",
            "border": "1px solid #ccc", "backgroundColor": "#eee", "color": "#666",
            "cursor": "pointer",
        }),
    ], style={"position": "fixed", "top": "10px", "right": "20px", "zIndex": "9999"})

    return html.Div([
        dcc.Location(id="url", refresh=False),
        lang_toggle,
        _sidebar(),
        html.Div(id="page-content", style=CONTENT_STYLE),
    ])


def register_routing(app: Dash) -> None:
    """Register the URL → page callback and language toggle."""
    from dash import callback, ctx, no_update
    from dashboard.pages.building_explorer import layout as explorer_layout

    @app.callback(Output("page-content", "children"), Input("url", "pathname"))
    def _route(pathname: str | None) -> html.Div:
        # Always show explorer (single-page app; handles Posit Connect sub-paths)
        return explorer_layout()

    @app.callback(
        Output("lang-store", "data"),
        Output("lang-btn-lv", "style"),
        Output("lang-btn-en", "style"),
        Input("lang-btn-lv", "n_clicks"),
        Input("lang-btn-en", "n_clicks"),
        prevent_initial_call=True,
    )
    def _switch_lang(lv_clicks, en_clicks):
        triggered = ctx.triggered_id
        active = {
            "padding": "0.2rem 0.5rem", "fontSize": "0.8rem", "borderRadius": "10px",
            "border": "1px solid #008080", "backgroundColor": "#008080", "color": "#fff",
            "cursor": "pointer", "marginRight": "4px",
        }
        inactive = {
            "padding": "0.2rem 0.5rem", "fontSize": "0.8rem", "borderRadius": "10px",
            "border": "1px solid #ccc", "backgroundColor": "#eee", "color": "#666",
            "cursor": "pointer", "marginRight": "4px",
        }
        if triggered == "lang-btn-en":
            return "en", inactive, {**active, "marginRight": "0px"}
        return "lv", active, {**inactive, "marginRight": "0px"}

    @app.callback(
        Output("sidebar-title", "children"),
        Output("nav-home", "children"),
        Output("nav-data", "children"),
        Output("nav-model-info", "children"),
        Input("lang-store", "data"),
        prevent_initial_call=True,
    )
    def _update_sidebar_lang(lang):
        from dashboard.i18n import t
        return (
            t("app.title", lang),
            f"🏠  {t('nav.explorer', lang)}",
            f"📋  {t('nav.data', lang)}",
            f"📊  {t('nav.model', lang)}",
        )
