"""
Verdex — Carbon emissions optimisation engine.

Methodology aligned with GHG Protocol Corporate Standard, IPCC AR6
emission factors, IEA country grid factors, DEFRA conversion factors,
and the HIGH Horizons D3.7 intervention catalogue
(DOI: 10.5281/zenodo.12730527).

Three-scenario optimisation: full coverage, fixed budget, optimised
(greedy knapsack ranking by tCO₂e reduced per USD).
"""
from datetime import date
from decimal import Decimal, ROUND_CEILING

# ---------------------------------------------------------------------------
# Country-specific electricity costs (USD / kWh)
# Sources: ZESA (ZW), Eskom standard tariff (ZA), Kenya Power residential (KE)
# ---------------------------------------------------------------------------
ELECTRICITY_COSTS = {
    # Sub-Saharan Africa
    'ZW': Decimal('0.098'),     # ZESA standard tariff
    'ZA': Decimal('0.131'),     # Eskom standard tariff
    'KE': Decimal('0.117'),     # Kenya Power residential
    'TZ': Decimal('0.105'),     # TANESCO commercial avg
    'UG': Decimal('0.165'),     # UMEME commercial
    'NG': Decimal('0.082'),     # NESI Band A average
    'GH': Decimal('0.110'),     # ECG non-residential
    # South Asia
    'IN': Decimal('0.085'),     # Indian commercial avg (state-weighted)
    'BD': Decimal('0.075'),     # BPDB commercial
    # Donor / OECD
    'GB': Decimal('0.380'),     # UK commercial 2024 (post-2022 spike)
    'US': Decimal('0.130'),     # US commercial avg (EIA 2024)
    'EU': Decimal('0.220'),     # EU commercial avg (Eurostat 2024)
    'DEFAULT': Decimal('0.12'),
}

CARBON_CREDIT_PRICE_USD = Decimal('15.00')

# LMIC public-sector discount rate (8 % reflects typical government borrowing)
DISCOUNT_RATE = Decimal('0.08')


# ---------------------------------------------------------------------------
# Emission conversion factors: raw usage units → tCO₂e
#
# Sources:
#   Electricity  — IEA World Energy Outlook 2022 country emission factors
#   Combustion   — GHG Protocol / UK BEIS 2023 conversion factors
#   Gases        — IPCC AR6 GWP₁₀₀ values (CH₄ = 29.8, N₂O = 273)
#   Travel       — UK DEFRA 2022 (average medium car, diesel)
#   Inhalers     — NHS England / BEIS 2023 (pMDI HFC-134a propellant)
#   Anaesthetics — weighted average: isoflurane (GWP 510, 50 %), sevoflurane
#                  (GWP 130, 30 %), desflurane (GWP 2540, 20 %)
#   Refrigerants — average HFC blend (R-410A GWP 2088, R-134a 1430, R-22 1810)
#   Waste        — DEFRA 2022 mixed clinical-waste treatment (landfill/incineration)
#   Contractor   — DEFRA 2022 average diesel logistics vehicle
# ---------------------------------------------------------------------------

ELECTRICITY_EF = {          # tCO₂e per kWh of grid electricity consumed
    # Sources: IEA 2023 emission factors; Climate Transparency country reports;
    # national grid operators where available.
    # Sub-Saharan Africa
    'ZW':    Decimal('0.000556'),   # Zimbabwe  — coal-dominated ZESA grid
    'ZA':    Decimal('0.000928'),   # S. Africa — Eskom ≈ 85 % coal
    'KE':    Decimal('0.000032'),   # Kenya     — > 90 % renewables (geothermal + hydro)
    'TZ':    Decimal('0.000300'),   # Tanzania  — gas + hydro mix
    'UG':    Decimal('0.000040'),   # Uganda    — > 90 % hydro
    'NG':    Decimal('0.000395'),   # Nigeria   — gas-heavy
    'GH':    Decimal('0.000395'),   # Ghana     — gas + hydro
    # South Asia
    'IN':    Decimal('0.000810'),   # India     — coal-heavy (CEA 2023)
    'BD':    Decimal('0.000620'),   # Bangladesh — gas-dominated
    # Donor / OECD
    'GB':    Decimal('0.000200'),   # UK        — renewables + gas (DEFRA 2023)
    'US':    Decimal('0.000390'),   # US        — mixed grid (EPA eGRID 2023)
    'EU':    Decimal('0.000235'),   # EU avg    — renewables-heavy (EEA 2024)
    'OTHER': Decimal('0.000400'),   # Catch-all SSA-leaning default
}

EMISSION_FACTORS = {
    # field_name: tCO₂e per unit (unit shown in parentheses)
    'grid_electricity':    None,                  # country-specific — see ELECTRICITY_EF
    'grid_gas':            Decimal('0.00202'),    # per m³ natural gas (DEFRA 2023: 2.02633 kg/m³)
    'bottled_gas':         Decimal('0.00294'),    # per kg LPG (DEFRA 2023: 2.93921 kg/kg)
    'liquid_fuel':         Decimal('0.00268'),    # per litre mineral diesel (DEFRA 2023: 2.68779 kg/L
                                                 # — mineral, not B7 blend; LMIC pump diesel)
    'vehicle_fuel_owned':  Decimal('0.00268'),    # per litre (owned fleet, mineral diesel)
    'business_travel':     Decimal('0.000171'),   # per km (DEFRA 2023 average car, unknown fuel)
    'anaesthetic_gases':   Decimal('0.802'),      # per kg agent (GWP₁₀₀ mix: 50% isoflurane 510,
                                                 # 30% sevoflurane 130, 20% desflurane 2540 —
                                                 # Sulbaek Andersen et al. 2010 / IPCC)
    'refrigeration_gases': Decimal('1.800'),      # per kg refrigerant lost (average HFC blend:
                                                 # R-410A 2088, R-134a 1430, R-22 1810)
    'waste_management':    None,                  # sector-specific — see WASTE_EF
    'medical_inhalers':    Decimal('0.0189'),     # per pMDI unit (NHS England ~10–37 kg/unit,
                                                 # salbutamol-weighted average)
    'contractor_logistics': Decimal('0.000267'), # per km contracted vehicle (DEFRA 2023 avg van)
    'flights':             Decimal('0.00015'),   # per passenger-km (DEFRA 2023 long-haul
                                                 # economy incl. radiative forcing: 0.14993 kg/pkm)
    'lab_consumables':     Decimal('0.0005'),    # per USD spend (EEIO spend-based, HESCET v2
                                                 # / DEFRA 2023 ~0.5 kgCO₂e per USD)
}

# Waste treatment factor depends on the disposal route, which follows sector:
# clinical waste goes to high-temperature incineration (the compliant route for
# infectious/anatomical waste, and the dominant route in LMIC facilities);
# general organisational waste goes to mixed municipal landfill.
# Sources: Rizan et al. 2021, J. Cleaner Production (high-temp incineration
# 1,074 kg CO₂e/t; range 21–1,074 across routes); DEFRA 2023 municipal
# residual waste to landfill 497 kg CO₂e/t.
WASTE_EF = {
    'clinical': Decimal('1.074'),   # tCO₂e per tonne — high-temp incineration
    'default':  Decimal('0.497'),   # tCO₂e per tonne — municipal landfill
}


# ---------------------------------------------------------------------------
# Procurement categories (GHG Protocol Scope 3, Category 1 — Purchased goods
# and services).
#
# Purchased goods are the largest single slice of a research organisation's
# footprint (Lannelongue et al. 2024, PLOS Sustainability and Transformation,
# "Purchases dominate the carbon footprint of research laboratories"), yet a
# single blended spend factor cannot say WHERE that carbon sits, so it supports
# no procurement decision. Splitting spend by category is what turns the number
# into something a procurement officer can act on.
#
# Factors are spend-based EEIO values from the US EPA Supply Chain Greenhouse
# Gas Emission Factors v1.2 (2017 NAICS-6, 2019 GHG data), "with margins",
# expressed by EPA as kgCO2e per 2021 USD at purchaser price. Stored here as
# tCO2e per USD to match the rest of EMISSION_FACTORS, i.e. EPA value / 1000.
# Dataset: https://catalog.data.gov/dataset/supply-chain-greenhouse-gas-emission-factors-v1-2-by-naics-6
#
# Spend-based factors are the weakest link in any footprint: they assume price
# tracks carbon, so a premium-priced low-carbon product looks worse than a cheap
# high-carbon one. They are appropriate for hot-spot ranking and for coverage of
# categories with no physical data, which is what this table is for. The
# methodology page states this limitation.
# ---------------------------------------------------------------------------
PROCUREMENT_CATEGORIES = {
    'LAB_PLASTICS': {
        'display_name': 'Lab plastics & single-use consumables',
        'factor': Decimal('0.000403'),
        'naics': '326199',
        'naics_title': 'All Other Plastics Product Manufacturing',
        'note': 'Pipette tips, tubes, plates, gloves, single-use labware.',
    },
    'LAB_CHEMICALS': {
        'display_name': 'Chemicals & solvents',
        'factor': Decimal('0.001510'),
        'naics': '325199',
        'naics_title': 'All Other Basic Organic Chemical Manufacturing',
        'note': 'Bulk solvents and organic chemicals. Carbon-intensive per dollar.',
    },
    'LAB_REAGENTS': {
        'display_name': 'Reagents & biological products',
        'factor': Decimal('0.000085'),
        'naics': '325414',
        'naics_title': 'Biological Product (except Diagnostic) Manufacturing',
        'note': 'Antibodies, enzymes, media, cell culture reagents.',
    },
    'LAB_DIAGNOSTICS': {
        'display_name': 'Diagnostic kits & assays',
        'factor': Decimal('0.000143'),
        'naics': '325413',
        'naics_title': 'In-Vitro Diagnostic Substance Manufacturing',
        'note': 'ELISA, PCR and rapid-test kits.',
    },
    'LAB_GASES': {
        'display_name': 'Industrial & laboratory gases',
        'factor': Decimal('0.001450'),
        'naics': '325120',
        'naics_title': 'Industrial Gas Manufacturing',
        'note': 'Liquid nitrogen, CO2 for incubators, compressed gases.',
    },
    'LAB_GLASS': {
        'display_name': 'Glassware',
        'factor': Decimal('0.000490'),
        'naics': '327215',
        'naics_title': 'Glass Product Manufacturing Made of Purchased Glass',
        'note': 'Reusable glassware. Low spend, but a reuse lever.',
    },
    'LAB_EQUIPMENT': {
        'display_name': 'Laboratory instruments & equipment',
        'factor': Decimal('0.000093'),
        'naics': '334516',
        'naics_title': 'Analytical Laboratory Instrument Manufacturing',
        'note': 'Sequencers, analysers, centrifuges, spectrometers.',
    },
    'COLD_CHAIN': {
        'display_name': 'Refrigeration & cold-chain equipment',
        'factor': Decimal('0.000236'),
        'naics': '333415',
        'naics_title': 'Air-Conditioning and Commercial and Industrial Refrigeration Equipment Manufacturing',
        'note': 'ULT freezers, cold rooms, sample fridges. Capital purchase only — '
                'running electricity sits under Grid Electricity.',
    },
    'MEDICAL_SUPPLIES': {
        'display_name': 'Medical & surgical supplies',
        'factor': Decimal('0.000190'),
        'naics': '339112',
        'naics_title': 'Surgical and Medical Instrument Manufacturing',
        'note': 'Clinical trial and participant-facing consumables.',
    },
    'PHARMA': {
        'display_name': 'Pharmaceuticals & study drugs',
        'factor': Decimal('0.000107'),
        'naics': '325412',
        'naics_title': 'Pharmaceutical Preparation Manufacturing',
    },
    'IT_HARDWARE': {
        'display_name': 'Computing & IT hardware',
        'factor': Decimal('0.000112'),
        'naics': '334111',
        'naics_title': 'Electronic Computer Manufacturing',
        'note': 'Laptops, servers, storage. A major line for data-heavy groups.',
    },
    'IT_SOFTWARE': {
        'display_name': 'Software & licences',
        'factor': Decimal('0.000097'),
        'naics': '511210',
        'naics_title': 'Software Publishers',
    },
    'OFFICE_PAPER': {
        'display_name': 'Office supplies & paper',
        'factor': Decimal('0.000418'),
        'naics': '322230',
        'naics_title': 'Stationery Product Manufacturing',
    },
    'FREIGHT_COURIER': {
        'display_name': 'Freight, courier & sample shipping',
        'factor': Decimal('0.000257'),
        'naics': '492110',
        'naics_title': 'Couriers and Express Delivery Services',
        'note': 'Cold-chain sample shipping and inbound deliveries.',
    },
    'FACILITIES_MAINT': {
        'display_name': 'Facilities, maintenance & fit-out',
        'factor': Decimal('0.000245'),
        'naics': '238220',
        'naics_title': 'Plumbing, Heating, and Air-Conditioning Contractors',
    },
    'CLEANING': {
        'display_name': 'Cleaning & janitorial services',
        'factor': Decimal('0.000167'),
        'naics': '561720',
        'naics_title': 'Janitorial Services',
    },
    'SUBCONTRACT_RESEARCH': {
        'display_name': 'Subcontracted research & site payments',
        'factor': Decimal('0.000174'),
        'naics': '541715',
        'naics_title': 'Research and Development in the Physical, Engineering and Life Sciences',
        'note': 'Payments to collaborating sites and CROs.',
    },
    'PROF_SERVICES': {
        'display_name': 'Professional & consulting services',
        'factor': Decimal('0.000084'),
        'naics': '541611',
        'naics_title': 'Administrative Management and General Management Consulting Services',
    },
    'OTHER': {
        'display_name': 'Other / unclassified spend',
        'factor': Decimal('0.000449'),
        'naics': '—',
        'naics_title': '75th percentile across all 1,016 EPA commodities',
        'note': 'Deliberately conservative: set above the median (0.208 kgCO2e/USD) '
                'so unclassified spend is not under-counted, and so classifying a '
                'line almost always lowers the reported figure.',
    },
}

# Categories whose emissions are already captured elsewhere must NOT appear
# here, or they would be counted twice. Waste disposal services are the obvious
# trap: that spend belongs to the Waste Management category, which uses a
# physical tonnage factor.
PROCUREMENT_EXCLUDED_NOTE = (
    'Waste disposal, electricity, fuel and travel are deliberately absent. '
    'Those are already measured with physical activity data elsewhere in the '
    'footprint, so counting the spend as well would double-count them.'
)


# Words a finance-system export is likely to contain, mapped to our categories.
# A spend export names things like "Consumables - plastics" or "Ref: Thermo
# Fisher tips", never 'LAB_PLASTICS', so import has to meet the data where it
# is. Checked longest-first so 'lab equipment' wins over bare 'lab'.
PROCUREMENT_ALIASES = {
    'LAB_PLASTICS': ['plastic', 'pipette', 'tip', 'tube', 'glove', 'labware',
                     'disposable', 'single-use', 'single use', 'petri', 'plate',
                     'consumable'],
    'LAB_CHEMICALS': ['chemical', 'solvent', 'ethanol', 'methanol', 'acid',
                      'buffer', 'stain'],
    'LAB_REAGENTS': ['reagent', 'antibod', 'enzyme', 'media', 'serum',
                     'cell culture', 'biological', 'primer', 'probe'],
    'LAB_DIAGNOSTICS': ['diagnostic', 'assay', 'elisa', 'pcr kit', 'test kit',
                        'rapid test'],
    'LAB_GASES': ['gas cylinder', 'liquid nitrogen', 'nitrogen', 'co2 gas',
                  'compressed gas', 'industrial gas'],
    'LAB_GLASS': ['glassware', 'glass'],
    'LAB_EQUIPMENT': ['lab equipment', 'laboratory equipment', 'instrument',
                      'centrifuge', 'sequencer', 'analyser', 'analyzer',
                      'microscope', 'spectrometer'],
    'COLD_CHAIN': ['freezer', 'cold chain', 'cold-chain', 'refrigerat',
                   'fridge', 'cold room', 'ult'],
    'MEDICAL_SUPPLIES': ['medical supply', 'medical supplies', 'surgical',
                         'syringe', 'needle', 'dressing', 'clinical supply'],
    'PHARMA': ['pharmaceutic', 'drug', 'medicine', 'vaccine', 'study drug'],
    'IT_HARDWARE': ['laptop', 'computer', 'server', 'hardware', 'monitor',
                    'printer', 'storage', 'tablet'],
    'IT_SOFTWARE': ['software', 'licence', 'license', 'subscription', 'saas',
                    'cloud'],
    'OFFICE_PAPER': ['stationery', 'paper', 'office supply', 'office supplies',
                     'printing'],
    'FREIGHT_COURIER': ['courier', 'freight', 'shipping', 'postage', 'dhl',
                        'logistics', 'delivery'],
    'FACILITIES_MAINT': ['maintenance', 'repair', 'fit-out', 'fitout',
                         'building', 'plumbing', 'electrical work',
                         'construction'],
    'CLEANING': ['cleaning', 'janitor', 'hygiene'],
    'SUBCONTRACT_RESEARCH': ['subcontract', 'sub-contract', 'cro', 'site payment',
                             'collaborat', 'participant reimbursement'],
    'PROF_SERVICES': ['consult', 'professional service', 'legal', 'audit',
                      'accounting', 'training'],
}


def match_procurement_category(text):
    """
    Best-guess category for a free-text spend description.

    Returns (category_code, matched) — matched is False when nothing hit and the
    line falls back to OTHER, so the import can report how much spend went
    unclassified instead of silently absorbing it.
    """
    if not text:
        return 'OTHER', False
    needle = str(text).strip().lower()

    # An exact category code or display name always wins.
    for code, spec in PROCUREMENT_CATEGORIES.items():
        if needle == code.lower() or needle == spec['display_name'].lower():
            return code, True

    # Otherwise longest alias first, so 'lab equipment' beats 'plate'.
    candidates = [
        (alias, code)
        for code, aliases in PROCUREMENT_ALIASES.items()
        for alias in aliases
    ]
    for alias, code in sorted(candidates, key=lambda pair: -len(pair[0])):
        if alias in needle:
            return code, True
    return 'OTHER', False


def procurement_category_choices():
    """(code, label) pairs for form fields, ordered by display name."""
    return sorted(
        ((code, spec['display_name']) for code, spec in PROCUREMENT_CATEGORIES.items()),
        key=lambda pair: pair[1],
    )


def compute_tco2e(emission_data, country='OTHER', sector=None):
    """
    Convert raw usage quantities stored in an EmissionData record to tCO₂e.

    Args:
        emission_data: EmissionData instance (raw physical units per field).
        country:       ISO-2 country code of the facility (for electricity EF).
        sector:        Facility sector key (for the waste treatment route:
                       clinical → high-temp incineration, else landfill).

    Returns:
        dict with one key per emission field (tCO₂e value) plus 'total'.

    Procurement: when the record has itemised procurement lines, they replace
    the single blended lab_consumables estimate rather than adding to it. This
    is resolved here, inside the one function every caller already routes
    through, so the dashboard, facility profile and optimiser all agree without
    each needing to know procurement exists.
    """
    electricity_ef = ELECTRICITY_EF.get(country, ELECTRICITY_EF['OTHER'])
    waste_ef = WASTE_EF['clinical'] if sector == 'clinical' else WASTE_EF['default']
    results = {}
    for field, factor in EMISSION_FACTORS.items():
        raw = getattr(emission_data, field, None) or Decimal('0')
        if field == 'grid_electricity':
            ef = electricity_ef
        elif field == 'waste_management':
            ef = waste_ef
        else:
            ef = factor or Decimal('0')
        results[field] = Decimal(str(raw)) * ef

    itemised = itemised_procurement_tco2e(emission_data)
    if itemised is not None:
        results['lab_consumables'] = itemised

    results['total'] = sum(results.values())
    return results


def itemised_procurement_tco2e(emission_data):
    """
    tCO₂e from this record's procurement lines, or None if it has none.

    None (rather than zero) is the signal to fall back to the blended
    lab_consumables spend figure — a record with no lines is un-itemised, not a
    record with zero procurement.

    Tolerates an unsaved or line-less record so compute_tco2e() stays usable on
    in-memory instances, which several callers rely on.
    """
    if getattr(emission_data, 'pk', None) is None:
        return None
    try:
        lines = emission_data.procurement_lines.all()
    except (AttributeError, ValueError):
        return None
    lines = list(lines)
    if not lines:
        return None
    return sum((line.tco2e() for line in lines), Decimal('0'))


def procurement_breakdown(emission_data):
    """
    Per-category procurement rollup for the hot-spot view, biggest first.

    Returns [] when the record has no lines. Each row carries the category's
    share of procurement carbon AND its share of spend, because the gap between
    those two is the actionable insight: a category at 5% of spend but 30% of
    carbon is where a procurement officer should look first.
    """
    lines = list(emission_data.procurement_lines.all()) if getattr(emission_data, 'pk', None) else []
    if not lines:
        return []

    totals = {}
    for line in lines:
        row = totals.setdefault(line.category, {
            'category': line.category,
            'label': line.category_label,
            'spec': line.spec,
            'spend': Decimal('0'),
            'tco2e': Decimal('0'),
            'line_count': 0,
        })
        row['spend'] += line.spend_usd or Decimal('0')
        row['tco2e'] += line.tco2e()
        row['line_count'] += 1

    total_tco2e = sum((r['tco2e'] for r in totals.values()), Decimal('0'))
    total_spend = sum((r['spend'] for r in totals.values()), Decimal('0'))
    rows = sorted(totals.values(), key=lambda r: r['tco2e'], reverse=True)

    cumulative = Decimal('0')
    for row in rows:
        row['carbon_share'] = (row['tco2e'] / total_tco2e * 100) if total_tco2e else Decimal('0')
        row['spend_share'] = (row['spend'] / total_spend * 100) if total_spend else Decimal('0')
        # Positive means this category punches above its spend — the hot spots.
        row['intensity_gap'] = row['carbon_share'] - row['spend_share']
        cumulative += row['carbon_share']
        row['cumulative_share'] = cumulative
    return rows


def sum_tco2e(emission_data_qs, country='OTHER', sector=None):
    """Sum tCO₂e across a queryset of EmissionData records for one facility."""
    return sum(compute_tco2e(ed, country, sector)['total'] for ed in emission_data_qs) or Decimal('0')


# ---------------------------------------------------------------------------
# Intervention library
# Emission category keys match EmissionData model fields.
# 'reduces' values are the fractional reduction in that emission category.
# Sourced from HIGH Horizons D3.7, Mt Darwin Hospital and AKHS Mombasa case studies.
# ---------------------------------------------------------------------------
INTERVENTION_LIBRARY = {
    # ── Legacy / generic entries (keep for backward compatibility) ────────────
    'SOLAR_PV': {
        'display_name': 'Solar PV System',
        'reduces': {'grid_electricity': Decimal('0.70')},
        'sdg_goals': [7, 13],
        'notes': (
            'Reduces grid dependency; protects cold chains and critical equipment '
            'from load shedding common in ZW and ZA contexts. '
            'See SOLAR_3KVA – SOLAR_600KWP for size-specific entries.'
        ),
    },
    'LOW_GWP_ANAESTHETICS': {
        'display_name': 'Low-GWP Anaesthetic Gases',
        'reduces': {'anaesthetic_gases': Decimal('0.85')},
        'sdg_goals': [3, 13],
        'sectors': ['clinical'],
        'notes': (
            'Replace desflurane and sevoflurane with TIVA or low-GWP alternatives. '
            'See ANAES_ISO_SEVO and ANAES_NO_AVOID for specific switch entries.'
        ),
    },
    'LED_LIGHTING': {
        'display_name': 'LED Lighting Upgrade',
        'reduces': {'grid_electricity': Decimal('0.30')},
        'sdg_goals': [7, 11],
        'notes': (
            'Retrofit fluorescent and incandescent fittings with LED throughout facility. '
            'See LED_WATT_5 – LED_WATT_95 for wattage-specific entries.'
        ),
    },
    'WASTE_SEGREGATION': {
        'display_name': 'Medical Waste Segregation & Management',
        'reduces': {'waste_management': Decimal('0.60')},
        'sdg_goals': [3, 12],
        'sectors': ['clinical'],
        'notes': (
            'Separate hazardous from non-hazardous waste streams to reduce '
            'incineration volume and associated dioxin emissions. '
            'NHS evidence: effective segregation reduces clinical waste carbon by 30 %.'
        ),
    },
    'WATER_EFFICIENT_FIXTURES': {
        'display_name': 'Water-Efficient Fixtures',
        'reduces': {'grid_electricity': Decimal('0.05')},
        'sdg_goals': [6, 11],
        'notes': 'Low-flow taps, showers, and cisterns; secondary benefit of reduced water-heating energy.',
    },
    'HFC_REFRIGERANT_SWAP': {
        'display_name': 'Low-GWP Refrigerant Conversion',
        'reduces': {'refrigeration_gases': Decimal('0.75')},
        'sdg_goals': [13],
        'notes': (
            'Replace HFC-134a and R-22 refrigerants in cold-chain and HVAC equipment. '
            'See REFRIG_* entries for gas-pair-specific options.'
        ),
    },
    'DPI_INHALER_SWITCH': {
        'display_name': 'Switch to Dry-Powder Inhalers (DPI)',
        'reduces': {'medical_inhalers': Decimal('0.70')},
        'sdg_goals': [3, 13],
        'sectors': ['clinical'],
        'notes': (
            'Pressurised MDIs contain HFC propellants with very high GWP. '
            'Switch to DPIs where clinically appropriate — WHO-endorsed.'
        ),
    },
    'FLEET_OPTIMISATION': {
        'display_name': 'Fleet & Travel Optimisation',
        'reduces': {
            'vehicle_fuel_owned': Decimal('0.30'),
            'business_travel': Decimal('0.20'),
        },
        'sdg_goals': [11, 13],
        'notes': 'Route optimisation, preventive vehicle maintenance, and active travel policy.',
    },

    # ── 1. LED Lights — wattage-specific ─────────────────────────────────────
    # Source: HIGH Horizons D3.7 Carbon Saving Calculator (ZW ZESA EF = 0.883 kgCO2e/kWh)
    'LED_WATT_5': {
        'display_name': 'LED Lights — 5W Wattage Reduction per Lamp',
        'reduces': {'grid_electricity': Decimal('0.20')},
        'sdg_goals': [7, 11, 13],
        'notes': (
            '25W → 20W lamp swap. Saves 21.9 kWh/lamp/year = 19.3 kgCO₂e/lamp/year. '
            'Default batch 100 lamps — CapEx US$6/lamp, maint US$0.18/lamp, '
            'annual cost saving US$920. Source: HIGH Horizons D3.7 Carbon Saving Calculator.'
        ),
    },
    'LED_WATT_10': {
        'display_name': 'LED Lights — 10W Wattage Reduction per Lamp',
        'reduces': {'grid_electricity': Decimal('0.50')},
        'sdg_goals': [7, 11, 13],
        'notes': (
            '20W → 10W lamp swap. Saves 43.8 kWh/lamp/year = 13.9 kgCO₂e/lamp/year. '
            'Default batch 20 lamps — CapEx US$2/lamp, maint US$0.06/lamp, '
            'annual cost saving US$184. Source: HIGH Horizons D3.7.'
        ),
    },
    'LED_WATT_20': {
        'display_name': 'LED Lights — 20W Wattage Reduction per Lamp',
        'reduces': {'grid_electricity': Decimal('0.80')},
        'sdg_goals': [7, 11, 13],
        'notes': (
            '25W → 5W lamp swap. Saves 87.6 kWh/lamp/year = 77.4 kgCO₂e/lamp/year. '
            'Default batch 20 lamps — CapEx US$8/lamp, maint US$0.24/lamp, '
            'annual cost saving US$368. Source: HIGH Horizons D3.7.'
        ),
    },
    'LED_WATT_50': {
        'display_name': 'LED Lights — 50W Wattage Reduction per Lamp',
        'reduces': {'grid_electricity': Decimal('0.50')},
        'sdg_goals': [7, 11, 13],
        'notes': (
            '100W → 50W lamp swap. Saves 219 kWh/lamp/year = 193.4 kgCO₂e/lamp/year. '
            'Default batch 20 lamps — CapEx US$8/lamp, maint US$0.24/lamp, '
            'annual cost saving US$920. Source: HIGH Horizons D3.7.'
        ),
    },
    'LED_WATT_95': {
        'display_name': 'LED Lights — 95W Wattage Reduction per Lamp',
        'reduces': {'grid_electricity': Decimal('0.95')},
        'sdg_goals': [7, 11, 13],
        'notes': (
            '100W → 5W lamp swap. Saves 416.1 kWh/lamp/year = 367.4 kgCO₂e/lamp/year. '
            'Default batch 20 lamps — CapEx US$10/lamp, maint US$0.30/lamp, '
            'annual cost saving US$1,748. Source: HIGH Horizons D3.7.'
        ),
    },

    # ── 2. Solar Systems ──────────────────────────────────────────────────────
    'SOLAR_3KVA': {
        'display_name': 'Solar PV System — 3 kVA',
        'reduces': {'grid_electricity': Decimal('0.09')},
        'sdg_goals': [7, 13],
        'notes': (
            '3 kVA / 3 kWp system generates ~4,903 kWh/year (ZW). '
            'Saves 1,330.7 kgCO₂e/year. CapEx US$2,500, maint US$1,875/year, '
            'annual cost saving US$1,555. Source: HIGH Horizons D3.7 Cost Calculator.'
        ),
    },
    'SOLAR_5KVA': {
        'display_name': 'Solar PV System — 5 kVA',
        'reduces': {'grid_electricity': Decimal('0.15')},
        'sdg_goals': [7, 13],
        'notes': (
            '5 kVA / 5 kWp system generates ~8,172 kWh/year (ZW). '
            'Saves 2,217.9 kgCO₂e/year. CapEx US$4,000, maint US$3,000/year, '
            'annual cost saving US$2,136. Source: HIGH Horizons D3.7.'
        ),
    },
    'SOLAR_10KVA': {
        'display_name': 'Solar PV System — 10 kVA',
        'reduces': {'grid_electricity': Decimal('0.30')},
        'sdg_goals': [7, 13],
        'notes': (
            '10 kVA / 10 kWp system generates ~16,344 kWh/year (ZW). '
            'Saves 13,678.1 kgCO₂e/year. CapEx US$11,000, maint US$8,250/year, '
            'annual cost saving US$3,362. Source: HIGH Horizons D3.7.'
        ),
    },
    'SOLAR_100KWP': {
        'display_name': 'Solar PV System — 100 kWp',
        'reduces': {'grid_electricity': Decimal('0.70')},
        'sdg_goals': [7, 13],
        'notes': (
            '100 kWp system generates ~170,558 kWh/year (ZW). '
            'Saves 142,825.3 kgCO₂e/year. CapEx US$80,000, maint US$60,000/year, '
            'annual cost saving US$30,917. Source: HIGH Horizons D3.7.'
        ),
    },
    'SOLAR_150KWP': {
        'display_name': 'Solar PV System — 150 kWp',
        'reduces': {'grid_electricity': Decimal('0.85')},
        'sdg_goals': [7, 13],
        'notes': (
            '150 kWp system generates ~255,837 kWh/year (ZW). '
            'Saves 214,237.9 kgCO₂e/year. CapEx US$153,000, maint US$114,750/year, '
            'annual cost saving US$43,716. Source: HIGH Horizons D3.7.'
        ),
    },
    'SOLAR_600KWP': {
        'display_name': 'Solar PV System — 600 kWp',
        'reduces': {'grid_electricity': Decimal('0.99')},
        'sdg_goals': [7, 13],
        'notes': (
            '600 kWp system generates ~1,023,000 kWh/year (ZW). '
            'Saves 856,660.2 kgCO₂e/year. CapEx US$612,000, maint US$459,000/year, '
            'annual cost saving US$172,690. Source: HIGH Horizons D3.7.'
        ),
    },

    # ── 3. Biogas Digestors ───────────────────────────────────────────────────
    'BIOGAS_6M3': {
        'display_name': 'Biogas Digester — 6 m³',
        'reduces': {'bottled_gas': Decimal('0.50')},
        'sdg_goals': [7, 13],
        'notes': (
            '6 m³ digester produces ~2.0 m³ biogas/day (43.0 kg/month, 516 kg/year). '
            'Replaces LPG; saves 1,516.6 kgCO₂e/year. '
            'CapEx US$2,000, maint US$300/year, annual cost saving US$526. '
            'Source: HIGH Horizons D3.7.'
        ),
    },
    'BIOGAS_20M3': {
        'display_name': 'Biogas Digester — 20 m³',
        'reduces': {'bottled_gas': Decimal('0.70')},
        'sdg_goals': [7, 13],
        'notes': (
            '20 m³ digester produces ~7.0 m³ biogas/day (151.2 kg/month, 1,815 kg/year). '
            'Replaces LPG; saves 5,331.4 kgCO₂e/year. '
            'CapEx US$5,000, maint US$750/year, annual cost saving US$2,316. '
            'Source: HIGH Horizons D3.7.'
        ),
    },

    # ── 4. Low-GWP Refrigerants — gas-pair specific ───────────────────────────
    'REFRIG_R134A_R1234YF': {
        'display_name': 'Refrigerant Swap — R134a to R1234yf (HFO)',
        'reduces': {'refrigeration_gases': Decimal('0.99')},
        'sdg_goals': [13],
        'notes': (
            'R1234yf GWP < 1 vs R134a GWP 1,430. '
            'Saves 1,429 kgCO₂e per kg swapped. Used in automotive A/C. '
            'Per 20 kg batch: CapEx US$0, maint US$0, cost saving –US$300 (HFO premium). '
            'Source: HIGH Horizons D3.7.'
        ),
    },
    'REFRIG_R134A_R1234ZE': {
        'display_name': 'Refrigerant Swap — R134a to R1234ze (HFO)',
        'reduces': {'refrigeration_gases': Decimal('0.99')},
        'sdg_goals': [13],
        'notes': (
            'R1234ze GWP < 1 vs R134a GWP 1,430. '
            'Saves 1,429 kgCO₂e per kg swapped. Used in chillers / commercial refrigeration. '
            'Per 20 kg batch: cost saving US$400. Source: HIGH Horizons D3.7.'
        ),
    },
    'REFRIG_R410A_R1234ZE': {
        'display_name': 'Refrigerant Swap — R410a to R1234ze (HFO)',
        'reduces': {'refrigeration_gases': Decimal('0.99')},
        'sdg_goals': [13],
        'notes': (
            'R1234ze GWP < 1 vs R410a GWP 2,088. '
            'Saves 2,087 kgCO₂e per kg swapped. Used in A/C and heat pumps. '
            'Per 20 kg batch: cost saving –US$200 (HFO premium). Source: HIGH Horizons D3.7.'
        ),
    },
    'REFRIG_R410A_R32': {
        'display_name': 'Refrigerant Swap — R410a to R32',
        'reduces': {'refrigeration_gases': Decimal('0.68')},
        'sdg_goals': [13],
        'notes': (
            'R32 GWP 675 vs R410a GWP 2,088. '
            'Saves 1,413 kgCO₂e per kg swapped. Modern A/C systems. '
            'Per 20 kg batch: cost saving US$700. Source: HIGH Horizons D3.7.'
        ),
    },
    'REFRIG_R404A_R448A': {
        'display_name': 'Refrigerant Swap — R404a to R448A (Solstice® N40)',
        'reduces': {'refrigeration_gases': Decimal('0.68')},
        'sdg_goals': [13],
        'notes': (
            'R448A GWP ≈ 1,273 vs R404A GWP 3,922. '
            'Saves 2,649 kgCO₂e per kg swapped. Commercial refrigeration. '
            'Per 20 kg batch: cost saving US$300. Source: HIGH Horizons D3.7.'
        ),
    },
    'REFRIG_R22_R290': {
        'display_name': 'Refrigerant Swap — R22 to R290 (Propane)',
        'reduces': {'refrigeration_gases': Decimal('0.99')},
        'sdg_goals': [13],
        'notes': (
            'R290 (Propane) GWP 3 vs R22 GWP 1,810. '
            'Saves 1,807 kgCO₂e per kg swapped. '
            'Default 50 kg batch — cost saving US$5,250. Source: HIGH Horizons D3.7.'
        ),
    },
    'REFRIG_R32_R744': {
        'display_name': 'Refrigerant Swap — R32 to R744 (CO₂)',
        'reduces': {'refrigeration_gases': Decimal('0.99')},
        'sdg_goals': [13],
        'notes': (
            'R744 (CO₂) GWP 1 vs R32 GWP 675. '
            'Saves 674 kgCO₂e per kg swapped. '
            'Default 10 kg batch — cost –US$600 (CO₂ system premium). Source: HIGH Horizons D3.7.'
        ),
    },
    'REFRIG_R403A_R407A': {
        'display_name': 'Refrigerant Swap — R403A to R407A',
        'reduces': {'refrigeration_gases': Decimal('0.56')},
        'sdg_goals': [13],
        'notes': (
            'R407A GWP ≈ 1,774 vs R403A GWP 4,032. '
            'Saves 2,258 kgCO₂e per kg swapped. '
            'Default 20 kg batch — cost saving US$700. Source: HIGH Horizons D3.7.'
        ),
    },

    # ── 5. Low-GWP Anaesthetic Gases ─────────────────────────────────────────
    'ANAES_ISO_SEVO': {
        'display_name': 'Anaesthetic Switch — Isoflurane to Sevoflurane',
        'reduces': {'anaesthetic_gases': Decimal('0.75')},
        'sdg_goals': [3, 13],
        'sectors': ['clinical'],
        'notes': (
            'Sevoflurane GWP 130 vs isoflurane GWP 510. '
            'Saves 380 kgCO₂e per kg agent switched. '
            'Cost saving –US$400/year (sevoflurane costs more per litre). '
            'Source: HIGH Horizons D3.7.'
        ),
    },

    # ── 6. Avoid Nitrous Oxide ────────────────────────────────────────────────
    'ANAES_NO_AVOID': {
        'display_name': 'Avoid Nitrous Oxide (N₂O)',
        'reduces': {'anaesthetic_gases': Decimal('1.00')},
        'sdg_goals': [3, 13],
        'sectors': ['clinical'],
        'notes': (
            'N₂O GWP 265; eliminating use saves 298 kgCO₂e per kg avoided. '
            'Per 20-unit batch — cost saving US$200. '
            'Source: HIGH Horizons D3.7.'
        ),
    },

    # ── 7. Low-GWP Inhalers ───────────────────────────────────────────────────
    'INHALER_DPI': {
        'display_name': 'Inhaler Switch — Salbutamol MDI to DPI',
        'reduces': {'medical_inhalers': Decimal('1.00')},
        'sdg_goals': [3, 13],
        'sectors': ['clinical'],
        'notes': (
            'Salbutamol MDI emits ~19 kgCO₂e per 200-dose device; DPI ≈ 0. '
            'Saves 19 kgCO₂e per device. '
            'Per 100 devices: cost –US$500 (DPIs cost more). Source: HIGH Horizons D3.7.'
        ),
    },
    'INHALER_SMI': {
        'display_name': 'Inhaler Switch — Salbutamol MDI to Soft Mist Inhaler (SMI)',
        'reduces': {'medical_inhalers': Decimal('1.00')},
        'sdg_goals': [3, 13],
        'sectors': ['clinical'],
        'notes': (
            'Salbutamol MDI emits ~19 kgCO₂e per device; SMI ≈ 0. '
            'Saves 19 kgCO₂e per device. '
            'Per 20 devices: cost –US$300 (SMIs cost more). Source: HIGH Horizons D3.7.'
        ),
    },

    # ── 8. Energy-Efficient Refrigerators ─────────────────────────────────────
    'FREEZER_UPRIGHT_S': {
        'display_name': 'Energy-Efficient Upright Freezer 280–425 L',
        'reduces': {'grid_electricity': Decimal('0.46')},
        'sdg_goals': [7, 13],
        'notes': (
            'Replaces conventional 700 kWh/year unit with 375 kWh model. '
            'Saves 325 kWh/year = 286.98 kgCO₂e/year. '
            'CapEx US$350, maint US$52.50/year, annual cost saving US$56. '
            'Source: HIGH Horizons D3.7.'
        ),
    },
    'FREEZER_UPRIGHT_M': {
        'display_name': 'Energy-Efficient Upright Freezer 425–566 L',
        'reduces': {'grid_electricity': Decimal('0.53')},
        'sdg_goals': [7, 13],
        'notes': (
            'Replaces conventional 900 kWh/year unit with 425 kWh model. '
            'Saves 475 kWh/year = 419.4 kgCO₂e/year. '
            'CapEx US$700, maint US$105/year, annual cost saving US$77. '
            'Source: HIGH Horizons D3.7.'
        ),
    },
    'FREEZER_UPRIGHT_L': {
        'display_name': 'Energy-Efficient Upright Freezer 566–708 L',
        'reduces': {'grid_electricity': Decimal('0.57')},
        'sdg_goals': [7, 13],
        'notes': (
            'Replaces conventional 1,100 kWh/year unit with 475 kWh model. '
            'Saves 625 kWh/year = 551.9 kgCO₂e/year. '
            'CapEx US$1,000, maint US$150/year, annual cost saving US$81. '
            'Source: HIGH Horizons D3.7.'
        ),
    },
    'FREEZER_DEEP_S': {
        'display_name': 'Energy-Efficient Deep Freezer 280–425 L',
        'reduces': {'grid_electricity': Decimal('0.45')},
        'sdg_goals': [7, 13],
        'notes': (
            'Replaces conventional 500 kWh/year unit with 275 kWh model. '
            'Saves 225 kWh/year = 198.7 kgCO₂e/year. '
            'CapEx US$400, maint US$60/year, annual cost saving US$49. '
            'Source: HIGH Horizons D3.7.'
        ),
    },
    'FREEZER_DEEP_M': {
        'display_name': 'Energy-Efficient Deep Freezer 425–566 L',
        'reduces': {'grid_electricity': Decimal('0.54')},
        'sdg_goals': [7, 13],
        'notes': (
            'Replaces conventional 700 kWh/year unit with 325 kWh model. '
            'Saves 375 kWh/year = 331.1 kgCO₂e/year. '
            'CapEx US$600, maint US$90/year, annual cost saving US$57. '
            'Source: HIGH Horizons D3.7.'
        ),
    },
    'FREEZER_DEEP_L': {
        'display_name': 'Energy-Efficient Deep Freezer 566–708 L',
        'reduces': {'grid_electricity': Decimal('0.58')},
        'sdg_goals': [7, 13],
        'notes': (
            'Replaces conventional 900 kWh/year unit with 375 kWh model. '
            'Saves 525 kWh/year = 463.6 kgCO₂e/year. '
            'CapEx US$900, maint US$135/year, annual cost saving US$61. '
            'Source: HIGH Horizons D3.7.'
        ),
    },

    # ── 9. Energy-Efficient AC Splits ─────────────────────────────────────────
    'AC_WINDOW_1TON': {
        'display_name': 'Energy-Efficient Window AC — 0.75–1 Ton (9K–12K BTU)',
        'reduces': {'grid_electricity': Decimal('0.43')},
        'sdg_goals': [7, 11, 13],
        'notes': (
            'Inverter window unit: 1,000 kWh/year vs 1,750 kWh baseline. '
            'Saves 750 kWh/year = 662.3 kgCO₂e/year. '
            'CapEx US$800, maint US$120/year, annual cost saving US$130. '
            'Source: HIGH Horizons D3.7.'
        ),
    },
    'AC_WINDOW_2TON': {
        'display_name': 'Energy-Efficient Window AC — 1.5–2 Tons (18K–24K BTU)',
        'reduces': {'grid_electricity': Decimal('0.47')},
        'sdg_goals': [7, 11, 13],
        'notes': (
            'Inverter window unit: 2,000 kWh/year vs 3,750 kWh baseline. '
            'Saves 1,750 kWh/year = 1,545.3 kgCO₂e/year. '
            'CapEx US$1,200, maint US$180/year, annual cost saving US$326. '
            'Source: HIGH Horizons D3.7.'
        ),
    },
    'AC_SPLIT_1TON': {
        'display_name': 'Energy-Efficient Split AC — 0.75–1 Ton (9K–12K BTU)',
        'reduces': {'grid_electricity': Decimal('0.43')},
        'sdg_goals': [7, 11, 13],
        'notes': (
            'Inverter split unit: 1,000 kWh/year vs 1,750 kWh baseline. '
            'Saves 750 kWh/year = 662.3 kgCO₂e/year. '
            'CapEx US$800, maint US$120/year, annual cost saving US$130. '
            'Source: HIGH Horizons D3.7.'
        ),
    },
    'AC_SPLIT_2TON': {
        'display_name': 'Energy-Efficient Split AC — 1.5–2 Tons (18K–24K BTU)',
        'reduces': {'grid_electricity': Decimal('0.47')},
        'sdg_goals': [7, 11, 13],
        'notes': (
            'Inverter split unit: 2,000 kWh/year vs 3,750 kWh baseline. '
            'Saves 1,750 kWh/year = 1,545.3 kgCO₂e/year. '
            'CapEx US$1,200, maint US$180/year, annual cost saving US$326. '
            'Source: HIGH Horizons D3.7.'
        ),
    },
    'AC_SPLIT_3TON': {
        'display_name': 'Energy-Efficient Split AC — 2–3 Tons (24K–36K BTU)',
        'reduces': {'grid_electricity': Decimal('0.52')},
        'sdg_goals': [7, 11, 13],
        'notes': (
            'Inverter split unit: 2,500 kWh/year vs 5,250 kWh baseline. '
            'Saves 2,750 kWh/year = 2,428.3 kgCO₂e/year. '
            'CapEx US$2,000, maint US$300/year, annual cost saving US$509. '
            'Source: HIGH Horizons D3.7.'
        ),
    },
    'AC_CENTRAL_5TON': {
        'display_name': 'Energy-Efficient Central AC — 3–5 Tons (36K–60K BTU)',
        'reduces': {'grid_electricity': Decimal('0.39')},
        'sdg_goals': [7, 11, 13],
        'notes': (
            'Inverter central unit: 4,250 kWh/year vs 7,000 kWh baseline. '
            'Saves 2,750 kWh/year = 2,428.3 kgCO₂e/year. '
            'CapEx US$6,000, maint US$900/year, annual cost saving US$371. '
            'Source: HIGH Horizons D3.7.'
        ),
    },

    # ── 10. Energy-Efficient Heaters ──────────────────────────────────────────
    'HEATER_SPACE_2KW': {
        'display_name': 'Energy-Efficient Electric Space Heater 1–2 kW',
        'reduces': {'grid_electricity': Decimal('0.46')},
        'sdg_goals': [7, 13],
        'notes': (
            'With thermostat: 950 kWh/year vs 1,750 kWh baseline. '
            'Saves 800 kWh/year = 706.4 kgCO₂e/year. '
            'CapEx US$150, maint US$22.50/year, annual cost saving US$164. '
            'Source: HIGH Horizons D3.7.'
        ),
    },
    'HEATER_INFRARED_1KW': {
        'display_name': 'Portable Infrared Heater 1.5 kW (programmable)',
        'reduces': {'grid_electricity': Decimal('0.50')},
        'sdg_goals': [7, 13],
        'notes': (
            'With programmable thermostat: 750 kWh/year vs 1,500 kWh baseline. '
            'Saves 750 kWh/year = 662.3 kgCO₂e/year. '
            'CapEx US$250, maint US$37.50/year, annual cost saving US$296. '
            'Source: HIGH Horizons D3.7.'
        ),
    },
    'HEATER_OIL_RADIATOR': {
        'display_name': 'Oil-Filled Radiator 1.5–2 kW (ECO mode)',
        'reduces': {'grid_electricity': Decimal('0.48')},
        'sdg_goals': [7, 13],
        'notes': (
            'With ECO mode: 1,050 kWh/year vs 2,000 kWh baseline. '
            'Saves 950 kWh/year = 838.9 kgCO₂e/year. '
            'CapEx US$200, maint US$30/year, annual cost saving US$188. '
            'Source: HIGH Horizons D3.7.'
        ),
    },
    'HEATER_BASEBOARD': {
        'display_name': 'Baseboard Heater 1–2 kW (built-in thermostat)',
        'reduces': {'grid_electricity': Decimal('0.51')},
        'sdg_goals': [7, 13],
        'notes': (
            'With built-in thermostat: 1,050 kWh/year vs 2,150 kWh baseline. '
            'Saves 1,100 kWh/year = 971.3 kgCO₂e/year. '
            'CapEx US$200, maint US$30/year, annual cost saving US$372. '
            'Source: HIGH Horizons D3.7.'
        ),
    },
    'HEATER_CENTRAL_FURNACE': {
        'display_name': 'Central Electric Furnace 10–20 kW (variable speed)',
        'reduces': {'grid_electricity': Decimal('0.47')},
        'sdg_goals': [7, 13],
        'notes': (
            'Variable speed + zoning: 9,500 kWh/year vs 18,000 kWh baseline. '
            'Saves 8,500 kWh/year = 7,505.5 kgCO₂e/year. '
            'CapEx US$6,000, maint US$900/year, annual cost saving US$1,425. '
            'Source: HIGH Horizons D3.7.'
        ),
    },

    # ── 11. Energy-Efficient Incinerators ─────────────────────────────────────
    'INCINERATOR_TAM': {
        'display_name': 'Biomedical TAM-ENERGY Incinerator',
        'reduces': {'waste_management': Decimal('0.67')},
        'sdg_goals': [3, 12, 13],
        'sectors': ['clinical'],
        'notes': (
            'High-efficiency medical waste incinerator; runs 8,000 hrs/year. '
            'Fuel use 600 L/year vs conventional 1,800 L/year. '
            'Saves 1,200 L fuel/year = 3,072 kgCO₂e/year (double-accounting per D3.7 = 1,536). '
            'CapEx US$37,000, maint US$5,550/year, annual cost saving US$668. '
            'Source: HIGH Horizons D3.7.'
        ),
    },

    # ── 12. Lamp Motion Sensors ───────────────────────────────────────────────
    'LAMP_MOTION_SENSOR': {
        'display_name': 'Lamp Motion Sensors (Philips Hue)',
        'reduces': {'grid_electricity': Decimal('0.03')},
        'sdg_goals': [7, 11, 13],
        'notes': (
            'Reduces lighting electricity from 2,772 kWh to 2,205 kWh for 8-lamp group. '
            'Saves ~70.9 kWh/group/year = 62.6 kgCO₂e/year. '
            'Per 200 sensors: CapEx US$50/sensor, maint US$7.50/sensor, '
            'annual cost saving US$9,276. Source: HIGH Horizons D3.7.'
        ),
    },

    # ── 13. Hybrid Vehicles ───────────────────────────────────────────────────
    'HYBRID_LAND_CRUISER': {
        'display_name': 'Hybrid Vehicle — Toyota Land Cruiser 2024',
        'reduces': {'vehicle_fuel_owned': Decimal('0.39')},
        'sdg_goals': [11, 13],
        'notes': (
            'Improves fuel economy from 14 mpg to 23 mpg; saves 6.57 L/100 km. '
            'At 24,000 km/year: saves 1,576.8 L/year = 3,500.5 kgCO₂e/year. '
            'CapEx US$60,000, maint US$9,000/year, annual cost saving US$484. '
            'Source: HIGH Horizons D3.7.'
        ),
    },
    'HYBRID_PRIUS': {
        'display_name': 'Hybrid Vehicle — Toyota Prius',
        'reduces': {'vehicle_fuel_owned': Decimal('0.44')},
        'sdg_goals': [11, 13],
        'notes': (
            'Prius 4.2 L/100 km vs conventional 7.8 L/100 km. '
            'At 24,000 km/year: saves 792 L/year = 2,027.5 kgCO₂e/year. '
            'CapEx US$26,000, maint US$3,900/year, annual cost saving US$503. '
            'Source: HIGH Horizons D3.7.'
        ),
    },

    # ── 14. Roof & Wall Paint ─────────────────────────────────────────────────
    'WHITE_ROOF_PAINT': {
        'display_name': 'White / Light-Colour Roof & Exterior Wall Paint',
        'reduces': {'grid_electricity': Decimal('0.10')},
        'sdg_goals': [11, 13],
        'notes': (
            'Heat-reflective coatings reduce wall surface temp by 8–10 °C. '
            'Saves ~69.6 kWh/year in A/C = 61.5 kgCO₂e/year. '
            'Per 20 m² paint: CapEx US$20/m², maint US$3/m², annual cost saving US$348. '
            'Source: HIGH Horizons D3.7.'
        ),
    },

    # ── 15. Sustainability Policy ─────────────────────────────────────────────
    'SUSTAINABILITY_POLICY': {
        'display_name': 'Facility Sustainability Policy',
        'reduces': {
            'grid_electricity': Decimal('0.10'),
            'waste_management': Decimal('0.10'),
        },
        'sdg_goals': [13, 17],
        'notes': (
            'Formal climate mitigation policy; evidence shows 4–15 % emission reduction '
            'across all emission areas. CapEx US$10,000 (policy development), '
            'maint US$0, annual net cost –US$2,000 (staff time). '
            'Source: HIGH Horizons D3.7.'
        ),
    },

    # ── 16. Tree Planting ─────────────────────────────────────────────────────
    'TREE_PLANTING': {
        'display_name': 'Tree Planting (Carbon Offset)',
        'reduces': {},
        'sdg_goals': [13, 15],
        'notes': (
            'Average tree sequesters ~21.8 kgCO₂/year. '
            'Per 100 trees: CapEx US$5/tree, maint US$0, '
            'carbon offset ≈ 2.18 tCO₂/year. Net cost saving –US$20 (upkeep). '
            'Source: HIGH Horizons D3.7.'
        ),
    },

    # ── 17. Training & Awareness ──────────────────────────────────────────────
    'TRAINING_AWARENESS': {
        'display_name': 'Staff Training & Sustainability Awareness',
        'reduces': {
            'grid_electricity': Decimal('0.06'),
            'waste_management': Decimal('0.06'),
        },
        'sdg_goals': [4, 13],
        'notes': (
            'Behavioural change contributes 4–8 % CO₂ reduction (Niamir et al.). '
            'Healthcare Without Harm (2020): effective waste segregation reduces '
            'hospital carbon by 15–30 %. CapEx US$2,500, maint US$225/year. '
            'Source: HIGH Horizons D3.7.'
        ),
    },

    # ── 18. Energy-Efficient Laundry ──────────────────────────────────────────
    'EE_LAUNDRY': {
        'display_name': 'Energy-Efficient Laundry Machines (ENERGY STAR)',
        'reduces': {'grid_electricity': Decimal('0.25')},
        'sdg_goals': [7, 13],
        'sectors': ['clinical'],
        'notes': (
            'ENERGY STAR certified washers use 25 % less energy and 33 % less water '
            'than standard models. Source: Natural Resources Canada / HIGH Horizons D3.7.'
        ),
    },

    # ── 19. Research & office Scope-3 interventions ───────────────────────────
    'VIRTUAL_FIRST_TRAVEL': {
        'display_name': 'Virtual-First Travel Policy',
        'reduces': {'flights': Decimal('0.30')},
        'sdg_goals': [13],
        'notes': (
            'Institutional policy: default to virtual attendance, combine trips, '
            'require economy class and train-over-plane where practical. Typical '
            '30 % reduction in flight passenger-km (Tyndall Centre travel strategy; '
            'Concordat for the Environmental Sustainability of Research good practice).'
        ),
    },
    'GREEN_PROCUREMENT': {
        'display_name': 'Sustainable Procurement & Consumables Policy',
        'reduces': {'lab_consumables': Decimal('0.15')},
        'sdg_goals': [12, 13],
        'notes': (
            'Supplier consolidation, packaging take-back, glass-over-plastic '
            'substitution and LEAF-aligned lab practices (e.g. My Green Lab / ACT '
            'label purchasing). Typical 10–20 % reduction in supply-chain '
            'emissions from consumables spend.'
        ),
    },
}


# ---------------------------------------------------------------------------
# End-use share caps — bound appliance-level interventions to the plausible
# share of a category their end-use represents. A lighting retrofit cannot
# abate more electricity than lighting consumes; without this, a single
# "per lamp" entry claims the whole electricity baseline.
#
# Shares approximate commercial-building end-use splits (US EIA CBECS 2018;
# CIBSE Guide F), with cooling raised for hot-climate LMIC settings. These are
# documented modelling assumptions, overridable per site via
# FacilityIntervention.emission_reduction_achieved.
# ---------------------------------------------------------------------------
END_USE_GROUPS = {
    # code_name prefix → (end-use pool name, max share of the target category)
    'LED_':           ('lighting',      Decimal('0.25')),
    'LED_LIGHTING':   ('lighting',      Decimal('0.25')),
    'LAMP_':          ('lighting',      Decimal('0.25')),
    'AC_':            ('cooling',       Decimal('0.30')),
    'FREEZER_':       ('refrigeration', Decimal('0.15')),
    'HEATER_':        ('heating',       Decimal('0.20')),
    'EE_LAUNDRY':     ('laundry',       Decimal('0.10')),
    'WHITE_ROOF':     ('cooling',       Decimal('0.30')),
}


def end_use_group(code_name):
    """Return (pool_name, share_cap) for a device-level intervention, or None."""
    for prefix, group in END_USE_GROUPS.items():
        if code_name.startswith(prefix):
            return group
    return None


# ---------------------------------------------------------------------------
# CarbomicaOptimizer — three-scenario resource allocation
# ---------------------------------------------------------------------------

class CarbomicaOptimizer:
    """
    Implements the three-scenario analysis described in HIGH Horizons D3.7:

      Scenario 1 — Full coverage:   all interventions regardless of budget
      Scenario 2 — Fixed budget:    cheapest interventions first until budget exhausted
      Scenario 3 — Optimised:       greedy knapsack maximising tCO2e reduced per USD

    Inputs are FacilityIntervention ORM records, which carry facility-specific
    implementation and maintenance costs from the database rather than defaults.
    """

    def __init__(self, facility_interventions, budget, total_baseline_emissions,
                 category_baselines=None):
        self.interventions = list(facility_interventions)
        self.budget = Decimal(str(budget))
        self.baseline = Decimal(str(total_baseline_emissions)) if total_baseline_emissions else Decimal('1')
        # Per-category tCO₂e breakdown for the facility (from compute_tco2e).
        # Used to apply each intervention's reduction to the correct emission slice.
        self.category_baselines = category_baselines or {}

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _total_cost(self, fi):
        return (fi.implementation_cost or Decimal('0')) + (fi.maintenance_cost or Decimal('0'))

    def _emission_reduction(self, fi):
        pct = fi.intervention.emission_reduction_percentage or Decimal('0')
        target_cats = fi.intervention.target_category or ''
        if target_cats and self.category_baselines:
            # Apply the % reduction only to the relevant emission category baseline.
            # E.g. Solar PV (70%) applied to grid_electricity tCO₂e, not total.
            relevant_baseline = sum(
                self.category_baselines.get(cat.strip(), Decimal('0'))
                for cat in target_cats.split(',')
            )
            return (pct / 100) * Decimal(str(relevant_baseline))
        # Fallback: apply to total baseline if no category info
        return (pct / 100) * self.baseline

    def _cost_effectiveness(self, fi):
        """tCO2e reduced per USD — the core ranking metric.

        Zero-cost interventions (e.g. refrigerant swaps with no CapEx, avoiding
        N₂O) are infinitely cost-effective — they always rank first so the greedy
        knapsack picks them before any paid intervention.
        """
        cost = self._total_cost(fi)
        reduction = self._emission_reduction(fi)
        if cost <= 0:
            # Return a sentinel larger than any realistic paid-intervention ratio.
            # Using reduction itself as a tiebreaker: higher-impact free actions rank first.
            return Decimal('1e12') + reduction
        return reduction / cost

    # ------------------------------------------------------------------
    # Baseline drawdown — prevents double-counting across interventions
    # that target the same emission category. Each selected intervention
    # draws its % reduction from what REMAINS of the category baseline,
    # so summed scenario reductions can never exceed the baseline itself.
    # ------------------------------------------------------------------

    def _fresh_remaining(self):
        remaining = {k: Decimal(str(v)) for k, v in self.category_baselines.items()}
        remaining['__untargeted__'] = self.baseline
        # End-use pools: each device class may only abate its share of the
        # category (lighting ≤ 25% of electricity, etc.). Pools are sized from
        # the ORIGINAL baselines and drawn down alongside the category itself.
        pools = {}
        for fi in self.interventions:
            group = end_use_group(fi.intervention.code_name)
            if not group:
                continue
            pool_name, share = group
            if pool_name in pools:
                continue
            target_cats = [
                c.strip() for c in (fi.intervention.target_category or '').split(',') if c.strip()
            ]
            pool_base = sum(
                (Decimal(str(self.category_baselines.get(cat, Decimal('0')))) for cat in target_cats),
                Decimal('0'),
            ) if target_cats else self.baseline
            pools[pool_name] = share * pool_base
        remaining['__pools__'] = pools
        return remaining

    def _drawdown_reduction(self, fi, remaining, commit=True):
        pct = fi.intervention.emission_reduction_percentage or Decimal('0')
        target_cats = [
            c.strip() for c in (fi.intervention.target_category or '').split(',') if c.strip()
        ]
        group = end_use_group(fi.intervention.code_name)
        pools = remaining.get('__pools__', {})
        pool_name = group[0] if group else None
        pool_left = pools.get(pool_name) if pool_name is not None else None

        if target_cats and self.category_baselines:
            total = Decimal('0')
            for cat in target_cats:
                available = remaining.get(cat, Decimal('0'))
                if pool_left is not None:
                    available = min(available, pool_left)
                red = (pct / 100) * available
                if commit:
                    remaining[cat] = remaining.get(cat, Decimal('0')) - red
                if pool_left is not None:
                    pool_left -= red
                total += red
            if commit and pool_name is not None:
                pools[pool_name] = pool_left
            return total
        # No category info: draw from the shared untargeted pool.
        available = remaining.get('__untargeted__', self.baseline)
        red = (pct / 100) * available
        if commit:
            remaining['__untargeted__'] = available - red
        return red

    def _build_result(self, fi, priority, reduction=None):
        cost = self._total_cost(fi)
        if reduction is None:
            reduction = self._emission_reduction(fi)
        annual_savings = fi.annual_savings or Decimal('0')
        payback_years = (cost / annual_savings) if annual_savings > 0 else None
        roi = ((annual_savings * 10 - cost) / cost * 100) if cost > 0 else Decimal('0')
        return {
            'priority': priority,
            'intervention_name': fi.intervention.display_name,
            'facility_name': fi.facility.display_name,
            'cost': cost,
            'emission_reduction': reduction,
            'annual_savings': annual_savings,
            'roi': roi,
            'payback_years': payback_years,
            'sdg_goals': [s.strip() for s in (fi.intervention.sdg_goals or '').split(',') if s.strip()],
        }

    def _summarise(self, results):
        total_cost = sum(r['cost'] for r in results)
        total_reduction = sum(r['emission_reduction'] for r in results)
        total_savings = sum(r['annual_savings'] for r in results)
        pct_of_baseline = (
            (total_reduction / self.baseline * 100) if self.baseline > 0 else Decimal('0')
        )
        return {
            'count': len(results),
            'total_cost': total_cost,
            'total_reduction': total_reduction,
            'pct_of_baseline': pct_of_baseline,
            'total_annual_savings': total_savings,
            'budget_remaining': max(self.budget - total_cost, Decimal('0')),
        }

    # ------------------------------------------------------------------
    # Three scenarios
    # ------------------------------------------------------------------

    def full_coverage(self):
        """Scenario 1: apply all interventions, ignoring budget constraint.

        Interventions are applied most-cost-effective first so the highest
        bang-for-buck actions claim baseline emissions before diminishing
        returns kick in for later same-category interventions.
        """
        ordered = sorted(self.interventions, key=self._cost_effectiveness, reverse=True)
        remaining = self._fresh_remaining()
        return [
            self._build_result(fi, i + 1, reduction=self._drawdown_reduction(fi, remaining))
            for i, fi in enumerate(ordered)
        ]

    def fixed_budget(self):
        """Scenario 2: lowest-cost interventions first until budget exhausted."""
        ordered = sorted(self.interventions, key=self._total_cost)
        results, budget_left = [], self.budget
        remaining = self._fresh_remaining()
        for fi in ordered:
            cost = self._total_cost(fi)
            if cost <= budget_left:
                reduction = self._drawdown_reduction(fi, remaining)
                results.append(self._build_result(fi, len(results) + 1, reduction=reduction))
                budget_left -= cost
        return results

    def optimised(self):
        """Scenario 3: greedy knapsack — maximise tCO2e reduction per USD spent.

        True greedy with diminishing returns: after each pick the relevant
        category baseline is drawn down, and every remaining candidate is
        re-scored against what is actually left to abate. A second refrigerant
        swap therefore competes on the residual refrigerant emissions, not the
        original baseline.
        """
        candidates = list(self.interventions)
        results, budget_left = [], self.budget
        remaining = self._fresh_remaining()
        while candidates:
            best, best_score, best_reduction = None, None, None
            for fi in candidates:
                cost = self._total_cost(fi)
                if cost > budget_left:
                    continue
                reduction = self._drawdown_reduction(fi, remaining, commit=False)
                if cost <= 0:
                    score = Decimal('1e12') + reduction
                else:
                    score = reduction / cost
                if best_score is None or score > best_score:
                    best, best_score, best_reduction = fi, score, reduction
            if best is None:
                break
            self._drawdown_reduction(best, remaining)  # commit the drawdown
            results.append(self._build_result(best, len(results) + 1, reduction=best_reduction))
            budget_left -= self._total_cost(best)
            candidates.remove(best)
        return results

    def run_all_scenarios(self):
        full = self.full_coverage()
        fixed = self.fixed_budget()
        opt = self.optimised()
        return {
            'full_coverage': {'results': full, 'summary': self._summarise(full)},
            'fixed_budget': {'results': fixed, 'summary': self._summarise(fixed)},
            'optimised': {'results': opt, 'summary': self._summarise(opt)},
        }


# ---------------------------------------------------------------------------
# Standalone financial helpers
# ---------------------------------------------------------------------------

def calculate_npv(annual_savings, implementation_cost, years=10, discount_rate=DISCOUNT_RATE):
    """
    Net Present Value using an 8 % LMIC public-sector discount rate.
    Returns a positive value when the intervention is financially viable.
    """
    annual_savings = Decimal(str(annual_savings))
    implementation_cost = Decimal(str(implementation_cost))
    npv = -implementation_cost
    for year in range(1, years + 1):
        npv += annual_savings / (1 + discount_rate) ** year
    return round(npv, 2)


class GreenInvestmentAnalyzer:
    """Financial analysis for individual facility interventions."""

    CARBON_CREDIT_PRICE = CARBON_CREDIT_PRICE_USD
    DISCOUNT_RATE = DISCOUNT_RATE

    def calculate_roi(self, implementation_cost, annual_savings, years=10):
        implementation_cost = Decimal(str(implementation_cost))
        annual_savings = Decimal(str(annual_savings))
        if implementation_cost == 0:
            return Decimal('0')
        total_savings = annual_savings * years
        return ((total_savings - implementation_cost) / implementation_cost) * 100

    def calculate_npv(self, implementation_cost, annual_savings, years=10):
        return calculate_npv(annual_savings, implementation_cost, years, self.DISCOUNT_RATE)

    def calculate_payback_period(self, implementation_cost, annual_savings):
        implementation_cost = Decimal(str(implementation_cost))
        annual_savings = Decimal(str(annual_savings))
        if annual_savings <= 0:
            return None
        return implementation_cost / annual_savings

    def calculate_carbon_credits(self, emission_reduction_tco2e):
        return Decimal(str(emission_reduction_tco2e)) * self.CARBON_CREDIT_PRICE


# ---------------------------------------------------------------------------
# Project (award) attribution
#
# Funders increasingly ask for the footprint of an AWARD rather than an
# organisation. Wellcome's environmental sustainability funding policy makes
# staff time to "assess, measure and report on the award's emissions and
# resource usage" an eligible cost, and requires "an auditable record of their
# time on the project" where staff work across more than one award.
#
# An award's footprint is therefore built the way grant finance already works,
# from two parts:
#
#   DIRECT      — purchases charged to the award. Counted in full.
#   APPORTIONED — the award's stated share of a site's shared running
#                 emissions (electricity, waste, fuel, shared travel), on a
#                 declared basis: staff FTE by default, since that is the
#                 record the funder already expects to exist.
#
# The two must never overlap. Procurement lines tagged to THIS award are
# direct; lines tagged to ANOTHER award are excluded from the pool entirely;
# only untagged lines are apportioned. Without that exclusion a site running
# three grants would report each of them a share of the other two's purchases.
# ---------------------------------------------------------------------------

# Categories that are shared site overheads and can only be apportioned.
# Procurement is handled separately because it supports direct attribution.
APPORTIONABLE_FIELDS = [
    'grid_electricity', 'grid_gas', 'bottled_gas', 'liquid_fuel',
    'vehicle_fuel_owned', 'business_travel', 'anaesthetic_gases',
    'refrigeration_gases', 'waste_management', 'medical_inhalers',
    'contractor_logistics', 'flights',
]


# Site travel figures an award's own travel log replaces. Once an award logs its
# journeys, apportioning it a share of the site's flights and road travel as
# well would count the same trips twice.
SITE_TRAVEL_FIELDS = ('flights', 'business_travel')

# ---------------------------------------------------------------------------
# Per-journey factors for the award travel log, kg CO₂e per unit.
#
# Source: UK Government GHG Conversion Factors for Company Reporting 2026
# (DESNZ / DEFRA), flat file v1.2, revised July 2026, sheets "Business travel-
# air" and "Business travel- land":
# https://www.gov.uk/government/publications/greenhouse-gas-reporting-conversion-factors-2026
# (read 2026-10-17). Air factors are the "With RF" rows, matching the site-level
# flights factor. DEFRA gives only "average passenger" for UK domestic flights
# and no first or premium-economy factor for short-haul, so those combinations
# are rejected rather than estimated.
# ---------------------------------------------------------------------------
TRAVEL_FACTOR_SOURCE = (
    'UK Government GHG Conversion Factors for Company Reporting 2026 '
    '(DESNZ/DEFRA), flat file v1.2, July 2026'
)
TRAVEL_FACTOR_URL = (
    'https://www.gov.uk/government/publications/'
    'greenhouse-gas-reporting-conversion-factors-2026'
)

AIR_FACTORS = {  # (haul, cabin) → kg CO₂e per passenger-km, incl. radiative forcing
    ('domestic_uk', 'average'):                  Decimal('0.22928'),
    ('short_haul_uk', 'average'):                Decimal('0.12786'),
    ('short_haul_uk', 'economy'):                Decimal('0.12576'),
    ('short_haul_uk', 'business'):               Decimal('0.18863'),
    ('long_haul_uk', 'average'):                 Decimal('0.15282'),
    ('long_haul_uk', 'economy'):                 Decimal('0.11704'),
    ('long_haul_uk', 'premium_economy'):         Decimal('0.18726'),
    ('long_haul_uk', 'business'):                Decimal('0.33940'),
    ('long_haul_uk', 'first'):                   Decimal('0.46814'),
    ('international_non_uk', 'average'):         Decimal('0.14253'),
    ('international_non_uk', 'economy'):         Decimal('0.10916'),
    ('international_non_uk', 'premium_economy'): Decimal('0.17465'),
    ('international_non_uk', 'business'):        Decimal('0.31656'),
    ('international_non_uk', 'first'):           Decimal('0.43663'),
}

# mode → (kg CO₂e per unit, per passenger?). Car is per vehicle-km, so people
# sharing one car do not multiply it; every other mode is per passenger-km.
SURFACE_FACTORS = {
    'rail_national':      (Decimal('0.03092'), True),   # National rail
    'rail_international': (Decimal('0.01135'), True),   # International rail
    'light_rail':         (Decimal('0.02121'), True),   # Light rail and tram
    'underground':        (Decimal('0.01549'), True),   # London Underground
    'bus':                (Decimal('0.10151'), True),   # Average local bus
    'coach':              (Decimal('0.03948'), True),   # Coach
    'taxi':               (Decimal('0.14861'), True),   # Regular taxi
    'car':                (Decimal('0.16591'), False),  # Average car, unknown fuel
}


def journey_factor(mode, air_haul='', cabin_class=''):
    """kg CO₂e per unit for one journey, or None if DEFRA publishes no factor."""
    if mode == 'air':
        return AIR_FACTORS.get((air_haul, cabin_class or 'average'))
    spec = SURFACE_FACTORS.get(mode)
    return spec[0] if spec else None


def journey_tco2e(mode, distance_km, passengers=1, air_haul='', cabin_class=''):
    """tCO₂e for one logged journey."""
    factor = journey_factor(mode, air_haul, cabin_class)
    if factor is None:
        raise ValueError(f'No DEFRA factor for {mode} / {air_haul} / {cabin_class}')
    per_passenger = mode == 'air' or SURFACE_FACTORS[mode][1]
    people = Decimal(passengers or 1) if per_passenger else Decimal('1')
    return Decimal(str(distance_km or 0)) * people * factor / Decimal('1000')


# ---------------------------------------------------------------------------
# Wellcome travel rules, checked per journey.
#
# Source: Wellcome, Environmental sustainability funding policy, travel section
# (page last updated 1 July 2025, read 2026-10-17). Quotes are verbatim. The
# policy names economy (the default) and business (not funded) only; it is
# silent on premium economy and first, so those are flagged as "not economy"
# without claiming a rule the policy does not state. It does not say whether
# the 10 hours is one way, so the check applies per logged journey.
# ---------------------------------------------------------------------------
WELLCOME_POLICY_URL = (
    'https://wellcome.org/research-funding/guidance/policies-grant-conditions/'
    'environmental-sustainability-funding-policy'
)
RAIL_HOURS_LIMIT = Decimal('10')

POLICY_QUOTES = {
    'rail': ('This includes taking the train for journeys of up to 10 hours '
             '(total travel time including connections).'),
    'rail_exceptions': ('Exceptions may include lack of availability, safety, or '
                        'visa/permit reasons, or in exceptional circumstances such as a '
                        'disability, long-term health condition or caring requirements '
                        'necessitating faster travel.'),
    'economy': 'If flying is unavoidable, using economy class as a default.',
    'business': 'Wellcome does not fund business class flights.',
    'justified': 'All travel requested in grant applications must be justified.',
    'assess': ('should use a tool appropriate to their setting to assess the '
               'environmental impact of their work and to track their efforts to reduce it.'),
    'mitigate': ('Mitigate the remaining carbon emissions of all journeys using '
                 'accredited carbon credits'),
    'accredited': 'Have arrangements to purchase third party accredited carbon credits',
    'lab': ('Laboratories should achieve the minimum level of accreditation offered by '
            'LEAF, My Green Lab or equivalent by the end of 2025.'),
}
LAB_ACCREDITATION_DEADLINE = date(2025, 12, 31)


def lab_status(facility, today):
    """
    Accreditation state of one laboratory site on a given date:
    'accredited' (current LEAF or My Green Lab), 'equivalent' (only a current
    other-scheme award, which Wellcome may or may not accept), or 'none'.
    """
    current = [a for a in facility.lab_accreditations.all() if a.is_current(today)]
    if any(a.scheme in ('leaf', 'my_green_lab') for a in current):
        state = 'accredited'
    elif current:
        state = 'equivalent'
    else:
        state = 'none'
    return {'state': state, 'current': current}


TRAVEL_FLAG_LABELS = {
    'business_class':   'Business-class flights',
    'not_economy':      'Flights above economy (premium economy or first)',
    'rail_feasible':    'Flights where rail is within 10 hours',
    'no_justification': 'Journeys with no justification',
    'rail_unknown':     'Flights with no rail time recorded',
}


def journey_policy_flags(journey):
    """
    Wellcome travel-rule flags for one journey, as a list of dicts with
    code, severity ('fail' | 'warn' | 'info'), message and the policy quote.
    """
    flags = []
    if journey.mode == 'air':
        if journey.rail_hours is None:
            flags.append({
                'code': 'rail_unknown', 'severity': 'info',
                'message': 'Rail time not recorded, so the 10-hour rule cannot be shown to be met.',
                'quote': POLICY_QUOTES['rail'],
            })
        elif journey.rail_hours <= RAIL_HOURS_LIMIT:
            flags.append({
                'code': 'rail_feasible', 'severity': 'warn',
                'message': (f'Rail takes {journey.rail_hours} h door to door, within the '
                            '10-hour limit. Record the exception that applies, or take the train.'),
                'quote': f"{POLICY_QUOTES['rail']} {POLICY_QUOTES['rail_exceptions']}",
            })
        if journey.cabin_class == 'business':
            flags.append({
                'code': 'business_class', 'severity': 'fail',
                'message': 'Business class is not fundable by Wellcome.',
                'quote': POLICY_QUOTES['business'],
            })
        elif journey.cabin_class in ('premium_economy', 'first'):
            flags.append({
                'code': 'not_economy', 'severity': 'warn',
                'message': (f'{journey.get_cabin_class_display()} is not economy, the '
                            "policy's default. The policy does not name this class."),
                'quote': POLICY_QUOTES['economy'],
            })
    if not (journey.purpose or '').strip():
        flags.append({
            'code': 'no_justification', 'severity': 'warn',
            'message': 'No justification recorded for this journey.',
            'quote': POLICY_QUOTES['justified'],
        })
    return flags


VERRA_VCU_URL = 'https://verra.org/programs/verified-carbon-standard/vcs-program-details/'


def credit_position(project, footprint):
    """
    Credits an award needs for its remaining travel emissions, and how far its
    purchases cover them.

    Travel is the logged journeys when there are any; otherwise the award's
    apportioned share of site flights and road travel (the estimate shown on
    the report). Credits are whole units, one per tonne CO₂e (Verra VCU
    definition), so the requirement is rounded up. Only accredited purchases
    count towards cover.
    """
    by_category = footprint['by_category']
    travel = (by_category.get('award_travel', Decimal('0'))
              + sum((by_category.get(f, Decimal('0')) for f in SITE_TRAVEL_FIELDS),
                    Decimal('0')))
    if footprint['travel_logged']:
        basis = 'logged'
    elif travel > 0:
        basis = 'apportioned'
    else:
        basis = 'none'

    purchases = list(project.credit_purchases.all())
    required = travel.to_integral_value(rounding=ROUND_CEILING) if travel > 0 else Decimal('0')
    # Only accredited credits count as cover: the policy asks for "accredited
    # carbon credits", so anything else is reported but not netted off.
    purchased = sum((p.credits_tco2e for p in purchases if p.is_accredited), Decimal('0'))
    not_counted = sum((p.credits_tco2e for p in purchases if not p.is_accredited), Decimal('0'))
    return {
        'travel_tco2e': travel,
        'basis': basis,
        'required': required,
        'purchases': purchases,
        'purchased': purchased,
        'not_counted': not_counted,
        'outstanding': max(required - purchased, Decimal('0')),
        'surplus': max(purchased - required, Decimal('0')),
        'covered': required > 0 and purchased >= required,
        'unaccredited': [p for p in purchases if not p.is_accredited],
        'unretired': [p for p in purchases if not p.retired],
    }


def award_checklist(project, footprint, credits, today=None):
    """
    Wellcome alignment checks for one award. Each row: key, label, state
    ('pass' | 'warn' | 'fail' | 'na'), detail, and the verbatim policy line it
    tests (None where the row is good practice the policy does not state).
    """
    rows = []

    def row(key, label, state, detail, quote):
        rows.append({'key': key, 'label': label, 'state': state,
                     'detail': detail, 'quote': quote})

    # Impact assessed with a tool
    missing = footprint['sites_missing_data']
    if footprint['total'] <= 0 and not missing:
        row('assessed', 'Environmental impact assessed', 'fail',
            'Nothing recorded yet: add sites, journeys or spend charged to the award.',
            POLICY_QUOTES['assess'])
    elif missing:
        row('assessed', 'Environmental impact assessed', 'warn',
            f'{len(missing)} site(s) on the award have no emission data, so their share counts as zero.',
            POLICY_QUOTES['assess'])
    else:
        row('assessed', 'Environmental impact assessed', 'pass',
            f"{footprint['total']:.1f} tCO₂e attributed to the award.",
            POLICY_QUOTES['assess'])

    journeys = footprint['journeys']
    codes = {flag['code'] for r in footprint['journey_rows'] for flag in r['flags']}
    flights = [j for j in journeys if j.mode == 'air']

    # Travel justified
    if not journeys:
        row('justified', 'All travel justified', 'na',
            'No journeys logged on this award.', POLICY_QUOTES['justified'])
    elif 'no_justification' in codes:
        n = sum(1 for r in footprint['journey_rows']
                if any(f['code'] == 'no_justification' for f in r['flags']))
        row('justified', 'All travel justified', 'warn',
            f'{n} of {len(journeys)} journeys have no justification recorded.',
            POLICY_QUOTES['justified'])
    else:
        row('justified', 'All travel justified', 'pass',
            f'All {len(journeys)} journeys carry a justification.', POLICY_QUOTES['justified'])

    # Rail for trips up to 10 hours
    if not flights:
        row('rail', 'Rail used for trips up to 10 hours', 'na',
            'No flights logged.', POLICY_QUOTES['rail'])
    elif 'rail_feasible' in codes or 'rail_unknown' in codes:
        row('rail', 'Rail used for trips up to 10 hours', 'warn',
            'Some flights had a rail option within 10 hours, or no rail time recorded. '
            'Record the exception that applied.',
            POLICY_QUOTES['rail'])
    else:
        row('rail', 'Rail used for trips up to 10 hours', 'pass',
            'Every flight records a rail alternative over 10 hours.', POLICY_QUOTES['rail'])

    # No business class
    if not flights:
        row('business', 'No business-class flights', 'na',
            'No flights logged.', POLICY_QUOTES['business'])
    elif 'business_class' in codes:
        n = sum(1 for j in flights if j.cabin_class == 'business')
        row('business', 'No business-class flights', 'fail',
            f'{n} business-class flight(s) logged.', POLICY_QUOTES['business'])
    else:
        row('business', 'No business-class flights', 'pass',
            'No business-class flights logged.', POLICY_QUOTES['business'])

    # Remaining travel emissions mitigated with credits
    if credits['required'] <= 0:
        row('mitigated', 'Remaining travel emissions mitigated', 'na',
            'No travel emissions to mitigate.', POLICY_QUOTES['mitigate'])
    elif credits['covered']:
        row('mitigated', 'Remaining travel emissions mitigated', 'pass',
            f"{credits['purchased']} accredited credits cover {credits['required']} required.",
            POLICY_QUOTES['mitigate'])
    else:
        row('mitigated', 'Remaining travel emissions mitigated', 'warn',
            f"{credits['outstanding']} of {credits['required']} credits still to buy.",
            POLICY_QUOTES['mitigate'])

    # Credits third-party accredited
    if not credits['purchases']:
        row('accredited', 'Credits third-party accredited', 'na',
            'No credits recorded.', POLICY_QUOTES['accredited'])
    elif credits['unaccredited']:
        row('accredited', 'Credits third-party accredited', 'fail',
            f"{len(credits['unaccredited'])} purchase(s) not from an accredited standard.",
            POLICY_QUOTES['accredited'])
    else:
        row('accredited', 'Credits third-party accredited', 'pass',
            'All purchases are from an accredited standard.', POLICY_QUOTES['accredited'])

    # Laboratory accreditation for lab sites on the award
    today = today or date.today()
    labs = [r['facility'] for r in footprint['site_rows'] if r['facility'].is_laboratory]
    statuses = [(f, lab_status(f, today)) for f in labs]
    missing = [f for f, st in statuses if st['state'] == 'none']
    equivalent = [f for f, st in statuses if st['state'] == 'equivalent']
    if not labs:
        row('lab', 'Laboratories accredited', 'na',
            'No site on this award is marked as having laboratories.', POLICY_QUOTES['lab'])
    elif missing:
        overdue = today > LAB_ACCREDITATION_DEADLINE
        names = ', '.join(f.display_name for f in missing)
        row('lab', 'Laboratories accredited', 'fail' if overdue else 'warn',
            f"No current accreditation: {names}."
            + (' The end-of-2025 deadline has passed.' if overdue else ''),
            POLICY_QUOTES['lab'])
    elif equivalent:
        names = ', '.join(f.display_name for f in equivalent)
        row('lab', 'Laboratories accredited', 'warn',
            f'Only an "equivalent" scheme recorded for {names}; confirm Wellcome accepts it.',
            POLICY_QUOTES['lab'])
    else:
        row('lab', 'Laboratories accredited', 'pass',
            f'All {len(labs)} lab site(s) hold current LEAF or My Green Lab accreditation.',
            POLICY_QUOTES['lab'])

    # Retirement: good practice, not stated in the policy
    if not credits['purchases']:
        row('retired', 'Credits retired on the registry', 'na',
            'No credits recorded.', None)
    elif credits['unretired']:
        row('retired', 'Credits retired on the registry', 'warn',
            f"{len(credits['unretired'])} purchase(s) not yet marked retired.", None)
    else:
        row('retired', 'Credits retired on the registry', 'pass',
            'All purchases marked retired.', None)

    return rows


# ---------------------------------------------------------------------------
# Reduction measures an applicant can commit to, each with the verbatim line of
# Wellcome's Environmental sustainability funding policy it comes from (read
# 2026-10-17). Grouped by the policy's own headings.
# ---------------------------------------------------------------------------
REDUCTION_MEASURES = {
    # key: (group, short label, policy quote)
    'virtual': ('Travel', 'Meet virtually where possible',
                'Use alternatives (such as video conferencing, hybrid meetings and attending '
                'conferences virtually) where possible.'),
    'local_skills': ('Travel', 'Use local skills for fieldwork',
                     'Leverage existing local skills for fieldwork or if necessary, upskill others '
                     'who are already located in the field rather than to travel to site themselves.'),
    'rail': ('Travel', 'Train for trips up to 10 hours', POLICY_QUOTES['rail']),
    'economy': ('Travel', 'Economy class when flying', POLICY_QUOTES['economy']),
    'equipment_off': ('Energy', 'Switch equipment off when not in use',
                      'Turn off equipment, including laminar flow cabinets when not in use '
                      '(for example overnight).'),
    'fume_hoods': ('Energy', 'Close fume hoods', 'Close fume hoods when not in use.'),
    'freezers': ('Energy', 'Ultra-low freezers at -70 °C',
                 'Set ultralow freezers no lower than -70 degrees Celsius.'),
    'asset_check': ('Reuse', 'Check inventories before buying',
                    'Check internal inventories/asset registries at host organisations for '
                    'existing equipment, materials and consumables before purchasing new items.'),
    'second_hand': ('Reuse', 'Second-hand or reconditioned equipment',
                    'Use second hand or reconditioned equipment where available, viable and more '
                    'sustainable than purchasing new.'),
    'share_equipment': ('Reuse', 'Share equipment',
                        'Share equipment with other researchers/organisations where available and '
                        'viable, rather than purchasing one of everything each.'),
    'maintenance': ('Reuse', 'Maintenance contracts so items are repaired',
                    'Use maintenance contracts so items can be repaired rather than recycled as '
                    'much as possible.'),
    'reusable': ('Consumables', 'Reusable instead of single-use plastics',
                 'Avoid single-use plastics where reusable alternatives are available and viable.'),
    'min_size': ('Consumables', 'Smallest plastic consumables needed',
                 'Use plastic consumables with the minimum size required.'),
    'recycling': ('Waste', 'Use institutional recycling',
                  'Use institutional recycling facilities, particularly for clean packaging, and use '
                  'general or hazardous waste bins only when unavoidable.'),
    'recycled_materials': ('Waste', 'Recycled or recyclable materials',
                           'Use materials, consumables and equipment that are made from recycled '
                           'materials and/or can be recycled at the end of their useful life where viable.'),
}


# ---------------------------------------------------------------------------
# Sustainability costs Wellcome says it will pay for, each with the verbatim
# line from the policy's "Wellcome will pay for" list (read 2026-10-17).
# ---------------------------------------------------------------------------
ELIGIBLE_COSTS = {
    # key: (label, policy heading, quote)
    'staff_measurement': (
        'Staff time to measure and report emissions', 'Project staff',
        'Time for technical experts to advise, assess, measure and report on the '
        'award\u2019s emissions and resource usage.'),
    'travel_credits': (
        'Carbon credits for remaining travel', 'Travel',
        'The cost to mitigate the carbon from remaining essential travel related to '
        'Wellcome grants through third-party accredited carbon credits.'),
    'low_carbon_travel': (
        'Lower-carbon travel', 'Travel',
        'Essential travel by the most carbon efficient mode and class of transport, even '
        'if cheaper less sustainable options are available.'),
    'hybrid_tools': (
        'Hybrid meeting hardware and software', 'Travel',
        'Computer hardware and software to enable hybrid meetings (for example business '
        'Zoom or Teams subscriptions where a collaborator does not already have these and '
        'where free versions are unsuitable).'),
    'lab_accreditation': (
        'Lead applicant\u2019s lab accreditation', 'Measuring and monitoring',
        'The cost of adding the lead applicants\u2019 laboratory to LEAF, My Green Lab or '
        'equivalent accreditation programme (we won\u2019t pay for an entire '
        'organisation\u2019s membership).'),
    'sustainable_materials': (
        'Sustainable materials and consumables', 'Materials and consumables',
        'Sustainable versions of the materials and consumables required for research.'),
    'efficient_equipment': (
        'Second-hand, efficient or maintained equipment', 'Equipment',
        'Second hand or reconditioned equipment. New efficient equipment where it is the '
        'more sustainable option (taking into account embodied carbon of manufacture). '
        'Maintenance of existing equipment where it is viable as an alternative to '
        'purchasing new equipment.'),
    'cpd_training': (
        'Sustainability training (CPD)', 'Continuing Professional Development',
        'our CPD policy allows up to \u00a3500 per person per year for career-based training '
        '... This funding can be used for training on how environmental sustainability '
        'relates to research and how to use tools to assess the sustainability of the research.'),
    'lca': (
        'Life cycle assessment of research outputs', 'Innovation',
        'Life cycle assessments for any products, tools or therapy developed as an output '
        'of research can be costed into outputs management plans.'),
}

# First-person wording for each measure in the draft application text. These
# are drafting aids for the applicant to edit, not policy quotations.
MEASURE_COMMITMENTS = {
    'virtual': 'hold meetings and attend conferences virtually where possible',
    'local_skills': 'use local skills for fieldwork, and upskill staff already in the field, instead of travelling to site',
    'rail': 'take the train for journeys of up to 10 hours door to door',
    'economy': 'fly economy class when flying is unavoidable',
    'equipment_off': 'switch equipment, including laminar flow cabinets, off when not in use',
    'fume_hoods': 'close fume hoods when not in use',
    'freezers': 'set ultra-low freezers no lower than -70 °C',
    'asset_check': 'check institutional inventories and asset registries before buying equipment or consumables',
    'second_hand': 'use second-hand or reconditioned equipment where viable',
    'share_equipment': 'share equipment with other groups instead of buying duplicates',
    'maintenance': 'use maintenance contracts so equipment is repaired rather than replaced',
    'reusable': 'replace single-use plastics with reusable alternatives where viable',
    'min_size': 'use the smallest plastic consumables the work needs',
    'recycling': 'use institutional recycling, keeping general and hazardous waste bins for what cannot be recycled',
    'recycled_materials': 'choose materials and equipment made from recycled content or recyclable at end of life',
}

MEASURE_GROUP_INTROS = {
    'Travel': 'To reduce travel emissions, the team will',
    'Energy': 'To reduce energy use, the team will',
    'Reuse': 'To reuse equipment and materials, the team will',
    'Consumables': 'To reduce consumables, the team will',
    'Waste': 'To reduce and recycle waste, the team will',
}


def _join_phrases(phrases):
    if len(phrases) <= 2:
        return ' and '.join(phrases)
    return '; '.join(phrases[:-1]) + '; and ' + phrases[-1]


def application_statement(project, estimate, footprint):
    """
    Draft text for the application's environmental sustainability section,
    built only from the applicant's own inputs. Returns paragraphs, the
    figures each number came from, and warnings to fix before submitting.
    """
    paragraphs, sources, warnings = [], [], []
    rows = {r['label']: r for r in estimate['rows']}
    travel = rows['Travel']['estimate']
    spend_t = rows['Purchases charged to the award']['estimate']
    site_t = rows['Share of site running emissions']['estimate']
    trips = [r['journey'] for r in estimate['planned_trips']]
    spend_usd = sum((line.spend_usd for line in estimate['planned_lines']), Decimal('0'))
    n_sites = len(footprint['site_rows'])

    parts = []
    if trips:
        parts.append(f'{len(trips)} planned trip{"s" if len(trips) != 1 else ""} ({travel:.1f} tCO₂e)')
        sources.append(f'Travel {travel:.2f} t: sum of {len(trips)} planned trips in the estimate.')
    if estimate['planned_lines']:
        parts.append(f'planned purchases of ${spend_usd:,.0f} ({spend_t:.1f} tCO₂e)')
        sources.append(f'Purchases {spend_t:.2f} t: {len(estimate["planned_lines"])} planned lines '
                       'at spend-based factors.')
    if n_sites:
        parts.append(f'the project\'s share of running emissions at {n_sites} '
                     f'site{"s" if n_sites != 1 else ""} ({site_t:.1f} tCO₂e)')
        sources.append(f'Site share {site_t:.2f} t: declared shares of each site\'s latest '
                       'emission record, excluding site travel.')
    if parts:
        paragraphs.append(
            f'We estimate the project\'s carbon footprint at {estimate["estimate_total"]:.1f} tCO₂e, '
            f'made up of {_join_phrases(parts)}. Travel uses the UK Government 2026 '
            'business-travel conversion factors; purchases use spend-based factors.'
        )

    chosen = [k for k in REDUCTION_MEASURES if k in (project.reduction_measures or [])]
    for group, intro in MEASURE_GROUP_INTROS.items():
        phrases = [MEASURE_COMMITMENTS[k] for k in chosen if REDUCTION_MEASURES[k][0] == group]
        text = f'{intro} {_join_phrases(phrases)}.' if phrases else ''
        if group == 'Travel' and estimate['credits_for_plan'] > 0:
            credit_text = (f'Remaining travel emissions of {travel:.1f} tCO₂e will be mitigated with '
                           f'{estimate["credits_for_plan"]:.0f} third-party accredited carbon credits')
            if estimate['credit_budget_usd'] is not None:
                credit_text += (f', budgeted at ${estimate["credit_budget_usd"]:,.0f} '
                                f'(${project.credit_price_usd:,.2f} per credit)')
                sources.append(f'Credit budget: {estimate["credits_for_plan"]:.0f} credits × '
                               f'${project.credit_price_usd:,.2f}, the price entered.')
            text = (text + ' ' if text else '') + credit_text + '.'
        if text:
            paragraphs.append(text)

    if estimate['cost_lines']:
        items = [f'{c.label.lower()} (${c.amount_usd:,.0f})' for c in estimate['cost_lines']]
        paragraphs.append(
            f'The budget includes ${estimate["costs_total"]:,.0f} of sustainability costs that '
            f'Wellcome lists as eligible: {_join_phrases(items)}.'
        )
        sources.append(f'Sustainability costs ${estimate["costs_total"]:,.2f}: '
                       f'{len(estimate["cost_lines"])} budget lines entered.')

    if project.reduction_notes:
        paragraphs.append(project.reduction_notes.strip())

    for row in estimate['planned_trips']:
        j = row['journey']
        for flag in row['flags']:
            if flag['severity'] in ('fail', 'warn'):
                warnings.append(f'{j.origin} → {j.destination}: {flag["message"]}')
    if not chosen and not project.reduction_notes:
        warnings.append('No reduction measures chosen yet.')

    return {'paragraphs': paragraphs, 'sources': sources, 'warnings': warnings,
            'text': '\n\n'.join(paragraphs)}


def project_estimate(project, footprint, credits):
    """
    Application-stage estimate for an award, laid beside the actuals.

    Estimate = the award's share of its sites' running emissions (excluding
    site travel, which planned trips replace) + planned trips + planned spend.
    The site share uses each site's latest record, so it is the same figure in
    both columns. Actual travel is the credit-position travel figure (logged
    journeys, or the site-travel estimate when none are logged).
    """
    by_category = footprint['by_category']
    site_travel = sum((by_category.get(f, Decimal('0')) for f in SITE_TRAVEL_FIELDS),
                      Decimal('0'))
    site_share = footprint['apportioned_total'] - site_travel

    planned_trips = list(project.journeys.filter(is_planned=True))
    planned_travel = sum((j.tco2e() for j in planned_trips), Decimal('0'))
    planned_lines = list(project.planned_spend.all())
    planned_spend = sum((line.tco2e() for line in planned_lines), Decimal('0'))

    actual_travel = credits['travel_tco2e']
    actual_spend = footprint['direct_total'] - footprint['travel_total']

    rows = [
        {'label': 'Travel', 'estimate': planned_travel, 'actual': actual_travel},
        {'label': 'Purchases charged to the award', 'estimate': planned_spend,
         'actual': actual_spend},
        {'label': 'Share of site running emissions', 'estimate': site_share,
         'actual': site_share},
    ]
    for r in rows:
        r['difference'] = r['actual'] - r['estimate']
    estimate_total = site_share + planned_travel + planned_spend
    actual_total = site_share + actual_travel + actual_spend

    cost_lines = list(project.sustainability_costs.all())

    credits_for_plan = (planned_travel.to_integral_value(rounding=ROUND_CEILING)
                        if planned_travel > 0 else Decimal('0'))
    price = project.credit_price_usd
    return {
        'planned_trips': [{'journey': j, 'flags': journey_policy_flags(j)} for j in planned_trips],
        'planned_lines': planned_lines,
        'rows': rows,
        'estimate_total': estimate_total,
        'actual_total': actual_total,
        'difference': actual_total - estimate_total,
        'credits_for_plan': credits_for_plan,
        'credit_budget_usd': (credits_for_plan * price) if price is not None else None,
        'measures': [
            {'key': k, 'group': g, 'label': label, 'quote': q}
            for k, (g, label, q) in REDUCTION_MEASURES.items()
            if k in (project.reduction_measures or [])
        ],
        'has_plan': bool(planned_trips or planned_lines),
        'cost_lines': cost_lines,
        'costs_total': sum((c.amount_usd for c in cost_lines), Decimal('0')),
        'credit_cost_budgeted': any(c.kind == 'travel_credits' for c in cost_lines),
    }


def _latest_record(facility):
    from appname.models import EmissionData
    return (
        EmissionData.objects
        .filter(emission_source__facility=facility)
        .order_by('-date', '-id')
        .first()
    )


def project_footprint(project):
    """
    Attribute emissions to one award.

    Returns a dict with per-site rows, the direct/apportioned split, a category
    breakdown, scope totals, and the procurement hot spots for spend charged to
    the award. Sites with no emission record are reported so the gap is visible
    rather than silently reducing the total. Logged journeys are direct, and once
    any exist they replace the award's share of SITE_TRAVEL_FIELDS.
    """
    from appname.models import ProcurementLine

    site_rows = []
    by_category = {field: Decimal('0') for field in APPORTIONABLE_FIELDS}
    by_category['lab_consumables'] = Decimal('0')
    by_category['award_travel'] = Decimal('0')
    direct_total = Decimal('0')
    apportioned_total = Decimal('0')
    direct_lines = []

    journeys = list(project.journeys.filter(is_planned=False))
    travel_logged = bool(journeys)
    apportioned_fields = [
        field for field in APPORTIONABLE_FIELDS
        if not (travel_logged and field in SITE_TRAVEL_FIELDS)
    ]

    for project_site in project.sites.select_related('facility').all():
        facility = project_site.facility
        share = (project_site.share_pct or Decimal('0')) / Decimal('100')
        record = _latest_record(facility)
        if record is None:
            site_rows.append({
                'site_id': project_site.id,
                'facility': facility,
                'share_pct': project_site.share_pct,
                'basis_note': project_site.basis_note,
                'period': None,
                'apportioned': Decimal('0'),
                'direct': Decimal('0'),
                'total': Decimal('0'),
                'missing_data': True,
            })
            continue

        full = compute_tco2e(record, facility.country, facility.sector)

        site_apportioned = Decimal('0')
        for field in apportioned_fields:
            value = full.get(field, Decimal('0')) * share
            by_category[field] += value
            site_apportioned += value

        # Procurement: direct lines in full, untagged lines apportioned, other
        # awards' lines excluded from the pool altogether.
        lines = list(record.procurement_lines.all())
        if lines:
            site_direct = sum(
                (line.tco2e() for line in lines if line.project_id == project.id),
                Decimal('0'),
            )
            untagged_pool = sum(
                (line.tco2e() for line in lines if line.project_id is None),
                Decimal('0'),
            )
            direct_lines.extend(
                line for line in lines if line.project_id == project.id
            )
        else:
            # Un-itemised site: the blended procurement figure is shared, so it
            # can only be apportioned.
            site_direct = Decimal('0')
            untagged_pool = full.get('lab_consumables', Decimal('0'))

        procurement_apportioned = untagged_pool * share
        by_category['lab_consumables'] += procurement_apportioned + site_direct
        site_apportioned += procurement_apportioned

        direct_total += site_direct
        apportioned_total += site_apportioned
        site_rows.append({
            'site_id': project_site.id,
            'facility': facility,
            'share_pct': project_site.share_pct,
            'basis_note': project_site.basis_note,
            'period': record.date,
            'apportioned': site_apportioned,
            'direct': site_direct,
            'total': site_apportioned + site_direct,
            'missing_data': False,
        })

    travel_total = sum((j.tco2e() for j in journeys), Decimal('0'))
    by_category['award_travel'] = travel_total
    journey_rows = [{'journey': j, 'flags': journey_policy_flags(j)} for j in journeys]
    flag_counts = {}
    for row in journey_rows:
        for flag in row['flags']:
            entry = flag_counts.setdefault(flag['code'], {
                'code': flag['code'], 'label': TRAVEL_FLAG_LABELS[flag['code']],
                'severity': flag['severity'], 'count': 0,
            })
            entry['count'] += 1
    severity_order = {'fail': 0, 'warn': 1, 'info': 2}
    travel_flag_summary = sorted(
        flag_counts.values(), key=lambda e: (severity_order[e['severity']], e['code']))
    direct_total += travel_total

    total = direct_total + apportioned_total
    category_rows = sorted(
        (
            {'field': field, 'tco2e': value}
            for field, value in by_category.items() if value > 0
        ),
        key=lambda row: row['tco2e'], reverse=True,
    )

    return {
        'site_rows': site_rows,
        'category_rows': category_rows,
        'by_category': by_category,
        'direct_total': direct_total,
        'apportioned_total': apportioned_total,
        'total': total,
        'direct_share_pct': (direct_total / total * 100) if total else Decimal('0'),
        'procurement_rows': _project_procurement_rows(direct_lines),
        'sites_missing_data': [r for r in site_rows if r['missing_data']],
        'journeys': journeys,
        'journey_rows': journey_rows,
        'travel_flag_summary': travel_flag_summary,
        'travel_total': travel_total,
        'travel_logged': travel_logged,
    }


def _project_procurement_rows(lines):
    """Per-category rollup of spend charged directly to an award."""
    if not lines:
        return []
    totals = {}
    for line in lines:
        row = totals.setdefault(line.category, {
            'category': line.category,
            'label': line.category_label,
            'spend': Decimal('0'),
            'tco2e': Decimal('0'),
        })
        row['spend'] += line.spend_usd or Decimal('0')
        row['tco2e'] += line.tco2e()
    rows = sorted(totals.values(), key=lambda r: r['tco2e'], reverse=True)
    grand = sum((r['tco2e'] for r in rows), Decimal('0'))
    for row in rows:
        row['share'] = (row['tco2e'] / grand * 100) if grand else Decimal('0')
    return rows
