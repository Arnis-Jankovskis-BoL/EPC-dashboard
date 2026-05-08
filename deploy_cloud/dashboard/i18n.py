"""Internationalisation support for the EPC dashboard.

Two languages: English (en) and Latvian (lv).
All user-facing strings should be accessed via `t(key, lang)`.
"""
from __future__ import annotations

# Translation dictionary: key → {en: ..., lv: ...}
_STRINGS: dict[str, dict[str, str]] = {
    # Navigation
    "nav.explorer": {"en": "Building Explorer", "lv": "Ēku pārlūks"},
    "nav.data": {"en": "Data", "lv": "Dati"},
    "nav.model": {"en": "Model Info", "lv": "Modeļa info"},
    "app.title": {"en": "EPC Explorer", "lv": "EPC pārlūks"},

    # Search & filters
    "search.placeholder": {"en": "Type and press Enter to add filter...", "lv": "Ievadiet un nospiediet Enter..."},
    "search.mode.all": {"en": "Match ALL terms (AND)", "lv": "Atbilst VISIEM (UN)"},
    "search.mode.any": {"en": "Match ANY term (OR)", "lv": "Atbilst JEBKURAM (VAI)"},
    "filter.no_active": {"en": "No active filters.", "lv": "Nav aktīvu filtru."},
    "filter.total": {"en": "total", "lv": "kopā"},
    "filter.remaining": {"en": "remaining", "lv": "atlikuši"},
    "filter.breakdown": {"en": "Filtering Breakdown", "lv": "Filtrēšanas sadalījums"},
    "filter.custom": {"en": "Custom Filters", "lv": "Pielāgoti filtri"},

    # Slicers
    "slicer.epc": {"en": "EPC Class", "lv": "EPC klase"},
    "slicer.era": {"en": "Construction Era", "lv": "Būvniecības periods"},
    "slicer.wall": {"en": "Wall Material", "lv": "Sienu materiāls"},
    "slicer.all": {"en": "All", "lv": "Visi"},

    # Map
    "map.na": {"en": "No region (N/A)", "lv": "Nav reģiona (N/A)"},
    "map.clear": {"en": "Clear map selection", "lv": "Notīrīt kartes atlasi"},

    # Plots
    "plot.epc_dist": {"en": "EPC Class Distribution", "lv": "EPC klašu sadalījums"},
    "plot.era_dist": {"en": "Construction Era Distribution", "lv": "Būvniecības periodu sadalījums"},
    "plot.wall_dist": {"en": "Wall Material Distribution", "lv": "Sienu materiālu sadalījums"},
    "plot.avg_energy": {"en": "Average Heating Energy", "lv": "Vidējā apkures enerģija"},
    "plot.ref_toggle": {"en": "Show full-sample reference", "lv": "Rādīt pilnas izlases atsauci"},
    "plot.epc_label": {"en": "EPC Class", "lv": "EPC klase"},
    "plot.era_label": {"en": "Construction Era", "lv": "Būvniecības periods"},
    "plot.wall_label": {"en": "Wall Material", "lv": "Sienu materiāls"},
    "gauge.title": {"en": "Avg Heating Energy", "lv": "Vid. apkures enerģija"},
    "gauge.na": {"en": "N/A — no matching rows", "lv": "N/A — nav atbilstošu rindu"},

    # Pagination
    "page.of": {"en": "Page {page} of {total}", "lv": "{page}. lapa no {total}"},
    "page.buildings": {"en": "{n} buildings", "lv": "{n} ēkas"},

    # Column panel
    "cols.title": {"en": "Display Columns", "lv": "Rādāmās kolonnas"},
    "cols.plots": {"en": "Plots", "lv": "Grafiki"},

    # Tooltips
    "tooltip.ref": {
        "en": "When ON, dashed outlines show the full-sample distribution for comparison.",
        "lv": "Kad ieslēgts, punktētas kontūras rāda pilnas izlases sadalījumu salīdzināšanai.",
    },
    "tooltip.gauge": {
        "en": "Average heating energy of filtered buildings vs full sample (black marker).",
        "lv": "Filtrēto ēku vidējā apkures enerģija salīdzinājumā ar pilnu izlasi (melnais marķieris).",
    },
    "tooltip.map_na": {
        "en": "Show buildings without region information",
        "lv": "Rādīt ēkas bez reģiona informācijas",
    },

    # Detail panel
    "detail.title": {"en": "Building Details", "lv": "Ēkas detaļas"},

    # Loading
    "loading.message": {"en": "Loading dashboard...", "lv": "Ielādē instrumentu paneli..."},

    # Button labels
    "btn.columns": {"en": "Columns", "lv": "Kolonnas"},
    "btn.custom_filters": {"en": "Custom Filters", "lv": "Pielāgoti filtri"},
    "btn.filter_breakdown": {"en": "Filtering Breakdown", "lv": "Filtrēšanas sadalījums"},
    "btn.plots": {"en": "Plots", "lv": "Grafiki"},
    "btn.export_csv": {"en": "Export CSV", "lv": "Eksportēt CSV"},
    "btn.prev_page": {"en": "\u2190 Previous 5,000", "lv": "\u2190 Iepriekšējie 5 000"},
    "btn.next_page": {"en": "Next 5,000 \u2192", "lv": "Nākamie 5 000 \u2192"},
    "btn.clear_map": {"en": "Clear map selection", "lv": "Notīrīt kartes atlasi"},
    "btn.no_region": {"en": "No region (N/A)", "lv": "Nav reģiona (N/A)"},

    # Search
    "search.match_label": {"en": "Match: ", "lv": "Atbilstība: "},
    "search.any": {"en": "Any", "lv": "Jebkurš"},
    "search.all": {"en": "All", "lv": "Visi"},

    # Selection mode
    "slicer.mode_label": {"en": "Selection mode: ", "lv": "Atlases režīms: "},
    "slicer.multi": {"en": "Multi-select", "lv": "Vairāku atlase"},
    "slicer.single": {"en": "Single-select", "lv": "Viena atlase"},

    # Panel header
    "panel.loading": {"en": "Loading additional features...", "lv": "Ielādē papildu funkcijas..."},
    "panel.buildings_shown": {"en": "{n} buildings shown", "lv": "{n} ēkas rādītas"},
    "buildings": {"en": "buildings", "lv": "ēkas"},

    # Detail panel
    "detail.building_details": {"en": "Building Details", "lv": "Ēkas detaļas"},

    # Dataset mode
    "dataset.full": {"en": "Full residential (380k)", "lv": "Pilnas dzīvojamās (380k)"},
    "dataset.epc_only": {"en": "EPC only (23k)", "lv": "Tikai EPC (23k)"},

    # Plot checklist labels
    "plot.checklist.epc": {"en": "EPC Class Distribution", "lv": "EPC klašu sadalījums"},
    "plot.checklist.era": {"en": "Construction Era Distribution", "lv": "Būvniecības periodu sadalījums"},
    "plot.checklist.wall": {"en": "Wall Material Distribution", "lv": "Sienu materiālu sadalījums"},
    "plot.checklist.avg_energy": {"en": "Average Heating Energy", "lv": "Vidējā apkures enerģija"},
    "plot.ref_label": {"en": "Show full-sample reference", "lv": "Rādīt pilnas izlases atsauci"},

    # Column selector
    "cols.select_help": {"en": "Select columns to show in the table.", "lv": "Izvēlieties kolonnas rādīšanai tabulā."},
}


def t(key: str, lang: str = "en") -> str:
    """Get translated string. Falls back to English if key/lang missing."""
    entry = _STRINGS.get(key)
    if entry is None:
        return key
    return entry.get(lang, entry.get("en", key))


def get_all_keys() -> list[str]:
    """Return all translation keys."""
    return list(_STRINGS.keys())
