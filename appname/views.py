import csv
import io
import json

from django.shortcuts import render, redirect, get_object_or_404
from django.db.models import Sum, F, Avg, Count
from django.db.models.functions import TruncMonth
from django.contrib import messages
from decimal import Decimal, InvalidOperation
from datetime import date

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
    Policy,
    FacilityIntervention,
    OptimizationScenario,
    OptimizationResult,
)
from .modeling import CarbomicaOptimizer, calculate_npv

# ---------------------------------------------------------------------------
# Shared query helpers
# ---------------------------------------------------------------------------

EMISSION_FIELDS = [
    'grid_electricity', 'grid_gas', 'bottled_gas', 'liquid_fuel',
    'vehicle_fuel_owned', 'business_travel', 'anaesthetic_gases',
    'refrigeration_gases', 'waste_management', 'medical_inhalers',
]


def emission_total_expression():
    expr = F(EMISSION_FIELDS[0])
    for field in EMISSION_FIELDS[1:]:
        expr = expr + F(field)
    return expr


def get_total_emissions():
    """Sum all emissions across all sources and facilities."""
    return EmissionData.objects.aggregate(
        total=Sum(emission_total_expression())
    )['total'] or Decimal('0')


# ---------------------------------------------------------------------------
# Home / landing
# ---------------------------------------------------------------------------

def home(request):
    """Landing page — guides health managers into the CARBOMICA tool."""
    facility_count = Facility.objects.count()
    total_emissions = get_total_emissions()
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

def dashboard(request):
    """Overview of facilities, emissions, and optimisation scenarios."""
    facilities = Facility.objects.all()
    total_emissions = get_total_emissions()

    active_interventions = FacilityIntervention.objects.filter(
        intervention__status='In Progress'
    ).count()

    total_investment = (
        FacilityIntervention.objects.aggregate(total=Sum('implementation_cost'))['total']
        or Decimal('0')
    )

    optimization_scenarios = (
        OptimizationScenario.objects
        .select_related('facility')
        .order_by('-created_at')
    )

    # Emission source breakdown — single aggregated query
    emission_sources = (
        EmissionData.objects
        .values('emission_source__display_name')
        .annotate(total_emissions=Sum(emission_total_expression()))
        .order_by('-total_emissions')
    )
    source_total = (
        emission_sources.aggregate(total=Sum('total_emissions'))['total'] or Decimal('1')
    )
    source_breakdown = [
        {
            'name': row['emission_source__display_name'],
            'amount': row['total_emissions'],
            'percentage': (row['total_emissions'] / source_total) * 100,
        }
        for row in emission_sources
    ]

    # Per-facility totals — single query via annotation avoids N+1
    facility_totals = {
        row['emission_source__facility_id']: row['total']
        for row in EmissionData.objects
        .values('emission_source__facility_id')
        .annotate(total=Sum(emission_total_expression()))
    }
    intervention_counts = {
        row['facility_id']: row['count']
        for row in FacilityIntervention.objects
        .filter(intervention__status='In Progress')
        .values('facility_id')
        .annotate(count=Count('id'))
    }
    facility_emissions = sorted(
        [
            {
                'id': f.id,
                'name': f.display_name,
                'emissions': facility_totals.get(f.id, Decimal('0')),
                'interventions_count': intervention_counts.get(f.id, 0),
            }
            for f in facilities
        ],
        key=lambda x: x['emissions'],
        reverse=True,
    )

    # Plotly chart payloads
    source_chart_data = json.dumps({
        'labels': [s['name'] for s in source_breakdown],
        'values': [float(s['amount'] or 0) for s in source_breakdown],
    })
    top_facilities = facility_emissions[:5]
    facility_chart_data = json.dumps({
        'labels': [f['name'] for f in top_facilities],
        'values': [float(f['emissions']) for f in top_facilities],
    })

    monthly_rows = (
        EmissionData.objects
        .annotate(month=TruncMonth('date'))
        .values('month')
        .order_by('month')
        .annotate(total=Sum(emission_total_expression()))
    )
    monthly_chart_data = json.dumps({
        'labels': [
            row['month'].strftime('%b %Y') if row['month'] else 'Unknown'
            for row in monthly_rows
        ],
        'values': [float(row['total'] or 0) for row in monthly_rows],
    })

    context = {
        'facilities': facility_emissions,
        'total_emissions': total_emissions,
        'active_interventions': active_interventions,
        'total_investment': total_investment,
        'source_breakdown': source_breakdown,
        'optimization_scenarios': optimization_scenarios,
        'source_chart_data': source_chart_data,
        'facility_chart_data': facility_chart_data,
        'monthly_chart_data': monthly_chart_data,
    }
    return render(request, 'appname/dashboard.html', context)


# ---------------------------------------------------------------------------
# Facilities
# ---------------------------------------------------------------------------

def facilities(request):
    all_facilities = Facility.objects.all()
    return render(request, 'appname/facilities.html', {'facilities': all_facilities})


def add_facility(request):
    if request.method == 'POST':
        facility_form = FacilityForm(request.POST)
        emission_data_form = EmissionDataForm(request.POST)

        if facility_form.is_valid() and emission_data_form.is_valid():
            facility = facility_form.save()
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

def interventions(request):
    """Portfolio view — all facility interventions with financial and SDG metrics."""
    qs = (
        FacilityIntervention.objects
        .select_related('facility', 'intervention')
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

def optimize_interventions(request, facility_id):
    """
    Run CARBOMICA's three-scenario optimisation for a facility:
      1. Full coverage  — all available interventions
      2. Fixed budget   — cheapest first within budget
      3. Optimised      — maximum tCO2e reduction per USD (greedy knapsack)
    """
    facility = get_object_or_404(Facility, id=facility_id)

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

            # Current total baseline emissions for this facility
            baseline = (
                EmissionData.objects
                .filter(emission_source__facility=facility)
                .aggregate(total=Sum(emission_total_expression()))['total']
                or Decimal('0')
            )

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


def optimization_results(request, scenario_id):
    scenario = get_object_or_404(OptimizationScenario, id=scenario_id)

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
    'grid_electricity': ['grid electricity', 'grid_electricity', 'electricity (grid)', 'scope 2 electricity'],
    'grid_gas': ['grid gas', 'grid_gas', 'natural gas', 'piped gas'],
    'bottled_gas': ['bottled gas', 'bottled_gas', 'lpg', 'liquid petroleum gas'],
    'liquid_fuel': ['liquid fuel', 'liquid_fuel', 'diesel', 'petrol', 'fuel oil'],
    'vehicle_fuel_owned': ['vehicle fuel', 'vehicle_fuel_owned', 'owned vehicles', 'fleet fuel'],
    'business_travel': ['business travel', 'business_travel', 'staff travel', 'travel'],
    'anaesthetic_gases': ['anaesthetic gases', 'anaesthetic_gases', 'anaesthetics', 'anesthetic gases'],
    'refrigeration_gases': ['refrigeration gases', 'refrigeration_gases', 'refrigerants', 'hfcs'],
    'waste_management': ['waste management', 'waste_management', 'waste', 'medical waste'],
    'medical_inhalers': ['medical inhalers', 'medical_inhalers', 'inhalers', 'mdis'],
}


def _match_column(header):
    """Map a CSV column header to an EmissionData field name."""
    normalised = header.strip().lower()
    for field, aliases in EMISSION_CSV_COLUMNS.items():
        if normalised in aliases or normalised == field:
            return field
    return None


def upload_emissions(request):
    """
    Upload emission data for a facility via CSV or manual form entry.

    CSV format (any order, headers matched flexibly against AKDN tool names):
        date, grid_electricity, grid_gas, bottled_gas, liquid_fuel,
        vehicle_fuel_owned, business_travel, anaesthetic_gases,
        refrigeration_gases, waste_management, medical_inhalers
    """
    facilities = Facility.objects.order_by('display_name')

    if request.method == 'POST':
        facility_id = request.POST.get('facility')
        facility = get_object_or_404(Facility, id=facility_id)
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


def upload_interventions(request):
    """
    Attach interventions to a facility with site-specific costs via form or CSV.

    CSV format:
        intervention_name, implementation_cost, maintenance_cost, annual_savings,
        implementation_date (YYYY-MM-DD, optional)
    """
    facilities = Facility.objects.order_by('display_name')
    interventions_qs = Intervention.objects.order_by('display_name')

    if request.method == 'POST':
        facility_id = request.POST.get('facility')
        facility = get_object_or_404(Facility, id=facility_id)

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

        return redirect('interventions')

    return render(request, 'appname/upload_interventions.html', {
        'facilities': facilities,
        'interventions': interventions_qs,
    })
