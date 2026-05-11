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
    _btn_base = {
        "padding": "0.2rem 0.5rem", "fontSize": "0.8rem", "borderRadius": "10px",
        "cursor": "pointer", "marginRight": "4px",
    }

    # --- Feedback modal with Google Form iframe (language-aware) ---
    feedback_modal = dbc.Modal([
        dbc.ModalHeader(dbc.ModalTitle(id="feedback-modal-title")),
        dbc.ModalBody(html.Iframe(
            id="feedback-iframe",
            style={"width": "100%", "height": "650px", "border": "none"},
        )),
    ], id="feedback-modal", size="lg", is_open=False, centered=True)

    # --- Help popover content ---
    help_popover = dbc.Popover(
        dbc.PopoverBody(
            html.Div(id="help-content"),
        ),
        id="help-popover",
        target="help-btn",
        trigger="click",
        placement="bottom-end",
        style={"maxWidth": "360px"},
    )

    lang_toggle = html.Div([
        dcc.Store(id="lang-store", data="lv", storage_type="session"),
        # Feedback button (envelope icon)
        html.Button("✉", id="feedback-btn", n_clicks=0, style={
            **_btn_base, "border": "1px solid #ccc", "backgroundColor": "#fff",
            "fontSize": "0.85rem", "padding": "0.15rem 0.45rem",
        }),
        feedback_modal,
        # Help button (question mark)
        html.Button("?", id="help-btn", n_clicks=0, style={
            **_btn_base, "border": "1px solid #ccc", "backgroundColor": "#fff",
            "fontWeight": "bold", "fontSize": "0.85rem", "padding": "0.15rem 0.5rem",
        }),
        help_popover,
        # Language buttons
        html.Button("LV", id="lang-btn-lv", n_clicks=0, style={
            **_btn_base, "border": "1px solid #008080", "backgroundColor": "#008080", "color": "#fff",
        }),
        html.Button("EN", id="lang-btn-en", n_clicks=0, style={
            **_btn_base, "border": "1px solid #ccc", "backgroundColor": "#eee", "color": "#666",
            "marginRight": "0px",
        }),
    ], id="lang-toggle-container", style={"position": "fixed", "top": "10px", "right": "20px", "zIndex": "9999"})

    from dashboard.pages.building_explorer import layout as explorer_layout
    from dashboard.pages.model_info import layout as model_info_layout
    from dashboard.pages.data_info import layout as data_info_layout

    return html.Div([
        dcc.Location(id="url", refresh=False),
        lang_toggle,
        _sidebar(),
        html.Div([
            html.Div(explorer_layout(), id="page-explorer"),
            html.Div(data_info_layout(), id="page-data-info", style={"display": "none"}),
            html.Div(model_info_layout(), id="page-model-info", style={"display": "none"}),
        ], id="page-content", style=CONTENT_STYLE),
    ])


def register_routing(app: Dash) -> None:
    """Register the URL → page callback and language toggle."""
    from dash import callback, ctx, no_update
    from dashboard.pages.model_info import register_callbacks as register_model_info_callbacks
    from dashboard.pages.data_info import register_callbacks as register_data_info_callbacks

    register_model_info_callbacks(app)
    register_data_info_callbacks(app)

    @app.callback(
        Output("page-explorer", "style"),
        Output("page-data-info", "style"),
        Output("page-model-info", "style"),
        Output("nav-home", "active"),
        Output("nav-data", "active"),
        Output("nav-model-info", "active"),
        Output("help-btn", "style"),
        Output("help-popover", "style"),
        Input("url", "pathname"),
    )
    def _route(pathname: str | None) -> tuple:
        pathname = pathname or "/"
        _btn_help_style = {
            "padding": "0.15rem 0.5rem", "fontSize": "0.85rem", "borderRadius": "10px",
            "cursor": "pointer", "marginRight": "4px",
            "border": "1px solid #ccc", "backgroundColor": "#fff",
            "fontWeight": "bold",
        }
        _show = {"display": "block"}
        _hide = {"display": "none"}
        hidden_help = {**_btn_help_style, "display": "none"}
        if "/model-info" in pathname:
            return _hide, _hide, _show, False, False, True, hidden_help, {"display": "none"}
        if "/data" in pathname:
            return _hide, _show, _hide, False, True, False, hidden_help, {"display": "none"}
        return _show, _hide, _hide, True, False, False, _btn_help_style, {"maxWidth": "360px"}

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

    # --- Feedback modal: open with language-aware Google Form ---
    from dash import State

    _GFORM_LV = "https://docs.google.com/forms/d/e/1FAIpQLSc6wirbH7A4hBD7ALV9FFJv_LjO3EmQE0b5_DFyS0DZq-XSbg/viewform?embedded=true"
    _GFORM_EN = "https://docs.google.com/forms/d/e/1FAIpQLSfADmuDZ9N8g5Y5ENdQKyeQcJ5SYWZZ7jJwz8U6kjynzK9pjA/viewform?embedded=true"

    @app.callback(
        Output("feedback-modal", "is_open"),
        Output("feedback-iframe", "src"),
        Output("feedback-modal-title", "children"),
        Input("feedback-btn", "n_clicks"),
        State("lang-store", "data"),
        State("feedback-modal", "is_open"),
        prevent_initial_call=True,
    )
    def _toggle_feedback_modal(n_clicks, lang, is_open):
        lang = lang or "lv"
        if is_open:
            return False, "", ""
        src = _GFORM_LV if lang == "lv" else _GFORM_EN
        title = "Atsauksme" if lang == "lv" else "Feedback"
        return True, src, title

    # --- Help content (language-aware) ---
    @app.callback(
        Output("help-content", "children"),
        Input("lang-store", "data"),
    )
    def _help_content(lang):
        if lang == "lv":
            return html.Div([
                html.H6("💡 Padomi", style={"marginBottom": "8px"}),
                html.Ul([
                    html.Li(html.Span(["Vērtības ", html.Span("šādā krāsā", style={"color": "#489E9E", "fontWeight": "bold"}), " ir aprēķinātas / novērtētas, nevis no avota datiem."])),
                    html.Li("Meklēšanā var ievadīt vairākus terminus, atdalot ar komatu."),
                    html.Li("Kartē izvēlieties apkaimi, lai filtrētu tabulu."),
                    html.Li("Noklikšķiniet uz tabulas rindas, lai redzētu detalizētu informāciju."),
                    html.Li("Filtru pogas (🔍 Pielāgotie filtri) ļauj filtrēt pēc EPC klases, gadagājuma, u.c."),
                    html.Li("Kolonnu pārvaldniekā izvēlieties, kuras kolonnas rādīt."),
                ], style={"paddingLeft": "18px", "fontSize": "0.78rem", "lineHeight": "1.6"}),
            ])
        return html.Div([
            html.H6("💡 Tips", style={"marginBottom": "8px"}),
            html.Ul([
                html.Li(html.Span(["Values shown in ", html.Span("this color", style={"color": "#489E9E", "fontWeight": "bold"}), " are estimated/derived, not from source data."])),
                html.Li("Enter multiple search terms separated by commas."),
                html.Li("Click a neighbourhood on the map to filter the table."),
                html.Li("Click a table row to see detailed building info."),
                html.Li("Use Custom Filters (🔍) to filter by EPC class, era, etc."),
                html.Li("Use the column manager to choose which columns to display."),
            ], style={"paddingLeft": "18px", "fontSize": "0.78rem", "lineHeight": "1.6"}),
        ])
