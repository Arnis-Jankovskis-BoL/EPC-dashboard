"""Model Info page — tabbed display of research findings, plots, and tables."""

from __future__ import annotations

import base64
from pathlib import Path

from dash import html, dcc, Input, Output, callback
import dash_bootstrap_components as dbc

from dashboard.theme import BOL_PALETTE, CARD_STYLE
from dashboard.i18n import t

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
_PLOTS = Path("output/plots")
_TABLES = Path("output/tables")

_NAVY = BOL_PALETTE["navy"]
_GREY = "#C0C0C8"
_WHITE = "#FFFFFF"
_BG = BOL_PALETTE["bg"]

# Tab definitions: (id, en_label, lv_label)
TABS = [
    ("overview",    "Overview",          "Pārskats"),
    ("literature",  "Literature",        "Literatūra"),
    ("data",        "Data & Features",   "Dati un pazīmes"),
    ("performance", "Model Performance", "Modeļa veiktspēja"),
    ("stock",       "Housing Stock",     "Ēku fonds"),
    ("maps",        "Maps",              "Kartes"),
]


def _img_src(filename: str) -> str | None:
    """Return base64 data URI for a PNG plot, or None if missing."""
    p = _PLOTS / filename
    if not p.exists():
        return None
    data = p.read_bytes()
    b64 = base64.b64encode(data).decode()
    return f"data:image/png;base64,{b64}"


def _plot_card(filename: str, caption_en: str, caption_lv: str, lang: str) -> html.Div:
    """Render a plot image inside a card with caption."""
    src = _img_src(filename)
    if src is None:
        return html.Div()
    caption = caption_lv if lang == "lv" else caption_en
    return html.Div([
        html.Img(src=src, style={
            "width": "100%", "maxWidth": "800px",
            "borderRadius": "6px", "marginBottom": "6px",
        }),
        html.P(caption, style={
            "fontSize": "0.82rem", "color": BOL_PALETTE["grey"],
            "fontStyle": "italic", "textAlign": "center",
        }),
    ], style={**CARD_STYLE, "textAlign": "center", "padding": "1rem"})


def _read_table(filename: str) -> str | None:
    """Read a text/CSV/MD table file."""
    p = _TABLES / filename
    if not p.exists():
        return None
    return p.read_text(encoding="utf-8")


def _section(title, children: list) -> html.Div:
    """Wrap children in a titled section. Title can be str or Dash component."""
    return html.Div([
        html.H5(title, style={
            "color": _NAVY, "fontWeight": "bold",
            "borderBottom": f"2px solid {BOL_PALETTE['gold']}",
            "paddingBottom": "6px", "marginBottom": "12px",
        }),
        *children,
    ], style={"marginBottom": "24px"})


# ---------------------------------------------------------------------------
# Tab content builders
# ---------------------------------------------------------------------------

_P = {"fontSize": "0.88rem", "lineHeight": "1.7", "marginBottom": "10px"}


def _p(text: str) -> html.P:
    return html.P(text, style=_P)


def _table_html(headers: list[str], rows: list[list[str]]) -> html.Table:
    """Render a simple HTML table."""
    hdr = html.Thead(html.Tr([html.Th(h, style={
        "padding": "6px 10px", "borderBottom": f"2px solid {_NAVY}",
        "textAlign": "left", "fontSize": "0.82rem", "fontWeight": "bold",
        "color": _NAVY, "backgroundColor": _BG,
    }) for h in headers]))
    body_rows = []
    for i, row in enumerate(rows):
        bg = "#fff" if i % 2 == 0 else "#f8f8fc"
        body_rows.append(html.Tr([html.Td(c, style={
            "padding": "5px 10px", "fontSize": "0.82rem", "borderBottom": "1px solid #e8e8ee",
        }) for c in row], style={"backgroundColor": bg}))
    return html.Table([hdr, html.Tbody(body_rows)], style={
        "width": "100%", "borderCollapse": "collapse", "marginBottom": "16px",
    })


def _tab_overview(lang: str) -> html.Div:
    if lang == "lv":
        return html.Div([
            _section("Pārskats", [
                _p("Šis panelis apkopo pētījuma galvenos rezultātus par Latvijas dzīvojamo ēku "
                   "energoefektivitātes sertifikātu (EPC) prognozēšanu, izmantojot mašīnmācīšanos."),
                _p("Latvijā aptuveni 30 000 ēku (8% no kopējā dzīvojamo ēku fonda) ir saņēmušas EPC sertifikātus. "
                   "Šis pētījums izmanto mašīnmācīšanos, lai prognozētu energoefektivitātes klases "
                   "atlikušajām ~381 000 nesertificētajām ēkām, izmantojot novērojamas ēku pazīmes."),
            ]),
            _section("Galvenie secinājumi", [
                html.Ul([
                    html.Li("22 887 ēkas ar zināmiem EPC sertifikātiem no 7 datu avotiem."),
                    html.Li("Labākais individuālais modelis: CatBoost klasifikators — 54.6% precīza atbilstība, 81.0% ±1 klases precizitāte."),
                    html.Li("Labākā specifikācija: Ensemble-stack-cls (LightGBM + XGBoost + CatBoost ar LogReg meta-mācīšanos) — 53.7% precīza, 81.6% ±1."),
                    html.Li("Salīdzinot ar 2025. g. bāzlīniju (6 pazīmes): +10 pp precīzā atbilstībā, +3 pp ±1 precizitātē."),
                    html.Li("Prognozētas ~381 000 dzīvojamo ēku energoefektivitātes klases visā Latvijā."),
                    html.Li("Konformālie prognozēšanas intervāli (CQR) ar mainīgu platumu katrai ēkai."),
                    html.Li("ES taksonomijas 15% energoefektivitātes slieksnis: ~139 kWh/m²/gadā primārā enerģija."),
                ], style={"fontSize": "0.88rem", "lineHeight": "1.6"}),
            ]),
            _section("Galvenie rādītāji", [
                _table_html(
                    ["Rādītājs", "Vērtība"],
                    [
                        ["Apmācību ēkas", "22 887"],
                        ["Pazīmju skaits", "71 (koks-gatavs)"],
                        ["Labākais klasifikators", "CatBoost-cls"],
                        ["Labākā specifikācija", "Ensemble-stack-cls (LGBM+XGB+CatBoost)"],
                        ["Precīza atbilstība", "54.6% (CatBoost-cls) / 53.7% (ansamblis)"],
                        ["±1 klases precizitāte", "81.0% / 81.6%"],
                        ["RMSE (regresija, CV)", "29.5 kWh/m²/gadā"],
                        ["Prognozētas ēkas", "380 534"],
                        ["CQR intervāla q̂", "5.84 kWh/m²/gadā"],
                    ],
                ),
            ]),
            _plot_card("dataset_composition.png",
                       "Datu kopas sastāvs", "Datu kopas sastāvs", lang),
            _plot_card("class_distribution.png",
                       "EPC klašu sadalījums", "EPC klašu sadalījums apmācību datu kopā", lang),
        ])
    else:
        return html.Div([
            _section("Overview", [
                _p("This panel summarises research findings on predicting Energy Performance "
                   "Certificate (EPC) levels for Latvian residential buildings using machine learning."),
                _p("In Latvia, approximately 30,000 buildings (8% of the total residential stock) hold EPC certificates. "
                   "This study uses machine learning to predict energy performance classes for the remaining "
                   "~381,000 uncertified buildings using observable building attributes from cadastral, "
                   "geographic, and socioeconomic data sources."),
            ]),
            _section("Key Findings", [
                html.Ul([
                    html.Li("22,887 buildings with known EPCs, enriched from 7 data sources."),
                    html.Li("Best individual model: CatBoost classifier — 54.6% exact match, 81.0% ±1 class accuracy."),
                    html.Li("Best specification: Ensemble-stack-cls (LightGBM + XGBoost + CatBoost with LogReg meta-learner) — 53.7% exact, 81.6% ±1."),
                    html.Li("Compared to 2025 baseline (6 features): +10 pp exact, +3 pp ±1 accuracy."),
                    html.Li("Predicted EPC classes for ~381,000 residential buildings across Latvia."),
                    html.Li("Conformal prediction intervals (CQR) with variable-width bounds for each building."),
                    html.Li("EU Taxonomy 15% energy-efficiency threshold: ~139 kWh/m²/year primary energy."),
                ], style={"fontSize": "0.88rem", "lineHeight": "1.6"}),
            ]),
            _section("Key Metrics", [
                _table_html(
                    ["Metric", "Value"],
                    [
                        ["Training buildings", "22,887"],
                        ["Feature count", "71 (tree-ready)"],
                        ["Best classifier", "CatBoost-cls"],
                        ["Best specification", "Ensemble-stack-cls (LGBM+XGB+CatBoost)"],
                        ["Exact accuracy", "54.6% (CatBoost-cls) / 53.7% (ensemble)"],
                        ["±1 class accuracy", "81.0% / 81.6%"],
                        ["RMSE (regression, CV)", "29.5 kWh/m²/year"],
                        ["Predicted buildings", "380,534"],
                        ["CQR interval q̂", "5.84 kWh/m²/year"],
                    ],
                ),
            ]),
            _plot_card("dataset_composition.png",
                       "Dataset composition: EPC certificates and GeoRiga records",
                       "Dataset composition", lang),
            _plot_card("class_distribution.png",
                       "EPC class distribution in the training dataset",
                       "EPC class distribution", lang),
        ])


def _tab_literature(lang: str) -> html.Div:
    if lang == "lv":
        studies_headers = ["Pētījums", "Valsts", "N", "Pazīmes", "Metode", "Galvenais rezultāts"]
    else:
        studies_headers = ["Study", "Country", "N", "Features", "Method", "Key result"]

    studies_rows = [
        ["Pasichnyi et al. (2019)", "Sweden", "260,000+", "20+", "RF, GBM", "RMSE 30–45 kWh/m²/year"],
        ["Hsu (2015)", "US", "11,000+", "15", "Clustering+RF", "55–65% classification acc."],
        ["Kontokosta & Tull (2017)", "US (NYC)", "23,000+", "11", "RF, SVM", "R²=0.58"],
        ["Gangolells et al. (2016)", "Spain", "n/a", "GIS", "Spatial", "40–50% class accuracy"],
        ["Geyer et al. (2018)", "Germany", "800+", "8", "RF, SVM, ANN", "R²=0.75 (non-residential)"],
        ["Sheng et al. (2022)", "UK", "5,933", "EPC+StreetView", "CNN+MLP", "MAD 0.01 kWh/m²/yr"],
        ["Seyedzadeh et al. (2018)", "Review", "67 studies", "—", "Review", "GBM/RF most effective"],
        ["Jankovskis & Strazdiņš (2025)", "Latvia", "19,715", "6", "LightGBM", "40%/49% exact (houses/apts)"],
        ["This study", "Latvia", "22,887", "71", "CatBoost", "54.6% exact, 81.0% ±1"],
    ]

    if lang == "lv":
        return html.Div([
            _section("Literatūras apskats", [
                _p("Mašīnmācīšanās pieejas ēku energoefektivitātes prognozēšanai ir būtiski paplašinājušās "
                   "kopš 2015. gada. Gradientu pastiprināšanas metodes (LightGBM, XGBoost, CatBoost) ir kļuvušas "
                   "par de facto standartu tabulāru EPC datu prognozēšanai."),
                _p("Trīs galvenie konsekventi atkārtotie secinājumi pētījumos: (1) būvniecības gads ir visspēcīgākais "
                   "individuālais prognozētājs; (2) gradientu pastiprināšanas metodes pārspēj lineāros modeļus un "
                   "neironu tīklus strukturētiem ēku datiem; (3) klašu nelīdzsvarotība ir universāla — vidējās "
                   "EPC klases (C, D) ir pārāk pārstāvētas, pasliktinot mazākumklašu atpazīšanu."),
            ]),
            _section("Salīdzinājums ar citiem pētījumiem", [
                _table_html(studies_headers, studies_rows),
            ]),
            _section("Telpiskā validācija", [
                _p("Standarta nejauši dalīta apmācības/testa kopa pieņem novērojumu neatkarību. Ēku enerģijas "
                   "datos šis pieņēmums ir pārkāpts, jo vienas apkaimes ēkām ir kopīgi nenovēroti faktori — "
                   "vietējās būvnormas, vērtētāju prakse, centrālapkures infrastruktūra."),
                _p("Roberts et al. (2017) parādīja, ka ģeogrāfiski bloķēta krusteniskā validācija sniedz "
                   "godīgākus vispārinājuma aplēses — precizitāte var būt par 5–15 procentpunktiem zemāka "
                   "nekā nejaušajā validācijā. Šis pētījums salīdzina četras CV stratēģijas ar pieaugošu "
                   "ģeogrāfisko stingrību."),
            ]),
            _section("Latvijas ēku fonda īpatnības", [
                _p("Baltijas valstīm ir raksturīga iezīme — liela daudzdzīvokļu ēku daļa tika celta "
                   "padomju periodā (1945–1991) pēc standartizētiem sērijveida projektiem (103, 119, 464, 602). "
                   "Šīs ēkas veido aptuveni 65% no daudzdzīvokļu fonda."),
                _p("2021. gada administratīvā reforma apvienoja 119 pašvaldības 43 vienībās (36 novadi + "
                   "7 valstspilsētas), ietekmējot telpiskās krusteniskās validācijas granularitāti."),
            ]),
            _section(html.Span(["Salīdzinājums ar 2025. g. pētījumu (", html.I("baseline"), ")"]), [
                _p("Jankovskis un Strazdiņš (2025) demonstrēja EPC prognozēšanas iespējamību Latvijai, apmācot "
                   "atsevišķus LightGBM klasifikatorus individuālajām mājām (40% precīzā, 79% ±1) un "
                   "daudzdzīvokļu ēkām (49% precīzā, 81% ±1) ar 6 pazīmēm un nejaušu 80/20 dalījumu."),
                _table_html(
                    ["Konfigurācija", "Pazīmes", "CV stratēģija", "Precīzā (%)", "±1 (%)"],
                    [
                        ["2025 replikācija (kombinēts)", "6", "Nejauša 80/20", "44.7", "78.4"],
                        ["Mūsu cauruļvads (6 pazīmes)", "6", "Nejauša 5-fold", "46.0", "77.7"],
                        ["Mūsu cauruļvads (6 pazīmes)", "6", "Teritoriāla", "41.7", "73.3"],
                        ["Pilns cauruļvads (71 pazīme)", "71", "Nejauša 80/20", "54.6", "81.0"],
                        ["Pilns cauruļvads (71 pazīme)", "71", "Nejauša 5-fold", "47.6", "81.2"],
                        ["Pilns cauruļvads (71 pazīme)", "71", "Teritoriāla", "46.8", "80.2"],
                    ],
                ),
                _p("Pilns cauruļvads (nejauša 80/20) uzlabo precīzo atbilstību par ~10 pp un ±1 precizitāti par ~3 pp "
                   "salīdzinot ar 2025. g. bāzlīniju."),
            ]),
        ])
    else:
        return html.Div([
            _section("Literature Review", [
                _p("Machine learning approaches to building energy performance prediction have expanded "
                   "substantially since 2015. Gradient boosting methods (LightGBM, XGBoost, CatBoost) have become "
                   "the de facto standard for tabular EPC prediction."),
                _p("Three findings are consistently replicated across studies: (1) construction year is the "
                   "single strongest predictor; (2) gradient boosting methods outperform linear models and neural "
                   "networks for structured building data; (3) class imbalance is universal — middle EPC classes "
                   "(C, D) are over-represented, depressing minority-class recall."),
            ]),
            _section("Comparison with Other Studies", [
                _table_html(studies_headers, studies_rows),
            ]),
            _section("Spatial Validation", [
                _p("Standard random train–test splits assume observation independence. In building energy datasets, "
                   "this assumption is violated because buildings in the same neighbourhood share unobserved factors — "
                   "local construction norms, assessor practices, district heating infrastructure."),
                _p("Roberts et al. (2017) demonstrated that geographic block cross-validation provides more honest "
                   "generalisation estimates — accuracy can be 5–15 percentage points lower than random validation. "
                   "This study systematically compares four CV strategies of increasing geographic stringency."),
            ]),
            _section("Latvian Building Stock Characteristics", [
                _p("The Baltic states share a distinctive characteristic: a large proportion of multi-apartment "
                   "buildings were constructed during the Soviet period (1945–1991) using standardised series "
                   "designs (103, 119, 464, 602). These buildings account for roughly 65% of the multi-apartment stock."),
                _p("The 2021 administrative reform consolidated Latvia's 119 municipalities into 43 units "
                   "(36 novads + 7 independent cities), affecting the geographic granularity available for "
                   "spatial cross-validation."),
            ]),
            _section("Comparison with 2025 Study", [
                _p("Jankovskis & Strazdiņš (2025) demonstrated EPC prediction feasibility for Latvia, training "
                   "separate LightGBM classifiers for individual houses (40% exact, 79% ±1) and apartment "
                   "buildings (49% exact, 81% ±1) using 6 features with a random 80/20 split."),
                _table_html(
                    ["Configuration", "Features", "CV Strategy", "Exact (%)", "±1 (%)"],
                    [
                        ["2025 replication (combined)", "6", "Random 80/20", "44.7", "78.4"],
                        ["Our pipeline (6 features)", "6", "Random 5-fold", "46.0", "77.7"],
                        ["Our pipeline (6 features)", "6", "Territory", "41.7", "73.3"],
                        ["Full pipeline (71 features)", "71", "Random 80/20", "54.6", "81.0"],
                        ["Full pipeline (71 features)", "71", "Random 5-fold", "47.6", "81.2"],
                        ["Full pipeline (71 features)", "71", "Territory", "46.8", "80.2"],
                    ],
                ),
                _p("The full pipeline (random 80/20) improves exact accuracy by ~10 pp and ±1 accuracy by ~3 pp compared "
                   "to the 2025 baseline."),
            ]),
        ])


def _tab_data(lang: str) -> html.Div:
    if lang == "lv":
        return html.Div([
            _section("Datu avoti", [
                _p("Modelis apvieno datus no septiņiem avotiem, veidojot daudzpusīgu ēku aprakstu:"),
                _table_html(
                    ["Datu avots", "Ieraksti", "Galvenās pazīmes"],
                    [
                        ["EPC sertifikātu datubāze", "35 896 (28 091 pēc deduplikācijas)", "Enerģijas patēriņš, EPC klase, sienu materiāls, platība"],
                        ["GeoRiga (Rīgas pilsētas inventārs)", "4 105", "Būvniecības gads, stāvu skaits, ēkas tips"],
                        ["VZD Kadastra atvērtie dati", "381 343", "Nolietojums, apkures tips, platība, būvtilpums"],
                        ["CSP sociālekonomiskie dati", "43 teritorijas", "Ienākumu līmenis, iedzīvotāju blīvums"],
                        ["Wayback Machine sludinājumi", "3 854 atbilstības", "Padomju ēku sērija (103, 119, 464, 602)"],
                        ["NITIS darījumu dati", "~200 000", "KNN telpiskā cenu aproksimācija"],
                        ["ALTUM renovāciju dati", "278 atbilstības", "Renovācijas statuss, sērija"],
                    ],
                ),
            ]),
            _section(html.Span(["Datu apstrādes ", html.I("pipeline")]), [
                _table_html(
                    ["Posms", "Ieraksti"],
                    [
                        ["Ielādēti neapstrādāti EPC sertifikāti", "35 896"],
                        ["Pēc gada tīrīšanas + kolonnu atvasināšanas", "35 896"],
                        ["Pēc deduplikācijas (jaunākais katrai ēkai)", "28 091"],
                        ["GeoRiga ēkas pievienotas", "32 196"],
                        ["Pēc pārklāšanās risināšanas + dzīvojamo filtrs", "24 046"],
                        ["Pamata dzīvojamo dalījums", "22 890"],
                        ["Modelim gatavs (EPC klase nav tukša)", "22 887"],
                    ],
                ),
            ]),
            _section("Būvniecības gada tīrīšana", [
                _p("Latvijas ēku datos būvniecības gads bieži ir nestandarta formā — teksts ar gadsimtu "
                   "norādēm ('19.gs'), diapazoniem ('80-tie gadi'), pareizrakstības kļūdām ('9180' → 1980), "
                   "un vairākiem gadskaitļiem vienā laukā. 13 soļu kaskāde atgūst ~95% datu."),
            ]),
            _section("Pazīmju inženierija", [
                _p("71 pazīme organizēta 8 grupās: ēkas raksturlielumi (platība, stāvi, gads), "
                   "materiāli (sienas, jumts), telpiskās (koordinātas, pasta indekss, teritorija), "
                   "sociālekonomiskie (ienākumi, blīvums), nolietojums, sērija, renovācija, NITIS cenas."),
            ]),
            _section("Pazīmju svarīgums (SHAP)", [
                _p("SHAP (SHapley Additive exPlanations) parāda katras pazīmes ieguldījumu prognozē. "
                   "Visspēcīgākie prognozētāji: būvniecības gads, nolietojums, platība, pasta indekss."),
                _plot_card("shap_summary_bar.png", "", "SHAP pazīmju svarīgums", lang),
                _plot_card("shap_summary_beeswarm.png", "", "SHAP bišu spieta diagramma", lang),
            ]),
        ])
    else:
        return html.Div([
            _section("Data Sources", [
                _p("The model combines data from seven sources to build a comprehensive building profile:"),
                _table_html(
                    ["Data Source", "Records", "Key Features"],
                    [
                        ["EPC certificate database", "35,896 (28,091 after dedup)", "Energy consumption, EPC class, wall material, area"],
                        ["GeoRiga (Riga city inventory)", "4,105", "Construction year, floor count, building type"],
                        ["VZD Cadastral open data", "381,343", "Depreciation, heating type, area, volume"],
                        ["CSP socioeconomic data", "43 territories", "Income level, population density"],
                        ["Wayback Machine ads", "3,854 matches", "Soviet building series (103, 119, 464, 602)"],
                        ["NITIS transaction data", "~200,000", "KNN spatial price approximation"],
                        ["ALTUM renovation data", "278 matches", "Renovation status, series"],
                    ],
                ),
            ]),
            _section("Data Processing Pipeline", [
                _table_html(
                    ["Stage", "Records"],
                    [
                        ["Raw EPC certificates loaded", "35,896"],
                        ["After year cleaning + column derivation", "35,896"],
                        ["After deduplication (keep newest per building)", "28,091"],
                        ["GeoRiga buildings appended", "32,196"],
                        ["After overlap resolution + residential filter", "24,046"],
                        ["Core residential split", "22,890"],
                        ["Model-ready (EPC class non-null)", "22,887"],
                    ],
                ),
            ]),
            _section("Construction Year Cleaning", [
                _p("Latvian building data frequently contains construction years in non-standard formats — "
                   "century references ('19.gs'), decade ranges ('80-tie gadi'), typos ('9180' → 1980), "
                   "and multiple years in one field. A 13-step cascade recovers ~95% of usable data."),
            ]),
            _section("Feature Engineering", [
                _p("71 features organised into 8 groups: building characteristics (area, floors, year), "
                   "materials (walls, roof), spatial (coordinates, postal code, territory), socioeconomic "
                   "(income, density), depreciation, series, renovation, NITIS prices."),
            ]),
            _section("Feature Importance (SHAP)", [
                _p("SHAP (SHapley Additive exPlanations) shows each feature's contribution to predictions. "
                   "Strongest predictors: construction year, depreciation, area, postal code."),
                _plot_card("shap_summary_bar.png", "SHAP feature importance (bar plot)", "", lang),
                _plot_card("shap_summary_beeswarm.png", "SHAP beeswarm plot — feature impact direction", "", lang),
            ]),
        ])


def _tab_performance(lang: str) -> html.Div:
    if lang == "lv":
        return html.Div([
            _section("Modeļu salīdzinājums", [
                _p("Novērtēti 29 modeļi ar četrām krusteniskās validācijas stratēģijām. "
                   "Tabula rāda rezultātus nejaušajai 5-fold CV stratēģijai."),
                _table_html(
                    ["Modelis", "Tips", "Precīzā (%, CV)", "±1 (%, CV)", "RMSE (CV)"],
                    [
                        ["CatBoost-cls", "Klasifikators", "47.6", "79.8", "—"],
                        ["LGBM-cls-tuned", "Klasifikators", "47.6", "81.2", "—"],
                        ["XGBoost-cls", "Klasifikators", "46.9", "80.1", "—"],
                        ["Ensemble-stack-cls", "Ansamblis (LGBM+XGB+CB)", "47.4", "80.7", "—"],
                        ["LGBM-tuned-log", "Regresoris", "38.4", "83.2", "29.5"],
                        ["Ensemble-stack-reg", "Regresijas ansamblis", "38.4", "—", "27.1"],
                    ],
                ),
                _plot_card("baseline_comparison.png", "", "Bāzlīnijas salīdzinājums", lang),
                _plot_card("cv_strategy_comparison.png", "", "CV stratēģiju salīdzinājums", lang),
            ]),
            _section("Krusteniskās validācijas stratēģijas", [
                _p("Četras stratēģijas ar pieaugošu ģeogrāfisko stingrību:"),
                _table_html(
                    ["Stratēģija", "Bloķēšanas vienība", "Grupas", "Mērķis"],
                    [
                        ["Nejauša", "Nav", "—", "Tradicionāls etalons"],
                        ["Pasta indekss", "Pasta indekss", "553", "Vietēja ģeogrāfiskā bloķēšana"],
                        ["Hibrīda", "Pasta indekss + nejauša", "—", "Mērenāk ietekmēta"],
                        ["Teritoriāla", "43 admin. teritorijas", "43", "Visstingrākā — Rīga kā vesela daļa"],
                    ],
                ),
                _p("Teritoriālā CV ir visstingrākā: Rīga (33.4% datu) veido vienu veselu testu daļu. "
                   "Tas penalizē telpisko autokorelāciju un sniedz konservatīvākas aplēses."),
                _plot_card("cv_fold_boxplots_exact.png", "", "Precizitātes sadalījums pa CV daļām", lang),
                _plot_card("cv_fold_boxplots_rmse.png", "", "RMSE sadalījums pa CV daļām", lang),
            ]),
            _section("Sajaukšanas matrica", [
                _p("Sagaidāmi, vislielākā kļūdu daļa ir ±1 klases nobīdes — C klase bieži tiek sajaukta ar B un D. "
                   "A+ klase ir pārāk maza (1.3% datu), lai to ticami prognozētu."),
                _plot_card("confusion_matrix_best.png", "", "Sajaukšanas matrica — labākais klasifikators", lang),
                _plot_card("confusion_matrix_dual.png", "", "Dubultā etiķešu sajaukšanas matrica", lang),
                _plot_card("holdout_drift_by_year.png", "", "Precizitāte pēc sertifikāta gada", lang),
            ]),
            _section("Rezultāti pa klasēm", [
                _p("C klase (28.4% no apmācības datiem) uzrāda augstāko F1-rādītāju. "
                   "D klase ir sistemātiski grūti prognozējama visos modeļos — iespējams, ka D klasē ietilpst "
                   "ēkas no dažādām ēras un materiālu kategorijām bez skaidra šķirošanas signāla."),
                _plot_card("per_class_metrics.png", "", "F1-rādītājs pa klasēm", lang),
                _plot_card("class_imbalance_delta.png", "", "Klašu nelīdzsvarotības ietekme", lang),
            ]),
            _section("Pazīmju grupu ablācija", [
                _p("Kumulatīvā ablācija parāda katras pazīmju grupas marginālo ieguldījumu. "
                   "Pamata ēkas raksturlielumi veido lielāko daļu, bet telpiskās un sociālekonomiskās "
                   "pazīmes pievieno nozīmīgus 2–3 procentpunktus."),
                _plot_card("ablation_waterfall.png", "", "Pazīmju grupu ablācija", lang),
            ]),
            _section("Konformālie prognozēšanas intervāli", [
                _p("Konformālā kvantīļu regresija (CQR) nodrošina mainīga platuma intervālus katrai ēkai. "
                   "Kalibrēšanas parametrs q̂ = 5.84 kWh/m²/gadā. Pārklājums: ~89% (mērķis: 90%)."),
                _plot_card("conformal_coverage.png", "", "Konformālais pārklājums", lang),
                _plot_card("cqr_comparison.png", "", "CQR intervālu salīdzinājums", lang),
                _plot_card("interval_width_comparison.png", "", "Intervālu platumu sadalījums", lang),
            ]),
        ])
    else:
        return html.Div([
            _section("Model Comparison", [
                _p("29 models evaluated across four cross-validation strategies. "
                   "Table shows results for the random 5-fold CV strategy."),
                _table_html(
                    ["Model", "Type", "Exact (%, CV)", "±1 (%, CV)", "RMSE (CV)"],
                    [
                        ["CatBoost-cls", "Classifier", "47.6", "79.8", "—"],
                        ["LGBM-cls-tuned", "Classifier", "47.6", "81.2", "—"],
                        ["XGBoost-cls", "Classifier", "46.9", "80.1", "—"],
                        ["Ensemble-stack-cls", "Ensemble (LGBM+XGB+CB)", "47.4", "80.7", "—"],
                        ["LGBM-tuned-log", "Regressor", "38.4", "83.2", "29.5"],
                        ["Ensemble-stack-reg", "Regression ensemble", "38.4", "—", "27.1"],
                    ],
                ),
                _plot_card("baseline_comparison.png", "Baseline comparison: 2025 study vs current", "", lang),
                _plot_card("cv_strategy_comparison.png", "Model performance across CV strategies", "", lang),
            ]),
            _section("Cross-Validation Strategies", [
                _p("Four strategies with increasing geographic stringency:"),
                _table_html(
                    ["Strategy", "Blocking Unit", "Groups", "Purpose"],
                    [
                        ["Random", "None", "—", "Traditional benchmark"],
                        ["Postal code", "Postal code", "553", "Local geographic blocking"],
                        ["Hybrid", "Postal + random", "—", "Moderate geographic penalty"],
                        ["Territory", "43 admin. territories", "43", "Strictest — Riga as a single fold"],
                    ],
                ),
                _p("Territory CV is the strictest: Riga (33.4% of data) forms one entire test fold. "
                   "This penalises spatial autocorrelation and provides more conservative estimates."),
                _plot_card("cv_fold_boxplots_exact.png", "Exact accuracy across CV folds", "", lang),
                _plot_card("cv_fold_boxplots_rmse.png", "RMSE across CV folds", "", lang),
            ]),
            _section("Confusion Matrix", [
                _p("As expected, the dominant error pattern is ±1 class shifts — C class is frequently "
                   "confused with B and D. A+ class is too small (1.3% of data) for reliable prediction."),
                _plot_card("confusion_matrix_best.png", "Confusion matrix — best classifier", "", lang),
                _plot_card("confusion_matrix_dual.png", "Dual-label confusion matrix", "", lang),
                _plot_card("holdout_drift_by_year.png", "Prediction accuracy by certificate year", "", lang),
            ]),
            _section("Per-Class Performance", [
                _p("C class (28.4% of training data) shows the highest F1-score. "
                   "D class is systematically difficult to predict across all models — likely because D-class "
                   "buildings span diverse eras and material categories without a clear separating signal."),
                _plot_card("per_class_metrics.png", "Per-class precision, recall, F1", "", lang),
                _plot_card("class_imbalance_delta.png", "Class imbalance effect on accuracy", "", lang),
            ]),
            _section("Feature Group Ablation", [
                _p("Cumulative ablation reveals each feature group's marginal contribution. "
                   "Core building characteristics provide the largest share, but spatial and socioeconomic "
                   "features add a meaningful 2–3 percentage points."),
                _plot_card("ablation_waterfall.png", "Feature group ablation — waterfall chart", "", lang),
            ]),
            _section("Conformal Prediction Intervals", [
                _p("Conformalized quantile regression (CQR) provides variable-width intervals for each building. "
                   "Calibration parameter q̂ = 5.84 kWh/m²/year. Coverage: ~89% (target: 90%)."),
                _plot_card("conformal_coverage.png", "Conformal coverage", "", lang),
                _plot_card("cqr_comparison.png", "CQR interval width comparison", "", lang),
                _plot_card("interval_width_comparison.png", "Interval width distribution", "", lang),
            ]),
        ])


def _tab_stock(lang: str) -> html.Div:
    if lang == "lv":
        return html.Div([
            _section("Ēku fonda prognožu sadalījums", [
                _p("Apmācītais modelis tika piemērots visām 380 534 dzīvojamām ēkām VZD Kadastrā. "
                   "Prognozētais sadalījums būtiski atšķiras no apmācības datu kopas — C klase dominē "
                   "ēku fondā (75%), bet apmācības datos ir tikai 28%."),
                _p("Šī nobīde atspoguļo faktu, ka EPC sertifikāti neproporcionāli pārstāv renovētas "
                   "un jaunbūves ēkas (A/B klases), savukārt lielākā daļa nesertificēto ēku ir tipiskā "
                   "padomju perioda apbūve ar mērenu energoefektivitāti."),
                _plot_card("housing_stock_energy_combined.png", "", "Prognozēto klašu sadalījums", lang),
                _plot_card("class_distribution_comparison.png", "", "Apmācības vs ēku fonda sadalījumi", lang),
            ]),
            _section("Prognožu ticamība", [
                _p("Modeļa ticamība (softmax varbūtība pareizajai klasei) ir vidēji ~42%. "
                   "Augstāka ticamība raksturīga ēkām ar pilnīgāku datu pieejamību un skaidrākām pazīmēm "
                   "(piemēram, jaunbūves ar pilnu kadastra informāciju)."),
                _p("Padomju perioda daudzdzīvokļu ēkas uzrāda zemāku ticamību — tām raksturīgs plašāks "
                   "EPC klašu diapazons atkarībā no renovācijas statusa."),
                _plot_card("prediction_confidence_distribution.png", "", "Ticamības sadalījums", lang),
                _plot_card("prediction_confidence_by_type_era.png", "", "Ticamība pēc tipa un ēras", lang),
                _plot_card("prediction_confidence_latvia.png", "", "Ticamības karte — Latvija", lang),
            ]),
            _section("ES taksonomijas analīze", [
                _p("ES Klimata deleģētais akts nosaka, ka 'zaļam' nekustamajam īpašumam jāierindojas "
                   "labāko 15% ēku vidū pēc primārās enerģijas patēriņa. Latvijā šis slieksnis ir "
                   "aptuveni 139 kWh/m²/gadā primārā enerģija (95% CI: 139.1–139.2)."),
                _p("Aptuveni 15% ēku fonda atbilst šim slieksnim — galvenokārt jaunbūves un renovētas ēkas. "
                   "Tomēr prognozēšanas nenoteiktība (CQR intervāli) nozīmē, ka atsevišķām ēkām atbilstība "
                   "taksonomijas prasībām nav droši noteikta."),
                _plot_card("eu_taxonomy_eligibility.png", "", "ES taksonomijas atbilstība — 15% slieksnis", lang),
                _plot_card("eu_taxonomy_ci.png", "", "ES taksonomija ar ticamības intervāliem", lang),
                _plot_card("eu_taxonomy_eligibility_riga.png", "", "ES taksonomija — Rīga", lang),
                _plot_card("eu_taxonomy_eligibility_latvia.png", "", "ES taksonomija — Latvijas reģioni", lang),
            ]),
        ])
    else:
        return html.Div([
            _section("Housing Stock Prediction Distribution", [
                _p("The trained model was applied to all 380,534 residential buildings in the VZD Cadastre. "
                   "The predicted distribution differs substantially from the training dataset — C class dominates "
                   "the housing stock (75%) vs only 28% in training data."),
                _p("This shift reflects the fact that EPC certificates disproportionately represent renovated "
                   "and new-build (A/B class) buildings, while most uncertified buildings are typical Soviet-era "
                   "construction with moderate energy performance."),
                _plot_card("housing_stock_energy_combined.png", "Predicted class distribution — full stock", "", lang),
                _plot_card("class_distribution_comparison.png", "Training vs stock class distributions", "", lang),
            ]),
            _section("Prediction Confidence", [
                _p("Model confidence (softmax probability for predicted class) averages ~42%. "
                   "Higher confidence is observed for buildings with more complete data and clearer feature "
                   "signals (e.g., new builds with full cadastral information)."),
                _p("Soviet-era multi-apartment buildings show lower confidence — they span a wide range of "
                   "EPC classes depending on renovation status."),
                _plot_card("prediction_confidence_distribution.png", "Confidence distribution", "", lang),
                _plot_card("prediction_confidence_by_type_era.png", "Confidence by type and era", "", lang),
                _plot_card("prediction_confidence_latvia.png", "Confidence map — Latvia", "", lang),
            ]),
            _section("EU Taxonomy Analysis", [
                _p("The EU Climate Delegated Act requires 'green' real estate to rank in the top 15% "
                   "by primary energy. In Latvia, this threshold is approximately 139 kWh/m²/year primary "
                   "energy (95% CI: 139.1–139.2)."),
                _p("Approximately 15% of the housing stock meets this threshold — mainly new builds and "
                   "renovated buildings. However, prediction uncertainty (CQR intervals) means that for "
                   "some buildings, taxonomy eligibility cannot be determined with certainty."),
                _plot_card("eu_taxonomy_eligibility.png", "EU Taxonomy eligibility — top 15%", "", lang),
                _plot_card("eu_taxonomy_ci.png", "EU Taxonomy with confidence intervals", "", lang),
                _plot_card("eu_taxonomy_eligibility_riga.png", "EU Taxonomy — Riga", "", lang),
                _plot_card("eu_taxonomy_eligibility_latvia.png", "EU Taxonomy — Latvia regions", "", lang),
            ]),
        ])


def _tab_maps(lang: str) -> html.Div:
    if lang == "lv":
        return html.Div([
            _section("Latvijas kartes", [
                _p("Ēku blīvuma un EPC klašu ģeogrāfiskais sadalījums visā Latvijā. "
                   "Rīga dominē gan ēku skaitā, gan EPC sertifikātu pārklājumā."),
                _plot_card("latvia_building_density.png", "", "Ēku blīvums Latvijā", lang),
                _plot_card("latvia_epc_class_dots.png", "", "EPC klašu punktkarte — Latvija", lang),
            ]),
            _section("Rīgas kartes", [
                _p("Rīga satur 33.4% no visiem apmācības datiem un uzrāda vienigotāku ēku fondu "
                   "nekā lauki — galvenokārt padomju perioda daudzdzīvokļu ēkas centrā un individuālās "
                   "mājas piepilsētā."),
                _plot_card("riga_building_density.png", "", "Ēku blīvums — Rīgas apkaimes", lang),
                _plot_card("riga_epc_class_dots.png", "", "EPC klašu punktkarte — Rīga", lang),
                _plot_card("riga_neighborhood_accuracy.png", "", "Prognožu precizitāte pa apkaimēm", lang),
                _plot_card("riga_neighborhood_apartments.png", "", "Daudzdzīvokļu ēku sadalījums", lang),
                _plot_card("riga_neighborhood_building_age.png", "", "Ēku vecuma sadalījums pa apkaimēm", lang),
            ]),
        ])
    else:
        return html.Div([
            _section("Latvia Maps", [
                _p("Geographic distribution of building density and EPC classes across Latvia. "
                   "Riga dominates both in building count and EPC certificate coverage."),
                _plot_card("latvia_building_density.png", "Building density across Latvia", "", lang),
                _plot_card("latvia_epc_class_dots.png", "EPC class dot map — Latvia", "", lang),
            ]),
            _section("Riga Maps", [
                _p("Riga contains 33.4% of all training data and shows a more homogeneous building stock "
                   "than rural areas — primarily Soviet-era apartment buildings in the center and individual "
                   "houses in the suburbs."),
                _plot_card("riga_building_density.png", "Building density — Riga neighbourhoods", "", lang),
                _plot_card("riga_epc_class_dots.png", "EPC class dot map — Riga", "", lang),
                _plot_card("riga_neighborhood_accuracy.png", "Prediction accuracy by neighbourhood", "", lang),
                _plot_card("riga_neighborhood_apartments.png", "Apartment building distribution", "", lang),
                _plot_card("riga_neighborhood_building_age.png", "Building age by neighbourhood", "", lang),
            ]),
        ])
_TAB_BUILDERS = {
    "overview": _tab_overview,
    "literature": _tab_literature,
    "data": _tab_data,
    "performance": _tab_performance,
    "stock": _tab_stock,
    "maps": _tab_maps,
}

# ---------------------------------------------------------------------------
# Layout
# ---------------------------------------------------------------------------

def layout() -> html.Div:
    """Return the Model Info page layout with tabs."""
    tab_buttons = html.Div(
        [
            html.Button(
                en_label,  # will be updated by callback
                id=f"mi-tab-{tid}",
                n_clicks=0,
                style=_tab_style(tid == "overview", active=True),
            )
            for tid, en_label, _ in TABS
        ],
        id="mi-tab-bar",
        style={
            "display": "flex", "gap": "0", "marginBottom": "0",
            "borderBottom": f"2px solid {_NAVY}",
        },
    )

    return html.Div([
        dcc.Store(id="mi-active-tab", data="overview"),
        tab_buttons,
        html.Div(id="mi-tab-content", style={"padding": "1.5rem 0.5rem"}),
    ])


def _tab_style(is_first: bool, active: bool = False) -> dict:
    """Return style for a tab button."""
    base = {
        "border": "none", "cursor": "pointer",
        "padding": "0.6rem 1.2rem", "fontSize": "0.88rem",
        "fontWeight": "600", "borderRadius": "6px 6px 0 0",
        "transition": "background-color 0.2s",
    }
    if active:
        return {**base, "backgroundColor": _NAVY, "color": _WHITE}
    return {**base, "backgroundColor": _GREY, "color": _NAVY}


# ---------------------------------------------------------------------------
# Callbacks
# ---------------------------------------------------------------------------

def register_callbacks(app):
    """Register all Model Info page callbacks."""
    from dash import ctx, no_update, ALL

    # Tab click → update active tab store
    @app.callback(
        Output("mi-active-tab", "data"),
        [Input(f"mi-tab-{tid}", "n_clicks") for tid, _, _ in TABS],
        prevent_initial_call=True,
    )
    def _switch_tab(*clicks):
        triggered = ctx.triggered_id
        if triggered:
            # Extract tab id from button id "mi-tab-{tid}"
            return triggered.replace("mi-tab-", "")
        return no_update

    # Render tab content + restyle buttons
    tab_outputs = (
        [Output("mi-tab-content", "children")]
        + [Output(f"mi-tab-{tid}", "style") for tid, _, _ in TABS]
        + [Output(f"mi-tab-{tid}", "children") for tid, _, _ in TABS]
    )

    @app.callback(
        tab_outputs,
        Input("mi-active-tab", "data"),
        Input("lang-store", "data"),
    )
    def _render_tab(active_tab, lang):
        lang = lang or "lv"
        active_tab = active_tab or "overview"

        builder = _TAB_BUILDERS.get(active_tab, _tab_overview)
        content = builder(lang)

        styles = []
        labels = []
        for tid, en_label, lv_label in TABS:
            is_active = tid == active_tab
            styles.append(_tab_style(False, active=is_active))
            labels.append(lv_label if lang == "lv" else en_label)

        return [content] + styles + labels
