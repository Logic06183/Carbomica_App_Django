"""
Verdex — Carbon emissions optimisation engine.

Methodology aligned with GHG Protocol Corporate Standard, IPCC AR6
emission factors, IEA country grid factors, DEFRA conversion factors,
and the HIGH Horizons D3.7 intervention catalogue
(DOI: 10.5281/zenodo.12730527).

Three-scenario optimisation: full coverage, fixed budget, optimised
(greedy knapsack ranking by tCO₂e reduced per USD).
"""
from decimal import Decimal

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
    rather than silently reducing the total.
    """
    from appname.models import ProcurementLine

    site_rows = []
    by_category = {field: Decimal('0') for field in APPORTIONABLE_FIELDS}
    by_category['lab_consumables'] = Decimal('0')
    direct_total = Decimal('0')
    apportioned_total = Decimal('0')
    direct_lines = []

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
        for field in APPORTIONABLE_FIELDS:
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
