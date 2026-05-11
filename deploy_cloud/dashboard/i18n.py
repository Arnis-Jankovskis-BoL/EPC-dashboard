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
    "map.tooltip": {"en": "Change map view", "lv": "Mainīt kartes skatu"},
    "map.section_map": {"en": "Map", "lv": "Karte"},
    "map.section_size": {"en": "Size", "lv": "Izmērs"},
    "map.size_normal": {"en": "Normal", "lv": "Normāls"},
    "map.size_large": {"en": "Large", "lv": "Liels"},

    # Plots
    "plot.epc_dist": {"en": "EPC Class Distribution", "lv": "EPC klašu sadalījums"},
    "plot.era_dist": {"en": "Construction Era Distribution", "lv": "Būvniecības periodu sadalījums"},
    "plot.wall_dist": {"en": "Wall Material Distribution", "lv": "Sienu materiālu sadalījums"},
    "plot.avg_energy": {"en": "Average Heating Energy", "lv": "Vidējā apkures enerģija"},
    "plot.ref_toggle": {"en": "Show full-sample reference", "lv": "Rādīt pilnas izlases atsauci"},
    "plot.epc_label": {"en": "EPC Class", "lv": "EPC klase"},
    "plot.era_label": {"en": "Construction Era", "lv": "Būvniecības periods"},
    "plot.wall_label": {"en": "Wall Material", "lv": "Sienu materiāls"},
    "plot.floor_label": {"en": "Floor Count", "lv": "Stāvu skaits"},
    "plot.primary_energy_label": {"en": "Primary Energy Percentile Distribution", "lv": "Primārās enerģijas procentīļu sadalījums"},
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
    "btn.maps": {"en": "Maps", "lv": "Kartes"},
    "btn.export_csv": {"en": "Export CSV", "lv": "Eksportēt CSV"},
    "btn.prev_page": {"en": "\u2190 Previous", "lv": "\u2190 Iepriekšējie"},
    "btn.next_page": {"en": "Next \u2192", "lv": "Nākamie \u2192"},
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
    "plot.checklist.floor": {"en": "Floor Count Distribution", "lv": "Stāvu sadalījums"},
    "plot.checklist.primary_energy": {"en": "Primary Energy Distribution", "lv": "Primārās enerģijas sadalījums"},
    "plot.ref_label": {"en": "Show full-sample reference", "lv": "Rādīt pilnas izlases atsauci"},

    # Column selector
    "cols.select_help": {"en": "Select columns to show in the table.", "lv": "Izvēlieties kolonnas rādīšanai tabulā."},

    # Column block labels
    "block.identification": {"en": "Identification", "lv": "Identifikācija"},
    "block.location": {"en": "Location", "lv": "Atrašanās vieta"},
    "block.energy": {"en": "Energy", "lv": "Enerģija"},
    "block.physical": {"en": "Physical", "lv": "Fiziskās īpašības"},
    "block.heating_renovation": {"en": "Heating & Renovation", "lv": "Apkure un atjaunošana"},

    # Slicer labels
    "slicer.epc_label": {"en": "EPC Class: ", "lv": "EPC klase: "},
    "slicer.era_label": {"en": "Era: ", "lv": "Periods: "},
    "slicer.floor_label": {"en": "Floors: ", "lv": "Stāvi: "},
    "slicer.wall_label": {"en": "Wall: ", "lv": "Sienas: "},
    "slicer.type_label": {"en": "Type: ", "lv": "Ēkas tips: "},

    # Wall material translations (filter buttons)
    "wall.wood": {"en": "Wood", "lv": "Koks"},
    "wall.brick_stone": {"en": "Brick and stone", "lv": "Ķieģeļi un akmens"},
    "wall.concrete": {"en": "Concrete", "lv": "Betons"},
    "wall.lightweight_concrete": {"en": "Lightweight concrete", "lv": "Vieglais betons"},
    "wall.metal_glass": {"en": "Metal and glass", "lv": "Metāls un stikls"},
    "wall.other": {"en": "Other", "lv": "Cits"},

    # Slicer all button
    "slicer.all_btn": {"en": "All", "lv": "Visi"},

    # Tooltips
    "tooltip.search": {
        "en": "Type a search term and press Enter to add it as a filter chip. Add multiple terms — use the Any/All toggle below to control matching.",
        "lv": "Ievadiet meklēšanas vārdu un nospiediet Enter, lai pievienotu filtru. Pievienojiet vairākus vārdus — izmantojiet Jebkurš/Visi pārslēgu.",
    },
    "tooltip.search_mode": {
        "en": "Any: show buildings matching at least one search term. All: show only buildings matching every search term.",
        "lv": "Jebkurš: rāda ēkas, kas atbilst vismaz vienam vārdam. Visi: rāda tikai ēkas, kas atbilst visiem vārdiem.",
    },
    "tooltip.slicer_mode": {
        "en": "Multi-select: toggle individual filters on/off. Single-select: clicking a filter deselects all others.",
        "lv": "Vairāku atlase: ieslēdziet/izslēdziet atsevišķus filtrus. Viena atlase: noklikšķinot filtru, pārējie tiek atcelti.",
    },
    "tooltip.ref_line": {
        "en": "When ON, dashed outlines show the full-sample distribution for comparison.",
        "lv": "Kad ieslēgts, punktētas kontūras rāda pilnas izlases sadalījumu salīdzināšanai.",
    },

    # Chart tooltips
    "tooltip.epc_chart": {"en": "EPC class distribution of filtered buildings.", "lv": "EPC klašu sadalījums filtrētajām ēkām."},
    "tooltip.era_chart": {"en": "Construction era distribution of filtered buildings.", "lv": "Būvniecības periodu sadalījums filtrētajām ēkām."},
    "tooltip.wall_chart": {"en": "Wall material distribution of filtered buildings.", "lv": "Sienu materiālu sadalījums filtrētajām ēkām."},
    "tooltip.energy_chart": {"en": "Average heating energy of filtered buildings vs full sample.", "lv": "Vidējā apkures enerģija filtrētajām ēkām salīdzinājumā ar pilnu izlasi."},

    # Filter breakdown step labels
    "filter.epc_step": {"en": "EPC", "lv": "EPC"},
    "filter.era_step": {"en": "Era", "lv": "Periods"},
    "filter.floor_step": {"en": "Floors", "lv": "Stāvi"},
    "filter.wall_step": {"en": "Wall", "lv": "Sienas"},
    "filter.type_step": {"en": "Building type", "lv": "Ēkas tips"},
    "filter.map_step": {"en": "Map", "lv": "Karte"},
    "filter.search_step": {"en": "search", "lv": "meklēšana"},
    "filter.no_region": {"en": "No region (N/A)", "lv": "Nav reģiona (N/A)"},

    # Page size
    "page.size_tooltip": {"en": "Page size. Larger values may increase loading time.", "lv": "Lapas izmērs. Lielākas vērtības var palielināt ielādes laiku."},

    # Custom sample panel
    "btn.custom_sample": {"en": "Custom Sample", "lv": "Pielāgota izlase"},
    "custom.heading": {"en": "Custom Sample", "lv": "Pielāgota izlase"},
    "custom.help": {
        "en": "Paste cadastral designations (14-digit numbers) to filter the dataset. "
              "Up to 10,000 designations. Accepted separators: comma, semicolon, space, tab, newline.",
        "lv": "Ielīmējiet kadastra apzīmējumus (14 ciparu numurus), lai filtrētu datu kopu. "
              "Līdz 10 000 apzīmējumiem. Pieņemtie atdalītāji: komats, semikols, atstarpe, tabulācija, jauna rinda.",
    },
    "custom.placeholder": {
        "en": "Paste designations here...\ne.g. 01001280293001, 01000580157004",
        "lv": "Ielīmējiet apzīmējumus šeit...\npiem. 01001280293001, 01000580157004",
    },
    "custom.load_btn": {"en": "Load custom sample", "lv": "Ielādēt pielāgoto izlasi"},
    "custom.add_btn": {"en": "Add to current list", "lv": "Pievienot esošajam sarakstam"},
    "custom.clear_btn": {"en": "Clear custom sample", "lv": "Notīrīt pielāgoto izlasi"},
    "custom.format_help_link": {"en": "Show accepted formats", "lv": "Rādīt pieņemtos formātus"},
    "custom.format_help": {
        "en": "Accepted formats:\n"
              "• Comma-separated: 01001280293001, 01000580157004\n"
              "• Semicolon-separated: 01001280293001; 01000580157004\n"
              "• Space-separated: 01001280293001 01000580157004\n"
              "• Tab-separated (paste from Excel row)\n"
              "• One per line (paste from Excel column or Word table)\n"
              "• Mixed separators are allowed\n"
              "• Each designation must be exactly 14 digits",
        "lv": "Pieņemtie formāti:\n"
              "• Ar komatu: 01001280293001, 01000580157004\n"
              "• Ar semikolu: 01001280293001; 01000580157004\n"
              "• Ar atstarpi: 01001280293001 01000580157004\n"
              "• Ar tabulāciju (ielīmēts no Excel rindas)\n"
              "• Pa vienai rindā (ielīmēts no Excel kolonnas vai Word tabulas)\n"
              "• Jaukti atdalītāji ir atļauti\n"
              "• Katram apzīmējumam jābūt tieši 14 cipariem",
    },
    "custom.warn_clear_filters": {
        "en": "Loading a custom sample will clear all active filters (EPC class, era, wall material, map selection, search). Continue?",
        "lv": "Pielāgotas izlases ielāde notīrīs visus aktīvos filtrus (EPC klase, periods, sienu materiāls, kartes atlase, meklēšana). Turpināt?",
    },
    "custom.result_success": {
        "en": "Custom sample loaded: {matched} of {total} designations matched ({pct}%).\n"
              "{not_found} not found in dataset, {invalid} invalid format.",
        "lv": "Pielāgotā izlase ielādēta: {matched} no {total} apzīmējumiem atrasti ({pct}%).\n"
              "{not_found} nav atrasti datu kopā, {invalid} nederīgā formātā.",
    },
    "custom.result_added": {
        "en": "Added to custom sample: {matched} new matches of {total} pasted.\n"
              "Total custom sample: {grand_total} designations.\n"
              "{not_found} not found, {invalid} invalid format.",
        "lv": "Pievienots pielāgotajai izlasei: {matched} jauni atbilstošie no {total} ielīmētajiem.\n"
              "Kopējā pielāgotā izlase: {grand_total} apzīmējumi.\n"
              "{not_found} nav atrasti, {invalid} nederīgā formātā.",
    },
    "custom.validate_warn": {
        "en": "{n} of {total} pasted designations have invalid format. Proceed anyway?",
        "lv": "{n} no {total} ielīmētajiem apzīmējumiem ir nederīgā formātā. Turpināt?",
    },
    "custom.show_invalid": {"en": "Show invalid entries", "lv": "Rādīt nederīgos ierakstus"},
    "custom.active_badge": {"en": "Custom sample: {n} designations", "lv": "Pielāgotā izlase: {n} apzīmējumi"},
    "filter.custom_step": {"en": "Custom sample", "lv": "Pielāgotā izlase"},

    # Download modal
    "btn.download_data": {"en": "Download data", "lv": "Lejupielādēt datus"},
    "download.title": {"en": "Download Data", "lv": "Lejupielādēt datus"},
    "download.format": {"en": "Format", "lv": "Formāts"},
    "download.separator": {"en": "CSV separator", "lv": "CSV atdalītājs"},
    "download.rows": {"en": "Rows", "lv": "Rindas"},
    "download.rows_filtered": {"en": "Currently filtered rows", "lv": "Pašlaik filtrētās rindas"},
    "download.rows_all": {"en": "Full dataset", "lv": "Pilna datu kopa"},
    "download.cols": {"en": "Columns", "lv": "Kolonnas"},
    "download.cols_visible": {"en": "Currently visible columns", "lv": "Pašlaik redzamās kolonnas"},
    "download.cols_all": {"en": "All available columns", "lv": "Visas pieejamās kolonnas"},
    "download.cols_custom": {"en": "Custom selection...", "lv": "Pielāgota izvēle..."},
    "download.btn": {"en": "Download", "lv": "Lejupielādēt"},
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
