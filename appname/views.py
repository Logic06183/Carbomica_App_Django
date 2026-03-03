import json

from django.shortcuts import render, redirect, get_object_or_404
from django.db.models import Sum, F, Avg, Count
from django.db.models.functions import TruncMonth
from django.contrib import messages
from decimal import Decimal
from .forms import (
    FacilityForm,
    EmissionSourceForm,
    InterventionForm,
    EmissionDataForm,
    PolicyForm,
    FacilityInterventionFormSet,
    OptimizationScenarioForm,
    EmissionDataUpdateForm
)
from .models import (
    Facility,
    EmissionSource,
    Intervention,
    EmissionData,
    Policy,
    FacilityIntervention,
    OptimizationScenario,
    OptimizationResult
)


def emission_total_expression():
    return (
        F('grid_electricity') +
        F('grid_gas') +
        F('bottled_gas') +
        F('liquid_fuel') +
        F('vehicle_fuel_owned') +
        F('business_travel') +
        F('anaesthetic_gases') +
        F('refrigeration_gases') +
        F('waste_management') +
        F('medical_inhalers')
    )


def get_total_emissions():
    """Return the summed emissions across all sources."""
    return EmissionData.objects.aggregate(
        total=Sum(emission_total_expression())
    )['total'] or 0


def home(request):
    """Landing page that guides health managers into the tool."""
    facility_count = Facility.objects.count()
    total_emissions = get_total_emissions()
    active_interventions = FacilityIntervention.objects.filter(
        intervention__status__in=['Planned', 'In Progress']
    ).count()
    optimized_scenarios = OptimizationScenario.objects.filter(status='Optimized').count()

    recent_facilities = Facility.objects.order_by('-id')[:3]
    recent_scenarios = OptimizationScenario.objects.select_related('facility').order_by('-created_at')[:3]
    upcoming_interventions = FacilityIntervention.objects.select_related('facility', 'intervention').filter(
        implementation_date__isnull=False
    ).order_by('implementation_date')[:3]

    call_to_actions = [
        {
            'title': 'Add a facility',
            'description': 'Capture your site data and baseline emissions.',
            'icon': 'hospital',
            'url_name': 'add_facility'
        },
        {
            'title': 'Review emissions',
            'description': 'Track hotspots and progress from the dashboard.',
            'icon': 'chart-line',
            'url_name': 'dashboard'
        },
        {
            'title': 'Plan interventions',
            'description': 'Model ROI, SDG impact and policy alignment.',
            'icon': 'tools',
            'url_name': 'interventions'
        }
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

def calculate_npv(intervention, discount_rate=0.05, years=10):
    """Calculate Net Present Value for an intervention"""
    initial_cost = -intervention.implementation_cost
    annual_savings = intervention.annual_savings
    npv = initial_cost

    for year in range(1, years + 1):
        npv += annual_savings / ((1 + discount_rate) ** year)
    
    return round(npv, 2)

def dashboard(request):
    """Dashboard view showing overview of facilities, emissions, and interventions"""
    facilities = Facility.objects.all()
    
    # Calculate total emissions from all emission data
    total_emissions = get_total_emissions()
    
    active_interventions = FacilityIntervention.objects.filter(
        intervention__status='In Progress'
    ).count()
    
    total_investment = FacilityIntervention.objects.aggregate(
        total=Sum('implementation_cost')
    )['total'] or 0
    
    # Get recent optimization scenarios
    optimization_scenarios = OptimizationScenario.objects.select_related('facility').order_by('-created_at')
    
    # Calculate emission source breakdown
    source_breakdown = []
    emission_sources = EmissionData.objects.values('emission_source__display_name').annotate(
        total_emissions=Sum(emission_total_expression())
    ).order_by('-total_emissions')
    
    total = emission_sources.aggregate(
        total=Sum('total_emissions')
    )['total'] or 0
    
    if total > 0:
        for source in emission_sources:
            percentage = (source['total_emissions'] / total) * 100
            source_breakdown.append({
                'name': source['emission_source__display_name'],
                'amount': source['total_emissions'],
                'percentage': percentage
            })
    
    # Get facility emissions for the table
    facility_emissions = []
    for facility in facilities:
        facility_total = EmissionData.objects.filter(
            emission_source__facility=facility
        ).aggregate(
            total=Sum(emission_total_expression())
        )['total'] or 0
        
        facility_emissions.append({
            'id': facility.id,
            'name': facility.display_name,
            'emissions': facility_total,
            'interventions_count': facility.facility_interventions.filter(
                intervention__status='In Progress'
            ).count()
        })
    
    # Sort facilities by emissions
    facility_emissions.sort(key=lambda x: x['emissions'], reverse=True)

    # Build Plotly-ready datasets
    source_chart_data = json.dumps({
        'labels': [source['name'] for source in source_breakdown],
        'values': [float(source['amount']) if source['amount'] is not None else 0 for source in source_breakdown]
    })

    top_facilities = facility_emissions[:5]
    facility_chart_data = json.dumps({
        'labels': [facility['name'] for facility in top_facilities],
        'values': [float(facility['emissions']) for facility in top_facilities]
    })

    monthly_trends = (
        EmissionData.objects.annotate(month=TruncMonth('date'))
        .values('month')
        .order_by('month')
        .annotate(total=Sum(emission_total_expression()))
    )

    monthly_labels = []
    monthly_values = []
    for entry in monthly_trends:
        month = entry['month']
        monthly_labels.append(month.strftime('%b %Y') if month else 'Unknown')
        monthly_values.append(float(entry['total']) if entry['total'] is not None else 0)

    monthly_chart_data = json.dumps({
        'labels': monthly_labels,
        'values': monthly_values
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

def facilities(request):
    facilities = Facility.objects.all()
    context = {
        'facilities': facilities
    }
    return render(request, 'appname/facilities.html', context)

def add_facility(request):
    if request.method == 'POST':
        facility_form = FacilityForm(request.POST)
        emission_source_form = EmissionSourceForm(request.POST)
        emission_data_form = EmissionDataForm(request.POST)
        
        if all([facility_form.is_valid(), emission_source_form.is_valid(), emission_data_form.is_valid()]):
            facility = facility_form.save()
            
            emission_source = emission_source_form.save(commit=False)
            emission_source.facility = facility
            emission_source.save()
            
            emission_data = emission_data_form.save(commit=False)
            emission_data.emission_source = emission_source
            emission_data.save()
            
            messages.success(request, 'Facility added successfully!')
            return redirect('facilities')
    else:
        facility_form = FacilityForm()
        emission_source_form = EmissionSourceForm()
        emission_data_form = EmissionDataForm()
    
    context = {
        'facility_form': facility_form,
        'emission_source_form': emission_source_form,
        'emission_data_form': emission_data_form
    }
    
    return render(request, 'appname/add_facility.html', context)

def interventions(request):
    """View and analyze interventions from the live dataset."""
    facility_interventions = FacilityIntervention.objects.select_related('facility', 'intervention').order_by(
        'facility__display_name', 'intervention__display_name'
    )

    aggregates = facility_interventions.aggregate(
        total_annual_savings=Sum('annual_savings'),
        total_investment=Sum(F('implementation_cost') + F('maintenance_cost')),
        average_roi=Avg('roi')
    )

    status_qs = facility_interventions.values('intervention__status').annotate(
        count=Count('id')
    )

    intervention_cards = []
    for record in facility_interventions:
        implementation_cost = record.implementation_cost or Decimal('0')
        maintenance_cost = record.maintenance_cost or Decimal('0')
        total_cost = implementation_cost + maintenance_cost
        annual_savings = record.annual_savings or Decimal('0')
        payback_years = None
        if annual_savings > 0:
            payback_years = total_cost / annual_savings

        roi_value = record.calculate_roi()
        npv_value = calculate_npv(record) if annual_savings else None

        intervention_cards.append({
            'id': record.id,
            'name': record.intervention.display_name,
            'facility': record.facility.display_name,
            'facility_id': record.facility.id,
            'status': record.intervention.status,
            'implementation_date': record.implementation_date,
            'financial': {
                'implementation_cost': implementation_cost,
                'maintenance_cost': maintenance_cost,
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
                'policy_alignment': record.intervention.description,
            }
        })

    summary = {
        'count': facility_interventions.count(),
        'total_annual_savings': aggregates['total_annual_savings'] or Decimal('0'),
        'total_investment': aggregates['total_investment'] or Decimal('0'),
        'average_roi': aggregates['average_roi'] or Decimal('0'),
    }
    if summary['total_annual_savings'] > 0:
        summary['portfolio_payback'] = summary['total_investment'] / summary['total_annual_savings']
    else:
        summary['portfolio_payback'] = None

    status_breakdown = []
    for entry in status_qs:
        count = entry['count']
        percentage = (count / summary['count'] * 100) if summary['count'] else 0
        status_breakdown.append({
            'status': entry['intervention__status'],
            'count': count,
            'percentage': percentage,
        })

    context = {
        'intervention_cards': intervention_cards,
        'summary': summary,
        'status_breakdown': status_breakdown,
    }

    return render(request, 'appname/interventions.html', context)

def optimize_interventions(request, facility_id):
    facility = get_object_or_404(Facility, id=facility_id)
    
    if request.method == 'POST':
        scenario_form = OptimizationScenarioForm(request.POST)
        emission_form = EmissionDataUpdateForm(request.POST)
        
        if scenario_form.is_valid() and emission_form.is_valid():
            # Create optimization scenario
            scenario = scenario_form.save(commit=False)
            scenario.facility = facility
            scenario.save()
            
            # Update emission data
            emission_data = EmissionData.objects.create(
                emission_source=facility.emission_sources.first(),
                **emission_form.cleaned_data
            )
            
            # Calculate total current emissions
            total_emissions = sum(
                getattr(emission_data, field)
                for field in EmissionDataUpdateForm.Meta.fields
            )
            
            # Get all available interventions
            available_interventions = Intervention.objects.all()
            
            # Initialize optimization results
            results = []
            remaining_budget = scenario.budget
            total_reduction = Decimal('0')
            
            # Simple greedy optimization algorithm
            sorted_interventions = sorted(
                available_interventions,
                key=lambda x: (x.emission_reduction_percentage / x.payback_period),
                reverse=True
            )
            
            for intervention in sorted_interventions:
                implementation_cost = Decimal('50000')  # Example cost, should be based on facility size
                if implementation_cost <= remaining_budget:
                    emission_reduction = (intervention.emission_reduction_percentage / 100) * total_emissions
                    annual_savings = intervention.energy_savings * Decimal('0.15')  # Example electricity rate
                    roi = (annual_savings / implementation_cost) * 100
                    
                    # Create optimization result
                    OptimizationResult.objects.create(
                        scenario=scenario,
                        intervention=intervention,
                        priority=len(results) + 1,
                        expected_roi=roi,
                        emission_reduction=emission_reduction,
                        implementation_cost=implementation_cost,
                        annual_savings=annual_savings,
                        payback_months=intervention.payback_period
                    )
                    
                    remaining_budget -= implementation_cost
                    total_reduction += emission_reduction
                    
                    if total_reduction >= (scenario.target_reduction / 100) * total_emissions:
                        break
            
            scenario.status = 'Optimized'
            scenario.save()
            
            return redirect('optimization_results', scenario_id=scenario.id)
    else:
        scenario_form = OptimizationScenarioForm()
        emission_form = EmissionDataUpdateForm()
        
        # Get latest emission data if available
        latest_emission = EmissionData.objects.filter(
            emission_source__facility=facility
        ).order_by('-date').first()
        
        if latest_emission:
            emission_form = EmissionDataUpdateForm(instance=latest_emission)
    
    context = {
        'facility': facility,
        'scenario_form': scenario_form,
        'emission_form': emission_form
    }
    
    return render(request, 'appname/optimize_interventions.html', context)

def optimization_results(request, scenario_id):
    scenario = get_object_or_404(OptimizationScenario, id=scenario_id)
    results = scenario.results.all().order_by('priority')
    
    # Calculate cumulative metrics
    total_reduction = sum(result.emission_reduction for result in results)
    total_cost = sum(result.implementation_cost for result in results)
    total_savings = sum(result.annual_savings for result in results)
    average_roi = sum(result.expected_roi for result in results) / len(results) if results else 0
    
    context = {
        'scenario': scenario,
        'results': results,
        'total_reduction': total_reduction,
        'total_cost': total_cost,
        'total_savings': total_savings,
        'average_roi': average_roi,
        'remaining_budget': scenario.budget - total_cost
    }
    
    return render(request, 'appname/optimization_results.html', context)
