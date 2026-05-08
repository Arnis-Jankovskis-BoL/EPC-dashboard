"""Column metadata — display names and tooltips for dashboard columns."""

from __future__ import annotations

# Mapping: database_column -> (display_name, tooltip)
# Tooltip should be max 1 sentence, useful for non-technical colleagues.
COLUMN_META: dict[str, tuple[str, str]] = {
    "KadastraApzimBuilding": (
        "Cadastral Designation",
        "Unique building identifier in the Latvian State Cadastre (e.g. 01000712428001).",
    ),
    "Town_Parish": (
        "Town / Parish",
        "Municipality or parish where the building is located (pre-2021 admin units).",
    ),
    "Street": (
        "Street",
        "Street name from the EPC certificate address.",
    ),
    "House": (
        "House Nr.",
        "House or building number on the street.",
    ),
    "Adrese": (
        "Full Address",
        "Complete address string as recorded in the EPC certificate.",
    ),
    "building_type": (
        "Building Type",
        "Residential category: Individual house, Apartment building, Terraced/Row house, or Other.",
    ),
    "construction_year": (
        "Construction Year",
        "Year the building was originally constructed (cleaned from multiple sources).",
    ),
    "EnergoefektivKlase": (
        "EPC Class (Certificate)",
        "Energy performance class (A–F) from the EPC certificate, using the regulation in force at certification time.",
    ),
    "EnergoefektivKlase_georiga_pref": (
        "EPC Class (GeoRiga Preferred)",
        "EPC class preferring GeoRiga value when both sources overlap; falls back to certificate value.",
    ),
    "EnergijaApkurei": (
        "Heating Energy (kWh/m²/yr)",
        "Specific energy consumption for heating per square metre per year, from the EPC certificate.",
    ),
    "EnergijaApkurei_georiga_pref": (
        "Heating Energy (GeoRiga Preferred)",
        "Heating energy preferring GeoRiga value when both sources overlap.",
    ),
    "PrimaraNeatjaunojamaEnergija": (
        "Primary Non-Renewable Energy",
        "Non-renewable primary energy from EPC certificate (kWh/m²/yr). Available in newer certificates only.",
    ),
    "estimated_primary_energy": (
        "Primary Energy (Est.)",
        "Non-renewable primary energy: actual from certificate if available, otherwise estimated via linear model (1.41×heating+34.18, R²=0.65).",
    ),
    "eu_taxonomy_top15": (
        "EU Taxonomy Top 15%",
        "True if building's primary energy \u2264141.8 kWh/m\xb2/yr (top 15% lowest consumption threshold).",
    ),
    "primary_energy_pctile": (
        "Energy Percentile (All)",
        "Percentile rank of primary energy among all buildings (lower = more efficient). E.g. 12.5 means top 12.5%.",
    ),
    "primary_energy_pctile_type": (
        "Energy Percentile (Type)",
        "Percentile rank of primary energy within same building type (individual house or apartment).",
    ),
    "predicted_epc_class": (
        "Predicted EPC Class",
        "Model-predicted EPC class (A-F) for the building. Available for full residential dataset.",
    ),
    "predicted_heating_kwh": (
        "Predicted Heating (kWh/m\u00b2/yr)",
        "Model-predicted heating energy consumption. Available for full residential dataset.",
    ),
    "source": (
        "Data Source",
        "Origin of the record: 'epc' = EPC certificate only, 'georiga' = GeoRiga cadastre data, 'both' = merged.",
    ),
    "DokNr": (
        "EPC Certificate Nr.",
        "Document number of the EPC certificate (e.g., BIS/ĒED-2-2016-1).",
    ),
    "address_mismatch": (
        "Address Mismatch",
        "True if Street + House Nr. doesn't match the Adrese field (possible data quality issue).",
    ),
    "estimated_from_address": (
        "Estimated from Address",
        "True if Town/Parish, Street, or House were estimated from the Adrese field (audit column).",
    ),
    "cert_date": (
        "Certificate Date",
        "Date the EPC certificate was issued.",
    ),
    "cert_year": (
        "Certificate Year",
        "Year the EPC certificate was issued (integer).",
    ),
    "postal_code_clean": (
        "Postal Code",
        "Cleaned postal code (LV-XXXX format).",
    ),
    "BuildingArea": (
        "Total Area (m²)",
        "Total building area including non-heated spaces, from Cadastre.",
    ),
    "ReferencesPlatiba": (
        "Reference Area (m²)",
        "Heated reference floor area per ISO 52000-1:2020, used for EPC class thresholds.",
    ),
    "BuildingDeprecation": (
        "Depreciation Group",
        "Physical condition: V1=Very good (0–12%), V2=Good (13–32%), V3=Satisfactory (33–52%), V4=Unsatisfactory (53–84%), V5=Critical (85–100%).",
    ),
    "wall_material_grouped": (
        "Wall Material",
        "Grouped wall construction: Brick, Panel (prefab concrete), Monolith, Wood, Blocks, Mixed, Other.",
    ),
    "ekas_veids_grouped": (
        "Building Form",
        "Grouped building form/purpose from Cadastre classification code.",
    ),
    "era_bin": (
        "Construction Era",
        "Regulation-based era: Pre-1945, 1946–1960, 1961–1990, 1991–2002, 2003–2014, 2015–2020, 2021+.",
    ),
    "Valstspilsetas": (
        "State City",
        "If the building is in one of 10 Latvian state cities (Rīga, Daugavpils, Liepāja, etc.); empty otherwise.",
    ),
    "Parish": (
        "Parish",
        "Administrative parish (pagasts) for rural buildings; empty for state cities.",
    ),
    "BuildingGroundFloors": (
        "Floors Above Ground",
        "Number of above-ground storeys from the Cadastre.",
    ),
    "BuildingExploitYear": (
        "Exploitation Year",
        "Year the building was put into operation, from Cadastre (may differ from construction year).",
    ),
    # --- New columns from featured parquet ---
    "area_band": (
        "Area Band",
        "Regulatory heated-area band for EPC thresholds: 50–120 m², 120–250 m², >250 m².",
    ),
    "apartment_count": (
        "Apartment Count",
        "Number of apartments in the building, from Cadaster open data.",
    ),
    "building_volume_m3": (
        "Volume (m³)",
        "Building volume from Cadaster open data.",
    ),
    "underground_floors": (
        "Underground Floors",
        "Number of underground (basement) storeys.",
    ),
    "footprint_area_m2": (
        "Footprint (m²)",
        "Building ground-floor footprint area from Cadaster.",
    ),
    "wwr_archetype": (
        "Window-Wall Ratio",
        "Archetype window-to-wall ratio group based on building era and type.",
    ),
    "estimated_wall_U": (
        "Wall U-value",
        "Estimated thermal transmittance of walls (W/m²K) based on construction era.",
    ),
    "estimated_window_U": (
        "Window U-value",
        "Estimated thermal transmittance of windows (W/m²K) based on era.",
    ),
    "estimated_roof_U": (
        "Roof U-value",
        "Estimated thermal transmittance of roof (W/m²K) based on era.",
    ),
    "volume_per_apartment": (
        "Vol / Apartment",
        "Building volume divided by apartment count (m³).",
    ),
    "area_per_apartment": (
        "Area / Apartment",
        "Total building area divided by apartment count (m²).",
    ),
    "heating_type_grouped": (
        "Heating Type",
        "Grouped heating type: Central, Individual, Mixed, Other.",
    ),
    "district_heating_flag": (
        "District Heating",
        "Whether the building is connected to a district heating network.",
    ),
    "is_renovated_before_epc": (
        "Renovated Before EPC",
        "Whether a renovation was completed before the EPC certificate date.",
    ),
    "renovation_count": (
        "Renovation Count",
        "Number of renovations detected from element year data.",
    ),
    "renovation_detected": (
        "Renovation Detected",
        "Whether any renovation has been detected for this building.",
    ),
    "years_since_renovation": (
        "Years Since Renovation",
        "Years elapsed since the most recent renovation.",
    ),
    "partial_renovation_flag": (
        "Partial Renovation",
        "Whether the building had a partial (not full) renovation.",
    ),
    "statistical_region": (
        "Statistical Region",
        "CSP statistical region: Rīga, Pierīga, Vidzeme, Kurzeme, Zemgale, Latgale.",
    ),
    "gis_territory_name": (
        "GIS Territory",
        "Administrative territory derived from GIS spatial join (post-2021 reform).",
    ),
    "apkaime_name": (
        "Neighbourhood",
        "Neighbourhood name for Rīga (58) and Daugavpils (25) from spatial join; empty for other cities.",
    ),
}

# Latvian translations — (display_name_lv, tooltip_lv)
COLUMN_META_LV: dict[str, tuple[str, str]] = {
    "KadastraApzimBuilding": ("Kadastra apzīmējums", "Unikāls ēkas identifikators Latvijas Valsts kadastrā."),
    "Town_Parish": ("Pilsēta / pagasts", "Pašvaldība vai pagasts, kurā atrodas ēka."),
    "Street": ("Iela", "Ielas nosaukums no EPC sertifikāta adreses."),
    "House": ("Mājas Nr.", "Mājas vai ēkas numurs uz ielas."),
    "Adrese": ("Pilna adrese", "Pilna adreses virkne no EPC sertifikāta."),
    "building_type": ("Ēkas tips", "Dzīvojamā kategorija: individuālā māja, daudzdzīvokļu, rindu māja vai cita."),
    "construction_year": ("Būvniecības gads", "Ēkas sākotnējais būvniecības gads (attīrīts no vairākiem avotiem)."),
    "EnergoefektivKlase": ("EPC klase (sertifikāts)", "Energoefektivitātes klase (A–F) no EPC sertifikāta."),
    "EnergoefektivKlase_georiga_pref": ("EPC klase (GeoRiga pref.)", "EPC klase, dodot priekšroku GeoRiga vērtībai."),
    "EnergijaApkurei": ("Apkures enerģija (kWh/m²/g.)", "Īpatnējais enerģijas patēriņš apkurei uz m² gadā."),
    "EnergijaApkurei_georiga_pref": ("Apkures enerģija (GeoRiga pref.)", "Apkures enerģija, dodot priekšroku GeoRiga vērtībai."),
    "PrimaraNeatjaunojamaEnergija": ("Primārā neatjaunojamā enerģija", "Neatjaunojamā primārā enerģija no sertifikāta (kWh/m²/g.)."),
    "estimated_primary_energy": ("Primārā enerģija (apr.)", "Primārā enerģija: faktiskā vai aprēķināta ar lineāro modeli."),
    "eu_taxonomy_top15": ("ES taksonomija Top 15%", "Vai ēkas primārā enerģija ir zemāko 15% vidū."),
    "primary_energy_pctile": ("Enerģ. procentile (visi)", "Primārās enerģijas procentile starp visām ēkām."),
    "primary_energy_pctile_type": ("Enerģ. procentile (tips)", "Primārās enerģijas procentile starp tāda paša tipa ēkām."),
    "predicted_epc_class": ("Prognozētā EPC klase", "Modeļa prognozētā EPC klase (A–F)."),
    "predicted_heating_kwh": ("Prognozētā apkure (kWh/m²/g.)", "Modeļa prognozētais apkures enerģijas patēriņš."),
    "source": ("Datu avots", "Ieraksta izcelsme: 'epc', 'georiga' vai 'both'."),
    "DokNr": ("EPC sertifikāta Nr.", "EPC sertifikāta dokumenta numurs."),
    "address_mismatch": ("Adreses neatbilstība", "Vai iela+nr. neatbilst Adrese laukam."),
    "estimated_from_address": ("Aprēķināts no adreses", "Vai pilsēta/iela/nr. tika aprēķināti no Adrese lauka."),
    "cert_date": ("Sertifikāta datums", "EPC sertifikāta izsniegšanas datums."),
    "cert_year": ("Sertifikāta gads", "EPC sertifikāta izsniegšanas gads."),
    "postal_code_clean": ("Pasta indekss", "Attīrīts pasta indekss (LV-XXXX formāts)."),
    "BuildingArea": ("Kopējā platība (m²)", "Kopējā ēkas platība, ieskaitot neapsildāmās telpas."),
    "ReferencesPlatiba": ("Atsauces platība (m²)", "Apsildāmā atsauces platība pēc ISO 52000-1:2020."),
    "BuildingDeprecation": ("Nolietojuma grupa", "Fiziskais stāvoklis: V1=Ļoti labs, V2=Labs, V3=Apmierinošs, V4=Neapmierinošs, V5=Kritisks."),
    "wall_material_grouped": ("Sienu materiāls", "Grupēts sienu materiāls: ķieģelis, panelis, monolīts, koks u.c."),
    "ekas_veids_grouped": ("Ēkas forma", "Grupēta ēkas forma/mērķis no kadastra klasifikācijas."),
    "era_bin": ("Būvniecības periods", "Regulējuma periods: pirms 1945, 1946–1960, 1961–1990 u.c."),
    "Valstspilsetas": ("Valstspilsēta", "Vai ēka atrodas kādā no 10 Latvijas valstspilsētām."),
    "Parish": ("Pagasts", "Administratīvais pagasts lauku ēkām."),
    "BuildingGroundFloors": ("Virszemes stāvi", "Virszemes stāvu skaits no kadastra."),
    "BuildingExploitYear": ("Ekspluatācijas gads", "Gads, kad ēka nodota ekspluatācijā."),
    "area_band": ("Platības josla", "Regulējuma platības josla EPC sliekšņiem."),
    "apartment_count": ("Dzīvokļu skaits", "Dzīvokļu skaits ēkā no kadastra."),
    "building_volume_m3": ("Tilpums (m³)", "Ēkas tilpums no kadastra."),
    "underground_floors": ("Pagraba stāvi", "Pazemes stāvu skaits."),
    "footprint_area_m2": ("Apbūves laukums (m²)", "Ēkas 1. stāva apbūves laukums."),
    "wwr_archetype": ("Logu-sienu attiecība", "Arhetipiskā logu-sienu attiecība pēc ēras un tipa."),
    "estimated_wall_U": ("Sienu U-vērtība", "Aprēķinātā sienu siltumpārvade (W/m²K)."),
    "estimated_window_U": ("Logu U-vērtība", "Aprēķinātā logu siltumpārvade (W/m²K)."),
    "estimated_roof_U": ("Jumta U-vērtība", "Aprēķinātā jumta siltumpārvade (W/m²K)."),
    "volume_per_apartment": ("Tilp. / dzīvoklis", "Ēkas tilpums dalīts ar dzīvokļu skaitu (m³)."),
    "area_per_apartment": ("Plat. / dzīvoklis", "Kopējā platība dalīta ar dzīvokļu skaitu (m²)."),
    "heating_type_grouped": ("Apkures tips", "Grupēts apkures tips: centrālā, individuālā, jaukta, cita."),
    "district_heating_flag": ("Centralizētā apkure", "Vai ēka pieslēgta centralizētajai siltumapgādei."),
    "is_renovated_before_epc": ("Renovēta pirms EPC", "Vai renovācija pabeigta pirms EPC sertifikāta."),
    "renovation_count": ("Renovāciju skaits", "Konstatēto renovāciju skaits."),
    "renovation_detected": ("Renovācija konstatēta", "Vai ēkai konstatēta kāda renovācija."),
    "years_since_renovation": ("Gadi kopš renovācijas", "Gadi kopš pēdējās renovācijas."),
    "partial_renovation_flag": ("Daļēja renovācija", "Vai ēkā bijusi daļēja (ne pilna) renovācija."),
    "statistical_region": ("Statistiskais reģions", "CSP statistiskais reģions: Rīga, Pierīga, Vidzeme, Kurzeme, Zemgale, Latgale."),
    "gis_territory_name": ("ĢIS teritorija", "Administratīvā teritorija no ĢIS (pēc 2021. gada reformas)."),
    "apkaime_name": ("Apkaime", "Apkaimes nosaukums Rīgai un Daugavpilij."),
    "combined_epc_class": ("Apvienotā EPC klase", "EPC klase no sertifikāta vai GeoRiga (apvienota)."),
    "combined_heating_kwh": ("Apvienotā apkure (kWh/m²/g.)", "Apkures enerģija no sertifikāta vai GeoRiga (apvienota)."),
}


def get_display_name(col: str, lang: str = "en") -> str:
    """Return the human-readable display name for a column."""
    if lang == "lv" and col in COLUMN_META_LV:
        return COLUMN_META_LV[col][0]
    if col in COLUMN_META:
        return COLUMN_META[col][0]
    return col.replace("_", " ").title()


def get_tooltip(col: str, lang: str = "en") -> str:
    """Return the tooltip description for a column."""
    if lang == "lv" and col in COLUMN_META_LV:
        return COLUMN_META_LV[col][1]
    if col in COLUMN_META:
        return COLUMN_META[col][1]
    return ""


# ---------------------------------------------------------------------------
# Filter type overrides
# AG Grid Community filter types: agTextColumnFilter, agNumberColumnFilter,
#   agDateColumnFilter. (agSetColumnFilter requires Enterprise license.)
# For categorical columns, we use agTextColumnFilter (community) which still
# provides contains/equals/startsWith filtering.
# ---------------------------------------------------------------------------
FILTER_TYPE_OVERRIDE: dict[str, str] = {
    # Numeric columns → number filter (range, >, <, equals)
    "construction_year": "agNumberColumnFilter",
    "EnergijaApkurei": "agNumberColumnFilter",
    "EnergijaApkurei_georiga_pref": "agNumberColumnFilter",
    "BuildingArea": "agNumberColumnFilter",
    "ReferencesPlatiba": "agNumberColumnFilter",
    "BuildingGroundFloors": "agNumberColumnFilter",
    "BuildingExploitYear": "agNumberColumnFilter",
    "cert_year": "agNumberColumnFilter",
    "apartment_count": "agNumberColumnFilter",
    "building_volume_m3": "agNumberColumnFilter",
    "underground_floors": "agNumberColumnFilter",
    "footprint_area_m2": "agNumberColumnFilter",
    "estimated_wall_U": "agNumberColumnFilter",
    "estimated_window_U": "agNumberColumnFilter",
    "estimated_roof_U": "agNumberColumnFilter",
    "volume_per_apartment": "agNumberColumnFilter",
    "area_per_apartment": "agNumberColumnFilter",
    "renovation_count": "agNumberColumnFilter",
    "years_since_renovation": "agNumberColumnFilter",
    "PrimaraNeatjaunojamaEnergija": "agNumberColumnFilter",
    "estimated_primary_energy": "agNumberColumnFilter",
    "primary_energy_pctile": "agNumberColumnFilter",
    "primary_energy_pctile_type": "agNumberColumnFilter",
    "predicted_heating_kwh": "agNumberColumnFilter",
    # Date
    "cert_date": "agDateColumnFilter",
    # Everything else defaults to agTextColumnFilter (auto-assigned below)
}


def get_filter_type(col: str, dtype_str: str = "") -> str:
    """Return the AG Grid filter type for a column.

    Uses explicit override if available, otherwise infers from pandas dtype.
    Only uses Community-edition filter types.
    """
    if col in FILTER_TYPE_OVERRIDE:
        return FILTER_TYPE_OVERRIDE[col]
    # Auto-assign by dtype
    if "int" in dtype_str or "float" in dtype_str:
        return "agNumberColumnFilter"
    if "datetime" in dtype_str:
        return "agDateColumnFilter"
    return "agTextColumnFilter"

