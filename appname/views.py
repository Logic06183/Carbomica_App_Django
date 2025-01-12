from django.shortcuts import render, redirect, get_object_or_404
from django.db.models import Sum, F
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
    total_emissions = EmissionData.objects.aggregate(
        total=Sum(
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
    )['total'] or 0
    
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
        total_emissions=Sum(
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
            total=Sum(
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
    
    context = {
        'facilities': facility_emissions,
        'total_emissions': total_emissions,
        'active_interventions': active_interventions,
        'total_investment': total_investment,
        'source_breakdown': source_breakdown,
        'optimization_scenarios': optimization_scenarios,
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
    """View and analyze interventions"""
    
    # Get all interventions
    db_interventions = Intervention.objects.all()
    
    # Prepare intervention analysis
    intervention_analysis = [
        {
            'name': 'LED Lighting Upgrade',
            'facility': 'Main Hospital',
            'status': 'Completed',
            'implementation_date': '2024-06-15',
            'time_to_benefit': {
                'initial_benefits': 'Immediate',
                'full_benefits': '1 month',
                'progress': 100
            },
            'financial_metrics': {
                'implementation_cost': 50000,
                'annual_savings': 25000,
                'roi': 50.0,
                'npv': 120000,
                'payback_period': 2.0,
                'carbon_credits': 15000
            },
            'environmental_metrics': {
                'emission_reduction': 3000,
                'trees_saved': 1500,
                'water_saved': 10000
            },
            'policy_metrics': {
                'sdg_impact': {
                    'AFFORDABLE CLEAN ENERGY': 85,
                    'GOOD HEALTH & WELLBEING': 90,
                    'CLIMATE ACTION': 75,
                    'REDUCED INEQUALITIES': 80
                },
                'policy_alignment': {
                    'LOCAL MANUFACTURING': 75,
                    'SKILLS DEVELOPMENT': 80,
                    'COMMUNITY BENEFIT': 85
                }
            }
        }
    ]

    # Additional LMIC-relevant interventions
    intervention_analysis.extend([
        {
            'name': 'Solar-Powered Vaccine Storage',
            'facility': 'Rural Health Center',
            'status': 'Planning',
            'implementation_date': '2025-03-01',
            'time_to_benefit': {
                'initial_benefits': '1 week',
                'full_benefits': '1 month',
                'progress': 0
            },
            'financial_metrics': {
                'implementation_cost': 85000,
                'annual_savings': 35000,
                'roi': 41.2,
                'npv': 155000,
                'payback_period': 2.4,
                'carbon_credits': 18000
            },
            'environmental_metrics': {
                'emission_reduction': 4200,
                'trees_saved': 2100,
                'water_saved': 15000
            },
            'policy_metrics': {
                'sdg_impact': {
                    'AFFORDABLE CLEAN ENERGY': 90,
                    'GOOD HEALTH & WELLBEING': 95,
                    'CLIMATE ACTION': 80,
                    'REDUCED INEQUALITIES': 90
                },
                'policy_alignment': {
                    'LOCAL MANUFACTURING': 80,
                    'SKILLS DEVELOPMENT': 85,
                    'COMMUNITY BENEFIT': 95
                }
            }
        },
        {
            'name': 'Waste Management System',
            'facility': 'District Hospital',
            'status': 'In Progress',
            'implementation_date': '2024-09-01',
            'time_to_benefit': {
                'initial_benefits': '2 weeks',
                'full_benefits': '3 months',
                'progress': 60
            },
            'financial_metrics': {
                'implementation_cost': 75000,
                'annual_savings': 55000,
                'roi': 36.7,
                'npv': 200000,
                'payback_period': 2.7,
                'carbon_credits': 28000
            },
            'environmental_metrics': {
                'emission_reduction': 3800,
                'trees_saved': 1900,
                'water_saved': 25000
            },
            'policy_metrics': {
                'sdg_impact': {
                    'AFFORDABLE CLEAN ENERGY': 95,
                    'GOOD HEALTH & WELLBEING': 100,
                    'CLIMATE ACTION': 85,
                    'REDUCED INEQUALITIES': 100
                },
                'policy_alignment': {
                    'LOCAL MANUFACTURING': 85,
                    'SKILLS DEVELOPMENT': 90,
                    'COMMUNITY BENEFIT': 100
                }
            }
        }
    ])

    context = {
        'interventions': intervention_analysis
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
