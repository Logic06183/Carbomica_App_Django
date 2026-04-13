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
    'SOLAR_PV': {
        'display_name': 'Solar PV System',
        'reduces': {'grid_electricity': Decimal('0.70')},
        'sdg_goals': [7, 13],
        'notes': (
            'Reduces grid dependency; protects cold chains and critical equipment '
            'from load shedding common in ZW and ZA contexts.'
        ),
    },
    'LOW_GWP_ANAESTHETICS': {
        'display_name': 'Low-GWP Anaesthetic Gases',
        'reduces': {'anaesthetic_gases': Decimal('0.85')},
        'sdg_goals': [3, 13],
        'notes': (
            'Replace desflurane and sevoflurane with total intravenous anaesthesia '
            '(TIVA) or low-GWP alternatives — highest-impact single intervention '
            'per unit cost in most LMIC facility profiles.'
        ),
    },
    'LED_LIGHTING': {
        'display_name': 'LED Lighting Upgrade',
        'reduces': {'grid_electricity': Decimal('0.30')},
        'sdg_goals': [7, 11],
        'notes': 'Retrofit fluorescent and incandescent fittings with LED throughout facility.',
    },
    'WASTE_SEGREGATION': {
        'display_name': 'Medical Waste Segregation & Management',
        'reduces': {'waste_management': Decimal('0.60')},
        'sdg_goals': [3, 12],
        'notes': (
            'Separate hazardous from non-hazardous waste streams to reduce '
            'incineration volume and associated dioxin emissions.'
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
        'notes': 'Replace HFC-134a and R-22 refrigerants in cold-chain and HVAC equipment.',
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
        """tCO2e reduced per USD — the core CARBOMICA ranking metric."""
        cost = self._total_cost(fi)
        reduction = self._emission_reduction(fi)
        if cost <= 0:
            return Decimal('0')
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
