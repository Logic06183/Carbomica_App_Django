from django.shortcuts import render, redirect
from django.db.models import Sum
from django.contrib import messages
from decimal import Decimal
from .forms import (
    FacilityForm,
    EmissionSourceForm,
    InterventionForm,
    EmissionDataForm,
    PolicyForm
)
from .models import (
    Facility,
    EmissionSource,
    Intervention,
    EmissionData,
    Policy
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
    """Main dashboard view showing key metrics and visualizations"""
    
    # Get all facilities
    facilities = Facility.objects.all()
    
    # Calculate total emissions
    total_emissions = EmissionData.objects.aggregate(
        total=Sum('amount')
    )['total'] or 0
    
    # Get emission sources breakdown
    emission_sources = EmissionSource.objects.all()
    source_breakdown = []
    for source in emission_sources:
        amount = EmissionData.objects.filter(source=source).aggregate(
            total=Sum('amount')
        )['total'] or 0
        source_breakdown.append({
            'name': source.name,
            'amount': amount,
            'percentage': (amount / total_emissions * 100) if total_emissions > 0 else 0
        })
    
    # Get interventions summary
    interventions = Intervention.objects.all()
    intervention_summary = {
        'total': interventions.count(),
        'completed': interventions.filter(status='Completed').count(),
        'in_progress': interventions.filter(status='In Progress').count(),
        'planned': interventions.filter(status='Planned').count()
    }
    
    # Calculate financial metrics
    total_investment = sum(i.implementation_cost for i in interventions)
    total_savings = sum(i.annual_savings for i in interventions)
    roi = (total_savings / total_investment * 100) if total_investment > 0 else 0
    
    # Get policy compliance
    policies = Policy.objects.all()
    policy_compliance = []
    for policy in policies:
        compliance_score = policy.compliance_score
        policy_compliance.append({
            'name': policy.name,
            'score': compliance_score,
            'status': 'Compliant' if compliance_score >= 80 else 'Non-Compliant'
        })
    
    # Prepare time series data
    emission_trend = EmissionData.objects.values('date').annotate(
        total=Sum('amount')
    ).order_by('date')
    
    # Calculate year-over-year change
    if len(emission_trend) >= 2:
        current = emission_trend.latest('date')['total']
        previous = emission_trend.earliest('date')['total']
        yoy_change = ((current - previous) / previous * 100)
    else:
        yoy_change = 0
    
    # Prepare facility comparison data
    facility_comparison = []
    for facility in facilities:
        emissions = EmissionData.objects.filter(facility=facility).aggregate(
            total=Sum('amount')
        )['total'] or 0
        facility_comparison.append({
            'name': facility.name,
            'emissions': emissions,
            'efficiency_score': facility.efficiency_score
        })
    
    # Calculate intervention effectiveness
    intervention_effectiveness = []
    for intervention in interventions:
        if intervention.status == 'Completed':
            reduction = intervention.emission_reduction
            cost_per_ton = (intervention.implementation_cost / reduction 
                          if reduction > 0 else 0)
            intervention_effectiveness.append({
                'name': intervention.name,
                'reduction': reduction,
                'cost_per_ton': cost_per_ton,
                'roi': intervention.roi
            })
    
    # Sort interventions by effectiveness
    intervention_effectiveness.sort(key=lambda x: x['cost_per_ton'])
    
    # Prepare recommendations based on data
    recommendations = []
    
    # Check high-emission sources
    for source in source_breakdown:
        if source['percentage'] > 20:
            recommendations.append({
                'type': 'High Emission Source',
                'description': f"Consider prioritizing reduction measures for {source['name']}",
                'priority': 'High'
            })
    
    # Check facility performance
    for facility in facility_comparison:
        if facility['efficiency_score'] < 60:
            recommendations.append({
                'type': 'Facility Performance',
                'description': f"Implement efficiency measures at {facility['name']}",
                'priority': 'Medium'
            })
    
    # Check policy compliance
    for policy in policy_compliance:
        if policy['status'] == 'Non-Compliant':
            recommendations.append({
                'type': 'Policy Compliance',
                'description': f"Address compliance issues with {policy['name']}",
                'priority': 'High'
            })
    
    context = {
        'total_emissions': total_emissions,
        'source_breakdown': source_breakdown,
        'intervention_summary': intervention_summary,
        'financial_metrics': {
            'total_investment': total_investment,
            'total_savings': total_savings,
            'roi': roi
        },
        'policy_compliance': policy_compliance,
        'emission_trend': emission_trend,
        'yoy_change': yoy_change,
        'facility_comparison': facility_comparison,
        'intervention_effectiveness': intervention_effectiveness,
        'recommendations': recommendations
    }
    
    return render(request, 'appname/dashboard.html', context)

def add_facility(request):
    """Add a new healthcare facility"""
    if request.method == 'POST':
        form = FacilityForm(request.POST)
        if form.is_valid():
            facility = form.save(commit=False)
            
            # Calculate initial efficiency score based on facility type and size
            base_score = 70  # Default base score
            
            # Adjust based on facility type
            type_adjustments = {
                'Hospital': 0,
                'Clinic': +5,
                'Laboratory': -5
            }
            base_score += type_adjustments.get(facility.facility_type, 0)
            
            # Adjust based on size
            if facility.size < 1000:  # Small facility
                base_score += 5
            elif facility.size > 5000:  # Large facility
                base_score -= 5
                
            facility.efficiency_score = min(100, max(0, base_score))
            facility.save()
            
            messages.success(request, 'Facility added successfully!')
            return redirect('dashboard')
    else:
        form = FacilityForm()
    
    return render(request, 'appname/add_facility.html', {'form': form})

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
