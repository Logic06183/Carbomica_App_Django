import csv
import io
import json
from collections import defaultdict

from django.shortcuts import render, redirect, get_object_or_404
from django.db.models import Sum, F, Avg, Count
from django.db.models.functions import TruncMonth
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from decimal import Decimal, InvalidOperation
from datetime import date

from django.db.models import Q

from .forms import (
    FacilityForm,
    InterventionForm,
    EmissionDataForm,
    PolicyForm,
    FacilityInterventionFormSet,
    OptimizationScenarioForm,
    EmissionDataUpdateForm,
)
from .models import (
    Facility,
    EmissionSource,
    Intervention,
    EmissionData,
    Organisation,
    Policy,
    FacilityIntervention,
    OptimizationScenario,
    OptimizationResult,
)
from .modeling import CarbomicaOptimizer, calculate_npv, compute_tco2e, sum_tco2e

# ---------------------------------------------------------------------------
# Shared constants
# ---------------------------------------------------------------------------

EMISSION_FIELDS = [
    'grid_electricity', 'grid_gas', 'bottled_gas', 'liquid_fuel',
    'vehicle_fuel_owned', 'business_travel', 'anaesthetic_gases',
    'refrigeration_gases', 'waste_management', 'medical_inhalers',
    'contractor_logistics',
]

CATEGORY_LABELS = {
    'grid_electricity':    'Grid Electricity',
    'grid_gas':            'Grid Gas',
    'bottled_gas':         'Bottled Gas / LPG',
    'liquid_fuel':         'Liquid Fuel',
    'vehicle_fuel_owned':  'Vehicle Fuel (Owned)',
    'business_travel':     'Business Travel',
    'anaesthetic_gases':   'Anaesthetic Gases',
    'refrigeration_gases': 'Refrigeration Gases',
    'waste_management':    'Waste Management',
    'medical_inhalers':    'Medical Inhalers',
    'contractor_logistics': 'Contractor Logistics',
}

# Default intervention cost guidance (USD) — shown in the upload form to help users
INTERVENTION_COST_DEFAULTS = {
    'Solar PV System':                    {'impl': 45000, 'maint': 1500, 'savings': 8000},
    'Low-GWP Anaesthetic Gases':          {'impl': 3500,  'maint': 500,  'savings': 6000},
    'LED Lighting Upgrade':               {'impl': 8000,  'maint': 200,  'savings': 2500},
    'Medical Waste Segregation & Management': {'impl': 2000, 'maint': 300, 'savings': 1200},
    'Water-Efficient Fixtures':           {'impl': 3000,  'maint': 100,  'savings': 600},
    'Low-GWP Refrigerant Conversion':     {'impl': 5000,  'maint': 400,  'savings': 1800},
    'Switch to Dry-Powder Inhalers (DPI)': {'impl': 1000, 'maint': 0,   'savings': 3500},
    'Fleet & Travel Optimisation':        {'impl': 2500,  'maint': 300,  'savings': 1400},
}


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _user_facilities(user):
    """
    Return all Facility objects this user can access:
      - facilities they created directly, OR
      - facilities belonging to an organisation they are a member of.
    """
    return Facility.objects.filter(
        Q(created_by=user) | Q(organisation__members=user)
    ).distinct()


def _aggregate_tco2e_all(user):
    """
    Load EmissionData records for *this user's* facilities and return:
      - category_tco2e: {field: Decimal} total tCO₂e per emission category
      - facility_tco2e: {facility_id: Decimal}
      - monthly_tco2e:  [(date_obj, Decimal)] sorted ascending
      - total_tco2e:    Decimal
    """
    user_facility_ids = _user_facilities(user).values_list('id', flat=True)
    all_records = (
        EmissionData.objects
        .select_related('emission_source__facility')
        .filter(emission_source__facility_id__in=user_facility_ids)
    )
    category_tco2e = {f: Decimal('0') for f in EMISSION_FIELDS}
    facility_tco2e = defaultdict(Decimal)
    monthly_tco2e_map = defaultdict(Decimal)   # date → tCO₂e
    total_tco2e = Decimal('0')

    for ed in all_records:
        country = ed.emission_source.facility.country
        tco2e = compute_tco2e(ed, country)
        for field in EMISSION_FIELDS:
            category_tco2e[field] += tco2e.get(field, Decimal('0'))
        facility_tco2e[ed.emission_source.facility_id] += tco2e['total']
        total_tco2e += tco2e['total']
        if ed.date:
            # Group by year-month for the trend chart
            month_key = date(ed.date.year, ed.date.month, 1)
            monthly_tco2e_map[month_key] += tco2e['total']

    monthly_tco2e = sorted(monthly_tco2e_map.items())  # [(date, Decimal), ...]
    return category_tco2e, dict(facility_tco2e), monthly_tco2e, total_tco2e


# ---------------------------------------------------------------------------
# Home / landing
# ---------------------------------------------------------------------------

def home(request):
    """Landing page — guides health managers into the CARBOMICA tool."""
    facility_count = Facility.objects.count()
    all_eds = EmissionData.objects.select_related('emission_source__facility').all()
    total_emissions = sum(
        compute_tco2e(ed, country=ed.emission_source.facility.country if ed.emission_source and ed.emission_source.facility else 'OTHER')['total']
        for ed in all_eds
    ) or Decimal('0')
    active_interventions = FacilityIntervention.objects.filter(
        intervention__status__in=['Planned', 'In Progress']
    ).count()
    optimized_scenarios = OptimizationScenario.objects.filter(status='Optimized').count()

    recent_facilities = Facility.objects.order_by('-id')[:3]
    recent_scenarios = (
        OptimizationScenario.objects
        .select_related('facility')
        .order_by('-created_at')[:3]
    )
    upcoming_interventions = (
        FacilityIntervention.objects
        .select_related('facility', 'intervention')
        .filter(implementation_date__isnull=False)
        .order_by('implementation_date')[:3]
    )

    call_to_actions = [
        {
            'title': 'Add a facility',
            'description': 'Capture your site data and baseline emissions.',
            'icon': 'hospital',
            'url_name': 'add_facility',
        },
        {
            'title': 'Review emissions',
            'description': 'Track hotspots and progress from the dashboard.',
            'icon': 'chart-line',
            'url_name': 'dashboard',
        },
        {
            'title': 'Plan interventions',
            'description': 'Model ROI, SDG impact and policy alignment.',
            'icon': 'tools',
            'url_name': 'interventions',
        },
    ]

    context = {
        'facility_count': facility_count,
        'total_emissions': total_emissions,
        'active_interventions': active_interventions,
        'optimized_scenarios': optimized_scenarios,
        'recent_facilities': recent_facilities,
        'recent_scenarios': recent_scenarios,
        'upcoming_interventions': upcoming_interventions,
        'call_to_actions': call_to_actions,
    }
    return render(request, 'appname/home.html', context)


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------

@login_required
def dashboard(request):
    """Overview of facilities, emissions, and optimisation scenarios."""
    facilities_qs = _user_facilities(request.user)

    # Compute tCO₂e only for this user's facilities
    category_tco2e, facility_tco2e, monthly_tco2e, total_tco2e = _aggregate_tco2e_all(request.user)

    user_facility_ids = facilities_qs.values_list('id', flat=True)

    active_interventions = FacilityIntervention.objects.filter(
        facility_id__in=user_facility_ids,
        intervention__status='In Progress',
    ).count()

    total_investment = (
        FacilityIntervention.objects
        .filter(facility_id__in=user_facility_ids)
        .aggregate(total=Sum('implementation_cost'))['total']
        or Decimal('0')
    )

    optimization_scenarios = (
        OptimizationScenario.objects
        .select_related('facility')
        .filter(facility_id__in=user_facility_ids)
        .order_by('-created_at')
    )

    # Per-category tCO₂e breakdown (replaces old source-name grouping)
    source_breakdown = sorted(
        [
            {
                'name': CATEGORY_LABELS.get(field, field),
                'amount': amount,
                'percentage': (amount / total_tco2e * 100) if total_tco2e > 0 else Decimal('0'),
            }
            for field, amount in category_tco2e.items()
            if amount > 0
        ],
        key=lambda x: x['amount'],
        reverse=True,
    )

    intervention_counts = {
        row['facility_id']: row['count']
        for row in FacilityIntervention.objects
        .filter(facility_id__in=user_facility_ids, intervention__status='In Progress')
        .values('facility_id')
        .annotate(count=Count('id'))
    }
    facility_emissions = sorted(
        [
            {
                'id': f.id,
                'name': f.display_name,
                'emissions': facility_tco2e.get(f.id, Decimal('0')),
                'interventions_count': intervention_counts.get(f.id, 0),
            }
            for f in facilities_qs
        ],
        key=lambda x: x['emissions'],
        reverse=True,
    )

    # Plotly chart payloads (tCO₂e values throughout)
    source_chart_data = json.dumps({
        'labels': [s['name'] for s in source_breakdown],
        'values': [float(s['amount'] or 0) for s in source_breakdown],
    })
    top_facilities = facility_emissions[:5]
    facility_chart_data = json.dumps({
        'labels': [f['name'] for f in top_facilities],
        'values': [float(f['emissions']) for f in top_facilities],
    })
    monthly_chart_data = json.dumps({
        'labels': [d.strftime('%b %Y') for d, _ in monthly_tco2e],
        'values': [float(v) for _, v in monthly_tco2e],
    })

    context = {
        'facilities': facility_emissions,
        'total_emissions': total_tco2e,
        'active_interventions': active_interventions,
        'total_investment': total_investment,
        'source_breakdown': source_breakdown,
        'optimization_scenarios': optimization_scenarios,
        'source_chart_data': source_chart_data,
        'facility_chart_data': facility_chart_data,
        'monthly_chart_data': monthly_chart_data,
        # Global stat for community momentum — shown as "X facilities registered globally"
        'global_facility_count': Facility.objects.count(),
    }
    return render(request, 'appname/dashboard.html', context)


# ---------------------------------------------------------------------------
# Facilities
# ---------------------------------------------------------------------------

@login_required
def facilities(request):
    all_facilities = list(
        _user_facilities(request.user)
        .prefetch_related('emission_sources__emission_data', 'facility_interventions')
    )
    # Attach computed tCO₂e and latest date directly to each facility object
    for facility in all_facilities:
        source = facility.emission_sources.first()
        latest = None
        if source:
            latest = source.emission_data.order_by('-date').first()
        facility.latest_tco2e = (
            compute_tco2e(latest, facility.country)['total'] if latest else None
        )
        facility.latest_date = latest.date if latest else None
        facility.has_emission_data = latest is not None
    return render(request, 'appname/facilities.html', {'facilities': all_facilities})


@login_required
def add_facility(request):
    if request.method == 'POST':
        facility_form = FacilityForm(request.POST)
        emission_data_form = EmissionDataForm(request.POST)

        if facility_form.is_valid() and emission_data_form.is_valid():
            facility = facility_form.save(commit=False)
            if request.user.is_authenticated:
                facility.created_by = request.user
            facility.save()
            # Auto-create the emission source — users don't need to configure this
            emission_source = EmissionSource.objects.create(
                facility=facility,
                code_name=f'{facility.code_name}_BASELINE',
                display_name=f'{facility.display_name} — Baseline',
            )
            emission_data = emission_data_form.save(commit=False)
            emission_data.emission_source = emission_source
            emission_data.save()
            messages.success(request, f'{facility.display_name} added successfully!')
            return redirect('facilities')
    else:
        facility_form = FacilityForm()
        emission_data_form = EmissionDataForm()

    return render(request, 'appname/add_facility.html', {
        'facility_form': facility_form,
        'emission_data_form': emission_data_form,
    })


# ---------------------------------------------------------------------------
# Interventions portfolio
# ---------------------------------------------------------------------------

@login_required
def interventions(request):
    """Portfolio view — all facility interventions with financial and SDG metrics."""
    user_facility_ids = _user_facilities(request.user).values_list('id', flat=True)
    qs = (
        FacilityIntervention.objects
        .select_related('facility', 'intervention')
        .filter(facility_id__in=user_facility_ids)
        .order_by('facility__display_name', 'intervention__display_name')
    )

    aggregates = qs.aggregate(
        total_annual_savings=Sum('annual_savings'),
        total_investment=Sum(F('implementation_cost') + F('maintenance_cost')),
        average_roi=Avg('roi'),
    )

    total_count = qs.count()

    status_qs = (
        qs.values('intervention__status')
        .annotate(count=Count('id'))
    )

    cards = []
    for record in qs:
        impl_cost = record.implementation_cost or Decimal('0')
        maint_cost = record.maintenance_cost or Decimal('0')
        total_cost = impl_cost + maint_cost
        annual_savings = record.annual_savings or Decimal('0')
        payback_years = (total_cost / annual_savings) if annual_savings > 0 else None
        roi_value = record.calculate_roi()
        npv_value = calculate_npv(annual_savings, impl_cost) if annual_savings else None

        cards.append({
            'id': record.id,
            'name': record.intervention.display_name,
            'facility': record.facility.display_name,
            'facility_id': record.facility.id,
            'status': record.intervention.status,
            'implementation_date': record.implementation_date,
            'sdg_goals': record.intervention.sdg_goals,
            'financial': {
                'implementation_cost': impl_cost,
                'maintenance_cost': maint_cost,
                'annual_savings': annual_savings,
                'total_cost': total_cost,
                'roi': roi_value,
                'payback_years': payback_years,
                'npv': npv_value,
            },
            'environmental': {
                'expected_reduction_pct': record.intervention.emission_reduction_percentage,
                'achieved_reduction': record.emission_reduction_achieved,
                'energy_savings': record.intervention.energy_savings,
            },
            'operational': {
                'payback_target_months': record.intervention.payback_period,
                'policy_notes': record.intervention.description,
            },
        })

    total_savings = aggregates['total_annual_savings'] or Decimal('0')
    total_invest = aggregates['total_investment'] or Decimal('0')
    summary = {
        'count': total_count,
        'total_annual_savings': total_savings,
        'total_investment': total_invest,
        'average_roi': aggregates['average_roi'] or Decimal('0'),
        'portfolio_payback': (total_invest / total_savings) if total_savings > 0 else None,
    }

    status_breakdown = [
        {
            'status': entry['intervention__status'],
            'count': entry['count'],
            'percentage': (entry['count'] / total_count * 100) if total_count else 0,
        }
        for entry in status_qs
    ]

    return render(request, 'appname/interventions.html', {
        'intervention_cards': cards,
        'summary': summary,
        'status_breakdown': status_breakdown,
    })


# ---------------------------------------------------------------------------
# Optimisation — CARBOMICA three-scenario engine
# ---------------------------------------------------------------------------

@login_required
def optimize_interventions(request, facility_id):
    """
    Run CARBOMICA's three-scenario optimisation for a facility:
      1. Full coverage  — all available interventions
      2. Fixed budget   — cheapest first within budget
      3. Optimised      — maximum tCO2e reduction per USD (greedy knapsack)
    """
    facility = get_object_or_404(_user_facilities(request.user), id=facility_id)

    if request.method == 'POST':
        scenario_form = OptimizationScenarioForm(request.POST)
        emission_form = EmissionDataUpdateForm(request.POST)

        if scenario_form.is_valid() and emission_form.is_valid():
            scenario = scenario_form.save(commit=False)
            scenario.facility = facility
            scenario.save()

            # Record updated emission data snapshot
            emission_source = facility.emission_sources.first()
            if emission_source:
                EmissionData.objects.create(
                    emission_source=emission_source,
                    **emission_form.cleaned_data,
                )

            # Baseline in tCO₂e — convert raw usage using country-specific factors
            emission_records = EmissionData.objects.filter(emission_source__facility=facility)
            baseline = sum_tco2e(emission_records, facility.country)

            # Per-category baseline for accurate intervention reduction calculation
            latest_ed = emission_records.order_by('-date').first()
            category_baselines = {}
            if latest_ed:
                cat = compute_tco2e(latest_ed, facility.country)
                cat.pop('total', None)
                category_baselines = cat

            # Fetch facility-specific intervention records (with actual costs)
            facility_interventions = (
                FacilityIntervention.objects
                .select_related('facility', 'intervention')
                .filter(facility=facility)
            )

            optimizer = CarbomicaOptimizer(
                facility_interventions=facility_interventions,
                budget=scenario.budget,
                total_baseline_emissions=baseline,
                category_baselines=category_baselines,
            )
            scenarios = optimizer.run_all_scenarios()

            # Persist the optimised results for the results view
            OptimizationResult.objects.filter(scenario=scenario).delete()
            for rank, item in enumerate(scenarios['optimised']['results'], start=1):
                intervention_obj = Intervention.objects.filter(
                    display_name=item['intervention_name']
                ).first()
                if intervention_obj:
                    OptimizationResult.objects.create(
                        scenario=scenario,
                        intervention=intervention_obj,
                        priority=rank,
                        expected_roi=item['roi'] or Decimal('0'),
                        emission_reduction=item['emission_reduction'],
                        implementation_cost=item['cost'],
                        annual_savings=item['annual_savings'],
                        payback_months=int(item['payback_years'] * 12)
                        if item['payback_years']
                        else 0,
                    )

            scenario.status = 'Optimized'
            scenario.save()

            # Store all three scenarios in session for the results view
            request.session[f'scenarios_{scenario.id}'] = _serialise_scenarios(scenarios)
            return redirect('optimization_results', scenario_id=scenario.id)

    else:
        scenario_form = OptimizationScenarioForm()
        latest_emission = (
            EmissionData.objects
            .filter(emission_source__facility=facility)
            .order_by('-date')
            .first()
        )
        emission_form = (
            EmissionDataUpdateForm(instance=latest_emission)
            if latest_emission
            else EmissionDataUpdateForm()
        )

    return render(request, 'appname/optimize_interventions.html', {
        'facility': facility,
        'scenario_form': scenario_form,
        'emission_form': emission_form,
    })


def _serialise_scenarios(scenarios):
    """Convert Decimal values to float so the dict is JSON-serialisable for the session."""
    def _fix(obj):
        if isinstance(obj, Decimal):
            return float(obj)
        if isinstance(obj, dict):
            return {k: _fix(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [_fix(i) for i in obj]
        return obj
    return _fix(scenarios)


@login_required
def optimization_results(request, scenario_id):
    user_facility_ids = _user_facilities(request.user).values_list('id', flat=True)
    scenario = get_object_or_404(OptimizationScenario, id=scenario_id, facility_id__in=user_facility_ids)

    # Try to load the live three-scenario data from session
    session_key = f'scenarios_{scenario.id}'
    scenarios = request.session.get(session_key)

    # Fall back to the persisted OptimizationResult rows if session expired
    if not scenarios:
        results = list(
            scenario.results.select_related('intervention').order_by('priority')
        )
        opt_results = [
            {
                'priority': r.priority,
                'intervention_name': r.intervention.display_name,
                'facility_name': scenario.facility.display_name,
                'cost': float(r.implementation_cost),
                'emission_reduction': float(r.emission_reduction),
                'annual_savings': float(r.annual_savings),
                'roi': float(r.expected_roi),
                'payback_years': r.payback_months / 12 if r.payback_months else None,
                'sdg_goals': r.intervention.sdg_goals,
            }
            for r in results
        ]
        total_cost = sum(r['cost'] for r in opt_results)
        total_reduction = sum(r['emission_reduction'] for r in opt_results)
        scenarios = {
            'optimised': {
                'results': opt_results,
                'summary': {
                    'count': len(opt_results),
                    'total_cost': total_cost,
                    'total_reduction': total_reduction,
                    'pct_of_baseline': 0,
                    'total_annual_savings': sum(r['annual_savings'] for r in opt_results),
                    'budget_remaining': float(scenario.budget) - total_cost,
                },
            },
            'full_coverage': {'results': [], 'summary': {}},
            'fixed_budget': {'results': [], 'summary': {}},
        }

    return render(request, 'appname/optimization_results.html', {
        'scenario': scenario,
        'scenarios': scenarios,
    })


# ---------------------------------------------------------------------------
# Data upload — CSV import (aligned with AKDN Carbon Management Tool format)
# and manual entry for emissions and facility interventions
# ---------------------------------------------------------------------------

# Column headers accepted in the CSV upload (case-insensitive, strips whitespace)
EMISSION_CSV_COLUMNS = {
    'grid_electricity':    ['grid electricity', 'grid_electricity', 'electricity (grid)', 'scope 2 electricity'],
    'grid_gas':            ['grid gas', 'grid_gas', 'natural gas', 'piped gas'],
    'bottled_gas':         ['bottled gas', 'bottled_gas', 'lpg', 'liquid petroleum gas'],
    'liquid_fuel':         ['liquid fuel', 'liquid_fuel', 'diesel', 'petrol', 'fuel oil'],
    'vehicle_fuel_owned':  ['vehicle fuel', 'vehicle_fuel_owned', 'owned vehicles', 'fleet fuel'],
    'business_travel':     ['business travel', 'business_travel', 'staff travel', 'travel'],
    'anaesthetic_gases':   ['anaesthetic gases', 'anaesthetic_gases', 'anaesthetics', 'anesthetic gases'],
    'refrigeration_gases': ['refrigeration gases', 'refrigeration_gases', 'refrigerants', 'hfcs'],
    'waste_management':    ['waste management', 'waste_management', 'waste', 'medical waste'],
    'medical_inhalers':    ['medical inhalers', 'medical_inhalers', 'inhalers', 'mdis'],
    'contractor_logistics': ['contractor logistics', 'contractor_logistics', 'contracted transport',
                             'supply chain transport', 'logistics'],
}


def _match_column(header):
    """Map a CSV column header to an EmissionData field name."""
    normalised = header.strip().lower()
    for field, aliases in EMISSION_CSV_COLUMNS.items():
        if normalised in aliases or normalised == field:
            return field
    return None


@login_required
def upload_emissions(request):
    """
    Upload emission data for a facility via CSV or manual form entry.

    CSV format (any order, headers matched flexibly against AKDN tool names):
        date, grid_electricity, grid_gas, bottled_gas, liquid_fuel,
        vehicle_fuel_owned, business_travel, anaesthetic_gases,
        refrigeration_gases, waste_management, medical_inhalers
    """
    facilities = _user_facilities(request.user).order_by('display_name')

    if request.method == 'POST':
        facility_id = request.POST.get('facility')
        facility = get_object_or_404(_user_facilities(request.user), id=facility_id)
        emission_source, _ = EmissionSource.objects.get_or_create(
            facility=facility,
            code_name=f'{facility.code_name}_UPLOAD',
            defaults={'display_name': f'{facility.display_name} — Uploaded Data'},
        )

        # ── CSV upload path ──────────────────────────────────────────────
        csv_file = request.FILES.get('csv_file')
        if csv_file:
            try:
                decoded = csv_file.read().decode('utf-8-sig')  # handles Excel BOM
                reader = csv.DictReader(io.StringIO(decoded))
                rows_saved = 0
                errors = []

                for row_num, row in enumerate(reader, start=2):
                    record_date = row.get('date', '').strip() or str(date.today())
                    try:
                        parsed_date = date.fromisoformat(record_date)
                    except ValueError:
                        errors.append(f'Row {row_num}: invalid date "{record_date}" — use YYYY-MM-DD.')
                        continue

                    kwargs = {'emission_source': emission_source, 'date': parsed_date}
                    for header, value in row.items():
                        field = _match_column(header or '')
                        if field:
                            try:
                                kwargs[field] = Decimal(value.strip() or '0')
                            except InvalidOperation:
                                kwargs[field] = Decimal('0')

                    EmissionData.objects.update_or_create(
                        emission_source=emission_source,
                        date=parsed_date,
                        defaults={k: v for k, v in kwargs.items()
                                  if k not in ('emission_source', 'date')},
                    )
                    rows_saved += 1

                if errors:
                    for e in errors:
                        messages.warning(request, e)
                if rows_saved:
                    messages.success(
                        request,
                        f'Imported {rows_saved} emission record(s) for {facility.display_name}.'
                    )
                else:
                    messages.error(request, 'No rows imported — check the file format.')

            except Exception as exc:
                messages.error(request, f'Could not parse CSV: {exc}')

        # ── Manual entry path ────────────────────────────────────────────
        else:
            form = EmissionDataForm(request.POST)
            if form.is_valid():
                entry = form.save(commit=False)
                entry.emission_source = emission_source
                entry.save()
                messages.success(
                    request,
                    f'Emission record saved for {facility.display_name}.'
                )
            else:
                return render(request, 'appname/upload_emissions.html', {
                    'facilities': facilities,
                    'form': form,
                    'selected_facility_id': int(facility_id),
                })

        return redirect('dashboard')

    return render(request, 'appname/upload_emissions.html', {
        'facilities': facilities,
        'form': EmissionDataForm(),
        'csv_columns': list(EMISSION_CSV_COLUMNS.keys()),
    })


@login_required
def upload_interventions(request):
    """
    Attach interventions to a facility with site-specific costs via form or CSV.

    CSV format:
        intervention_name, implementation_cost, maintenance_cost, annual_savings,
        implementation_date (YYYY-MM-DD, optional)
    """
    facilities = _user_facilities(request.user).order_by('display_name')
    interventions_qs = Intervention.objects.order_by('display_name')

    if request.method == 'POST':
        facility_id = request.POST.get('facility')
        facility = get_object_or_404(_user_facilities(request.user), id=facility_id)

        csv_file = request.FILES.get('csv_file')
        if csv_file:
            try:
                decoded = csv_file.read().decode('utf-8-sig')
                reader = csv.DictReader(io.StringIO(decoded))
                rows_saved, errors = 0, []

                for row_num, row in enumerate(reader, start=2):
                    name = (row.get('intervention_name') or row.get('intervention', '')).strip()
                    intervention = Intervention.objects.filter(
                        display_name__iexact=name
                    ).first()
                    if not intervention:
                        errors.append(
                            f'Row {row_num}: intervention "{name}" not found — '
                            'create it in the admin or check spelling.'
                        )
                        continue

                    def _dec(key):
                        try:
                            return Decimal(str(row.get(key, '0')).strip() or '0')
                        except InvalidOperation:
                            return Decimal('0')

                    impl_date_str = (row.get('implementation_date') or '').strip()
                    impl_date = None
                    if impl_date_str:
                        try:
                            impl_date = date.fromisoformat(impl_date_str)
                        except ValueError:
                            errors.append(f'Row {row_num}: invalid date "{impl_date_str}".')

                    fi, _ = FacilityIntervention.objects.update_or_create(
                        facility=facility,
                        intervention=intervention,
                        defaults={
                            'implementation_cost': _dec('implementation_cost'),
                            'maintenance_cost': _dec('maintenance_cost'),
                            'annual_savings': _dec('annual_savings'),
                            'implementation_date': impl_date,
                        },
                    )
                    fi.roi = fi.calculate_roi()
                    fi.save(update_fields=['roi'])
                    rows_saved += 1

                for e in errors:
                    messages.warning(request, e)
                if rows_saved:
                    messages.success(
                        request,
                        f'Linked {rows_saved} intervention(s) to {facility.display_name}.'
                    )
                else:
                    messages.error(request, 'No rows imported — check the file format.')

            except Exception as exc:
                messages.error(request, f'Could not parse CSV: {exc}')

        else:
            # Manual single-intervention entry
            intervention_id = request.POST.get('intervention')
            intervention = get_object_or_404(Intervention, id=intervention_id)

            def _post_dec(key):
                try:
                    return Decimal(request.POST.get(key, '0') or '0')
                except InvalidOperation:
                    return Decimal('0')

            impl_date_str = request.POST.get('implementation_date', '').strip()
            impl_date = None
            if impl_date_str:
                try:
                    impl_date = date.fromisoformat(impl_date_str)
                except ValueError:
                    messages.error(request, f'Invalid date: {impl_date_str}')

            fi, _ = FacilityIntervention.objects.update_or_create(
                facility=facility,
                intervention=intervention,
                defaults={
                    'implementation_cost': _post_dec('implementation_cost'),
                    'maintenance_cost': _post_dec('maintenance_cost'),
                    'annual_savings': _post_dec('annual_savings'),
                    'implementation_date': impl_date,
                },
            )
            fi.roi = fi.calculate_roi()
            fi.save(update_fields=['roi'])
            messages.success(
                request,
                f'Added {intervention.display_name} to {facility.display_name}.'
            )

        return redirect('upload_interventions')

    # ── Create a custom intervention ──────────────────────────────────────
    if request.method == 'POST' and request.POST.get('action') == 'create_custom':
        name = request.POST.get('custom_name', '').strip()
        if name:
            from django.utils.text import slugify
            target_cat = request.POST.get('custom_target_category', '').strip()
            try:
                red_pct = Decimal(request.POST.get('custom_reduction_pct', '0') or '0')
            except InvalidOperation:
                red_pct = Decimal('0')
            Intervention.objects.get_or_create(
                code_name=f'CUSTOM_{slugify(name).upper()[:80]}',
                defaults={
                    'display_name': name,
                    'emission_reduction_percentage': red_pct,
                    'target_category': target_cat,
                    'status': 'Planned',
                }
            )
            messages.success(request, f'Custom intervention "{name}" created and added to the list.')
        else:
            messages.error(request, 'Please enter a name for the custom intervention.')
        return redirect('upload_interventions')

    return render(request, 'appname/upload_interventions.html', {
        'facilities': facilities,
        'interventions': interventions_qs,
        'cost_defaults': json.dumps(INTERVENTION_COST_DEFAULTS),
        'emission_fields': list(EMISSION_FIELDS),
    })


# ---------------------------------------------------------------------------
# Organisation — team management
# ---------------------------------------------------------------------------

@login_required
def my_organisation(request):
    """
    Manage the user's organisation (team). Members share access to all facilities
    in the organisation. A user can belong to multiple orgs and own one or more.
    """
    from django.contrib.auth.models import User as AuthUser

    # Orgs the current user owns or is a member of
    owned_orgs = Organisation.objects.filter(created_by=request.user).prefetch_related('members', 'facilities')
    member_orgs = Organisation.objects.filter(members=request.user).exclude(created_by=request.user).prefetch_related('members', 'facilities')

    if request.method == 'POST':
        action = request.POST.get('action')

        # ── Create a new organisation ──────────────────────────────────
        if action == 'create':
            name = request.POST.get('org_name', '').strip()
            if name:
                org = Organisation.objects.create(name=name, created_by=request.user)
                org.members.add(request.user)
                messages.success(request, f'Organisation "{name}" created.')
            else:
                messages.error(request, 'Please enter an organisation name.')

        # ── Add a member by email ──────────────────────────────────────
        elif action == 'add_member':
            org_id = request.POST.get('org_id')
            email = request.POST.get('email', '').strip().lower()
            org = get_object_or_404(Organisation, id=org_id, created_by=request.user)
            try:
                new_member = AuthUser.objects.get(email__iexact=email)
                org.members.add(new_member)
                messages.success(request, f'{email} added to {org.name}.')
            except AuthUser.DoesNotExist:
                messages.error(request, f'No user with email {email}. They must sign in with Google first.')

        # ── Remove a member ────────────────────────────────────────────
        elif action == 'remove_member':
            org_id = request.POST.get('org_id')
            user_id = request.POST.get('user_id')
            org = get_object_or_404(Organisation, id=org_id, created_by=request.user)
            if str(request.user.id) != user_id:  # can't remove yourself as owner
                org.members.remove(user_id)
                messages.success(request, 'Member removed.')

        # ── Assign a facility to an org ────────────────────────────────
        elif action == 'assign_facility':
            org_id = request.POST.get('org_id')
            facility_id = request.POST.get('facility_id')
            org = get_object_or_404(Organisation, id=org_id, created_by=request.user)
            facility = get_object_or_404(Facility, id=facility_id, created_by=request.user)
            facility.organisation = org
            facility.save(update_fields=['organisation'])
            messages.success(request, f'{facility.display_name} assigned to {org.name}.')

        # ── Remove a facility from an org ──────────────────────────────
        elif action == 'unassign_facility':
            org_id = request.POST.get('org_id')
            facility_id = request.POST.get('facility_id')
            org = get_object_or_404(Organisation, id=org_id, created_by=request.user)
            facility = get_object_or_404(Facility, id=facility_id, organisation=org)
            facility.organisation = None
            facility.save(update_fields=['organisation'])
            messages.success(request, f'{facility.display_name} removed from {org.name}.')

        return redirect('my_organisation')

    # Facilities the user owns that aren't yet in any org (available to assign)
    unassigned_facilities = Facility.objects.filter(created_by=request.user, organisation__isnull=True)

    return render(request, 'appname/organisation.html', {
        'owned_orgs': owned_orgs,
        'member_orgs': member_orgs,
        'unassigned_facilities': unassigned_facilities,
    })


# ---------------------------------------------------------------------------
# Facility detail — full profile with tCO₂e breakdown and linked interventions
# ---------------------------------------------------------------------------

@login_required
def facility_detail(request, facility_id):
    """
    Comprehensive facility profile page.
    Shows: tCO₂e breakdown by category, emission history, linked interventions,
    and a per-category Plotly chart — suitable for the May 2026 report demo.
    """
    facility = get_object_or_404(
        _user_facilities(request.user).prefetch_related(
            'emission_sources__emission_data',
            'facility_interventions__intervention',
        ),
        id=facility_id,
    )

    # All emission records for this facility, newest first
    emission_records = list(
        EmissionData.objects
        .filter(emission_source__facility=facility)
        .order_by('-date')
    )

    # tCO₂e per record (for history table) and per category (for latest)
    records_with_tco2e = []
    for ed in emission_records:
        breakdown = compute_tco2e(ed, facility.country)
        records_with_tco2e.append({
            'date': ed.date,
            'total_tco2e': breakdown['total'],
            'breakdown': {CATEGORY_LABELS[f]: breakdown[f] for f in EMISSION_FIELDS},
        })

    # Latest record category breakdown for charts
    latest_breakdown = records_with_tco2e[0] if records_with_tco2e else None

    # Per-category chart data (latest record)
    if latest_breakdown:
        cat_items = sorted(
            [(name, val) for name, val in latest_breakdown['breakdown'].items() if val > 0],
            key=lambda x: x[1], reverse=True,
        )
        category_chart_data = json.dumps({
            'labels': [c[0] for c in cat_items],
            'values': [float(c[1]) for c in cat_items],
        })
        # Bar chart: all categories including zeros for completeness
        all_cat_items = [(CATEGORY_LABELS[f], latest_breakdown['breakdown'][CATEGORY_LABELS[f]])
                         for f in EMISSION_FIELDS]
        bar_chart_data = json.dumps({
            'labels': [c[0] for c in all_cat_items],
            'values': [float(c[1]) for c in all_cat_items],
        })
    else:
        category_chart_data = json.dumps({'labels': [], 'values': []})
        bar_chart_data = json.dumps({'labels': [], 'values': []})

    # Linked interventions with financial metrics
    facility_interventions = []
    for fi in facility.facility_interventions.select_related('intervention').all():
        impl = fi.implementation_cost or Decimal('0')
        maint = fi.maintenance_cost or Decimal('0')
        savings = fi.annual_savings or Decimal('0')
        total_cost = impl + maint
        payback_yrs = (total_cost / savings) if savings > 0 else None
        facility_interventions.append({
            'name': fi.intervention.display_name,
            'status': fi.intervention.status,
            'sdg_goals': fi.intervention.sdg_goals,
            'implementation_cost': impl,
            'maintenance_cost': maint,
            'annual_savings': savings,
            'payback_yrs': payback_yrs,
            'roi': fi.calculate_roi(),
            'emission_reduction_pct': fi.intervention.emission_reduction_percentage,
        })

    # Baseline tCO₂e (most recent record)
    baseline_tco2e = latest_breakdown['total_tco2e'] if latest_breakdown else Decimal('0')

    # Potential tCO₂e savings from all linked interventions
    potential_savings_pct = sum(
        fi['emission_reduction_pct'] or 0 for fi in facility_interventions
    )
    potential_savings_tco2e = baseline_tco2e * min(potential_savings_pct, 100) / 100

    return render(request, 'appname/facility_detail.html', {
        'facility': facility,
        'records_with_tco2e': records_with_tco2e,
        'latest_breakdown': latest_breakdown,
        'facility_interventions': facility_interventions,
        'baseline_tco2e': baseline_tco2e,
        'potential_savings_tco2e': potential_savings_tco2e,
        'category_chart_data': category_chart_data,
        'bar_chart_data': bar_chart_data,
        'emission_fields': EMISSION_FIELDS,
        'category_labels': CATEGORY_LABELS,
    })
