"""
CARBOMICA — CARBOn Mitigation Intervention for healthCare fAcilities
Optimization engine aligned with the HIGH Horizons project methodology.

Reference: HIGH Horizons D3.7 — Report on the tool for modelling of
alternative mitigation interventions (DOI: 10.5281/zenodo.12730527)

Partners: Wits Planetary Health (ZA), CeSHHAR (ZW), Burnet Institute (AU),
          Aga Khan Health Service Kenya (KE)
Funded by: European Union — Horizon Europe Grant No. 101057843 (HIGH Horizons)
"""
from decimal import Decimal

# ---------------------------------------------------------------------------
# Country-specific electricity costs (USD / kWh)
# Sources: ZESA (ZW), Eskom standard tariff (ZA), Kenya Power residential (KE)
# ---------------------------------------------------------------------------
ELECTRICITY_COSTS = {
    'ZW': Decimal('0.098'),
    'ZA': Decimal('0.131'),
    'KE': Decimal('0.117'),
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
    'ZW':    Decimal('0.000556'),   # Zimbabwe  — coal-dominated ZESA grid
    'ZA':    Decimal('0.000928'),   # S. Africa — Eskom ≈ 85 % coal
    'KE':    Decimal('0.000032'),   # Kenya     — > 90 % renewables
    'OTHER': Decimal('0.000400'),   # SSA default
}

EMISSION_FACTORS = {
    # field_name: tCO₂e per unit (unit shown in parentheses)
    'grid_electricity':    None,                  # country-specific — see ELECTRICITY_EF
    'grid_gas':            Decimal('0.00202'),    # per m³ natural gas (piped)
    'bottled_gas':         Decimal('0.00214'),    # per kg LPG
    'liquid_fuel':         Decimal('0.00268'),    # per litre diesel/petrol
    'vehicle_fuel_owned':  Decimal('0.00268'),    # per litre (owned fleet diesel)
    'business_travel':     Decimal('0.000171'),   # per km (average medium car)
    'anaesthetic_gases':   Decimal('0.802'),      # per kg anaesthetic agent consumed
    'refrigeration_gases': Decimal('1.800'),      # per kg refrigerant lost/recharged
    'waste_management':    Decimal('0.467'),      # per tonne clinical waste
    'medical_inhalers':    Decimal('0.0189'),     # per pMDI unit dispensed
    'contractor_logistics': Decimal('0.000267'), # per km contracted vehicle travel
}


def compute_tco2e(emission_data, country='OTHER'):
    """
    Convert raw usage quantities stored in an EmissionData record to tCO₂e.

    Args:
        emission_data: EmissionData instance (raw physical units per field).
        country:       ISO-2 country code of the facility (for electricity EF).

    Returns:
        dict with one key per emission field (tCO₂e value) plus 'total'.
    """
    electricity_ef = ELECTRICITY_EF.get(country, ELECTRICITY_EF['OTHER'])
    results = {}
    for field, factor in EMISSION_FACTORS.items():
        raw = getattr(emission_data, field, None) or Decimal('0')
        ef = electricity_ef if field == 'grid_electricity' else (factor or Decimal('0'))
        results[field] = Decimal(str(raw)) * ef
    results['total'] = sum(results.values())
    return results


def sum_tco2e(emission_data_qs, country='OTHER'):
    """Sum tCO₂e across a queryset of EmissionData records for one facility."""
    return sum(compute_tco2e(ed, country)['total'] for ed in emission_data_qs) or Decimal('0')


# ---------------------------------------------------------------------------
# CARBOMICA intervention library
# Emission category keys match EmissionData model fields.
# 'reduces' values are the fractional reduction in that emission category.
# Sourced from CARBOMICA D3.7, Mt Darwin Hospital and AKHS Mombasa case studies.
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
    # Source: CARBOMICA Carbon Saving Calculator (ZW ZESA EF = 0.883 kgCO2e/kWh)
    'LED_WATT_5': {
        'display_name': 'LED Lights — 5W Wattage Reduction per Lamp',
        'reduces': {'grid_electricity': Decimal('0.20')},
        'sdg_goals': [7, 11, 13],
        'notes': (
            '25W → 20W lamp swap. Saves 21.9 kWh/lamp/year = 19.3 kgCO₂e/lamp/year. '
            'Default batch 100 lamps — CapEx US$6/lamp, maint US$0.18/lamp, '
            'annual cost saving US$920. Source: CARBOMICA D3.7 Carbon Saving Calculator.'
        ),
    },
    'LED_WATT_10': {
        'display_name': 'LED Lights — 10W Wattage Reduction per Lamp',
        'reduces': {'grid_electricity': Decimal('0.50')},
        'sdg_goals': [7, 11, 13],
        'notes': (
            '20W → 10W lamp swap. Saves 43.8 kWh/lamp/year = 13.9 kgCO₂e/lamp/year. '
            'Default batch 20 lamps — CapEx US$2/lamp, maint US$0.06/lamp, '
            'annual cost saving US$184. Source: CARBOMICA D3.7.'
        ),
    },
    'LED_WATT_20': {
        'display_name': 'LED Lights — 20W Wattage Reduction per Lamp',
        'reduces': {'grid_electricity': Decimal('0.80')},
        'sdg_goals': [7, 11, 13],
        'notes': (
            '25W → 5W lamp swap. Saves 87.6 kWh/lamp/year = 77.4 kgCO₂e/lamp/year. '
            'Default batch 20 lamps — CapEx US$8/lamp, maint US$0.24/lamp, '
            'annual cost saving US$368. Source: CARBOMICA D3.7.'
        ),
    },
    'LED_WATT_50': {
        'display_name': 'LED Lights — 50W Wattage Reduction per Lamp',
        'reduces': {'grid_electricity': Decimal('0.50')},
        'sdg_goals': [7, 11, 13],
        'notes': (
            '100W → 50W lamp swap. Saves 219 kWh/lamp/year = 193.4 kgCO₂e/lamp/year. '
            'Default batch 20 lamps — CapEx US$8/lamp, maint US$0.24/lamp, '
            'annual cost saving US$920. Source: CARBOMICA D3.7.'
        ),
    },
    'LED_WATT_95': {
        'display_name': 'LED Lights — 95W Wattage Reduction per Lamp',
        'reduces': {'grid_electricity': Decimal('0.95')},
        'sdg_goals': [7, 11, 13],
        'notes': (
            '100W → 5W lamp swap. Saves 416.1 kWh/lamp/year = 367.4 kgCO₂e/lamp/year. '
            'Default batch 20 lamps — CapEx US$10/lamp, maint US$0.30/lamp, '
            'annual cost saving US$1,748. Source: CARBOMICA D3.7.'
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
            'annual cost saving US$1,555. Source: CARBOMICA D3.7 Cost Calculator.'
        ),
    },
    'SOLAR_5KVA': {
        'display_name': 'Solar PV System — 5 kVA',
        'reduces': {'grid_electricity': Decimal('0.15')},
        'sdg_goals': [7, 13],
        'notes': (
            '5 kVA / 5 kWp system generates ~8,172 kWh/year (ZW). '
            'Saves 2,217.9 kgCO₂e/year. CapEx US$4,000, maint US$3,000/year, '
            'annual cost saving US$2,136. Source: CARBOMICA D3.7.'
        ),
    },
    'SOLAR_10KVA': {
        'display_name': 'Solar PV System — 10 kVA',
        'reduces': {'grid_electricity': Decimal('0.30')},
        'sdg_goals': [7, 13],
        'notes': (
            '10 kVA / 10 kWp system generates ~16,344 kWh/year (ZW). '
            'Saves 13,678.1 kgCO₂e/year. CapEx US$11,000, maint US$8,250/year, '
            'annual cost saving US$3,362. Source: CARBOMICA D3.7.'
        ),
    },
    'SOLAR_100KWP': {
        'display_name': 'Solar PV System — 100 kWp',
        'reduces': {'grid_electricity': Decimal('0.70')},
        'sdg_goals': [7, 13],
        'notes': (
            '100 kWp system generates ~170,558 kWh/year (ZW). '
            'Saves 142,825.3 kgCO₂e/year. CapEx US$80,000, maint US$60,000/year, '
            'annual cost saving US$30,917. Source: CARBOMICA D3.7.'
        ),
    },
    'SOLAR_150KWP': {
        'display_name': 'Solar PV System — 150 kWp',
        'reduces': {'grid_electricity': Decimal('0.85')},
        'sdg_goals': [7, 13],
        'notes': (
            '150 kWp system generates ~255,837 kWh/year (ZW). '
            'Saves 214,237.9 kgCO₂e/year. CapEx US$153,000, maint US$114,750/year, '
            'annual cost saving US$43,716. Source: CARBOMICA D3.7.'
        ),
    },
    'SOLAR_600KWP': {
        'display_name': 'Solar PV System — 600 kWp',
        'reduces': {'grid_electricity': Decimal('0.99')},
        'sdg_goals': [7, 13],
        'notes': (
            '600 kWp system generates ~1,023,000 kWh/year (ZW). '
            'Saves 856,660.2 kgCO₂e/year. CapEx US$612,000, maint US$459,000/year, '
            'annual cost saving US$172,690. Source: CARBOMICA D3.7.'
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
            'Source: CARBOMICA D3.7.'
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
            'Source: CARBOMICA D3.7.'
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
            'Source: CARBOMICA D3.7.'
        ),
    },
    'REFRIG_R134A_R1234ZE': {
        'display_name': 'Refrigerant Swap — R134a to R1234ze (HFO)',
        'reduces': {'refrigeration_gases': Decimal('0.99')},
        'sdg_goals': [13],
        'notes': (
            'R1234ze GWP < 1 vs R134a GWP 1,430. '
            'Saves 1,429 kgCO₂e per kg swapped. Used in chillers / commercial refrigeration. '
            'Per 20 kg batch: cost saving US$400. Source: CARBOMICA D3.7.'
        ),
    },
    'REFRIG_R410A_R1234ZE': {
        'display_name': 'Refrigerant Swap — R410a to R1234ze (HFO)',
        'reduces': {'refrigeration_gases': Decimal('0.99')},
        'sdg_goals': [13],
        'notes': (
            'R1234ze GWP < 1 vs R410a GWP 2,088. '
            'Saves 2,087 kgCO₂e per kg swapped. Used in A/C and heat pumps. '
            'Per 20 kg batch: cost saving –US$200 (HFO premium). Source: CARBOMICA D3.7.'
        ),
    },
    'REFRIG_R410A_R32': {
        'display_name': 'Refrigerant Swap — R410a to R32',
        'reduces': {'refrigeration_gases': Decimal('0.68')},
        'sdg_goals': [13],
        'notes': (
            'R32 GWP 675 vs R410a GWP 2,088. '
            'Saves 1,413 kgCO₂e per kg swapped. Modern A/C systems. '
            'Per 20 kg batch: cost saving US$700. Source: CARBOMICA D3.7.'
        ),
    },
    'REFRIG_R404A_R448A': {
        'display_name': 'Refrigerant Swap — R404a to R448A (Solstice® N40)',
        'reduces': {'refrigeration_gases': Decimal('0.68')},
        'sdg_goals': [13],
        'notes': (
            'R448A GWP ≈ 1,273 vs R404A GWP 3,922. '
            'Saves 2,649 kgCO₂e per kg swapped. Commercial refrigeration. '
            'Per 20 kg batch: cost saving US$300. Source: CARBOMICA D3.7.'
        ),
    },
    'REFRIG_R22_R290': {
        'display_name': 'Refrigerant Swap — R22 to R290 (Propane)',
        'reduces': {'refrigeration_gases': Decimal('0.99')},
        'sdg_goals': [13],
        'notes': (
            'R290 (Propane) GWP 3 vs R22 GWP 1,810. '
            'Saves 1,807 kgCO₂e per kg swapped. '
            'Default 50 kg batch — cost saving US$5,250. Source: CARBOMICA D3.7.'
        ),
    },
    'REFRIG_R32_R744': {
        'display_name': 'Refrigerant Swap — R32 to R744 (CO₂)',
        'reduces': {'refrigeration_gases': Decimal('0.99')},
        'sdg_goals': [13],
        'notes': (
            'R744 (CO₂) GWP 1 vs R32 GWP 675. '
            'Saves 674 kgCO₂e per kg swapped. '
            'Default 10 kg batch — cost –US$600 (CO₂ system premium). Source: CARBOMICA D3.7.'
        ),
    },
    'REFRIG_R403A_R407A': {
        'display_name': 'Refrigerant Swap — R403A to R407A',
        'reduces': {'refrigeration_gases': Decimal('0.56')},
        'sdg_goals': [13],
        'notes': (
            'R407A GWP ≈ 1,774 vs R403A GWP 4,032. '
            'Saves 2,258 kgCO₂e per kg swapped. '
            'Default 20 kg batch — cost saving US$700. Source: CARBOMICA D3.7.'
        ),
    },

    # ── 5. Low-GWP Anaesthetic Gases ─────────────────────────────────────────
    'ANAES_ISO_SEVO': {
        'display_name': 'Anaesthetic Switch — Isoflurane to Sevoflurane',
        'reduces': {'anaesthetic_gases': Decimal('0.75')},
        'sdg_goals': [3, 13],
        'notes': (
            'Sevoflurane GWP 130 vs isoflurane GWP 510. '
            'Saves 380 kgCO₂e per kg agent switched. '
            'Cost saving –US$400/year (sevoflurane costs more per litre). '
            'Source: CARBOMICA D3.7.'
        ),
    },

    # ── 6. Avoid Nitrous Oxide ────────────────────────────────────────────────
    'ANAES_NO_AVOID': {
        'display_name': 'Avoid Nitrous Oxide (N₂O)',
        'reduces': {'anaesthetic_gases': Decimal('1.00')},
        'sdg_goals': [3, 13],
        'notes': (
            'N₂O GWP 265; eliminating use saves 298 kgCO₂e per kg avoided. '
            'Per 20-unit batch — cost saving US$200. '
            'Source: CARBOMICA D3.7.'
        ),
    },

    # ── 7. Low-GWP Inhalers ───────────────────────────────────────────────────
    'INHALER_DPI': {
        'display_name': 'Inhaler Switch — Salbutamol MDI to DPI',
        'reduces': {'medical_inhalers': Decimal('1.00')},
        'sdg_goals': [3, 13],
        'notes': (
            'Salbutamol MDI emits ~19 kgCO₂e per 200-dose device; DPI ≈ 0. '
            'Saves 19 kgCO₂e per device. '
            'Per 100 devices: cost –US$500 (DPIs cost more). Source: CARBOMICA D3.7.'
        ),
    },
    'INHALER_SMI': {
        'display_name': 'Inhaler Switch — Salbutamol MDI to Soft Mist Inhaler (SMI)',
        'reduces': {'medical_inhalers': Decimal('1.00')},
        'sdg_goals': [3, 13],
        'notes': (
            'Salbutamol MDI emits ~19 kgCO₂e per device; SMI ≈ 0. '
            'Saves 19 kgCO₂e per device. '
            'Per 20 devices: cost –US$300 (SMIs cost more). Source: CARBOMICA D3.7.'
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
            'Source: CARBOMICA D3.7.'
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
            'Source: CARBOMICA D3.7.'
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
            'Source: CARBOMICA D3.7.'
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
            'Source: CARBOMICA D3.7.'
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
            'Source: CARBOMICA D3.7.'
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
            'Source: CARBOMICA D3.7.'
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
            'Source: CARBOMICA D3.7.'
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
            'Source: CARBOMICA D3.7.'
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
            'Source: CARBOMICA D3.7.'
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
            'Source: CARBOMICA D3.7.'
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
            'Source: CARBOMICA D3.7.'
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
            'Source: CARBOMICA D3.7.'
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
            'Source: CARBOMICA D3.7.'
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
            'Source: CARBOMICA D3.7.'
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
            'Source: CARBOMICA D3.7.'
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
            'Source: CARBOMICA D3.7.'
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
            'Source: CARBOMICA D3.7.'
        ),
    },

    # ── 11. Energy-Efficient Incinerators ─────────────────────────────────────
    'INCINERATOR_TAM': {
        'display_name': 'Biomedical TAM-ENERGY Incinerator',
        'reduces': {'waste_management': Decimal('0.67')},
        'sdg_goals': [3, 12, 13],
        'notes': (
            'High-efficiency medical waste incinerator; runs 8,000 hrs/year. '
            'Fuel use 600 L/year vs conventional 1,800 L/year. '
            'Saves 1,200 L fuel/year = 3,072 kgCO₂e/year (double-accounting per D3.7 = 1,536). '
            'CapEx US$37,000, maint US$5,550/year, annual cost saving US$668. '
            'Source: CARBOMICA D3.7.'
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
            'annual cost saving US$9,276. Source: CARBOMICA D3.7.'
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
            'Source: CARBOMICA D3.7.'
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
            'Source: CARBOMICA D3.7.'
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
            'Source: CARBOMICA D3.7.'
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
            'Source: CARBOMICA D3.7.'
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
            'Source: CARBOMICA D3.7.'
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
            'Source: CARBOMICA D3.7.'
        ),
    },

    # ── 18. Energy-Efficient Laundry ──────────────────────────────────────────
    'EE_LAUNDRY': {
        'display_name': 'Energy-Efficient Laundry Machines (ENERGY STAR)',
        'reduces': {'grid_electricity': Decimal('0.25')},
        'sdg_goals': [7, 13],
        'notes': (
            'ENERGY STAR certified washers use 25 % less energy and 33 % less water '
            'than standard models. Source: Natural Resources Canada / CARBOMICA D3.7.'
        ),
    },
}


# ---------------------------------------------------------------------------
# CarbomicaOptimizer — three-scenario resource allocation
# ---------------------------------------------------------------------------

class CarbomicaOptimizer:
    """
    Implements the CARBOMICA three-scenario analysis described in HIGH Horizons D3.7:

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
        """tCO2e reduced per USD — the core CARBOMICA ranking metric.

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

    def _build_result(self, fi, priority):
        cost = self._total_cost(fi)
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
            'sdg_goals': fi.intervention.sdg_goals or '',
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
        """Scenario 1: apply all interventions, ignoring budget constraint."""
        return [self._build_result(fi, i + 1) for i, fi in enumerate(self.interventions)]

    def fixed_budget(self):
        """Scenario 2: lowest-cost interventions first until budget exhausted."""
        ordered = sorted(self.interventions, key=self._total_cost)
        results, remaining = [], self.budget
        for fi in ordered:
            cost = self._total_cost(fi)
            if cost <= remaining:
                results.append(self._build_result(fi, len(results) + 1))
                remaining -= cost
        return results

    def optimised(self):
        """Scenario 3: greedy knapsack — maximise tCO2e reduction per USD spent."""
        ordered = sorted(self.interventions, key=self._cost_effectiveness, reverse=True)
        results, remaining = [], self.budget
        for fi in ordered:
            cost = self._total_cost(fi)
            if cost <= remaining:
                results.append(self._build_result(fi, len(results) + 1))
                remaining -= cost
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
