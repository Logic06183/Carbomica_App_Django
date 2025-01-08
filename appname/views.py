from django.shortcuts import render, redirect
from django.db.models import Sum
from django.contrib import messages
from decimal import Decimal
from .forms import (
    FacilityForm, 
    EmissionDataForm, 
    FacilityInterventionFormSet,
    EmissionSourceForm
)
from .models import (
    Facility, 
    EmissionData, 
    FacilityIntervention,
    EmissionSource,
    models
)
import json

def calculate_npv(intervention, discount_rate=0.05, years=10):
    """Calculate Net Present Value for an intervention"""
    initial_cost = float(intervention.implementation_cost)
    annual_savings = float(intervention.annual_savings)
    npv = -initial_cost
    for year in range(1, years + 1):
        npv += annual_savings / ((1 + discount_rate) ** year)
    return round(npv, 2)

def dashboard(request):
    # Dummy data for demonstration
    facilities_data = [
        {
            'name': 'Central Hospital',
            'total_emissions': 1200.5,
            'scope1_emissions': 400.2,
            'scope2_emissions': 600.1,
            'scope3_emissions': 200.2
        },
        {
            'name': 'North Clinic',
            'total_emissions': 800.3,
            'scope1_emissions': 300.1,
            'scope2_emissions': 400.1,
            'scope3_emissions': 100.1
        },
        {
            'name': 'South Medical Center',
            'total_emissions': 950.7,
            'scope1_emissions': 350.3,
            'scope2_emissions': 450.2,
            'scope3_emissions': 150.2
        },
        {
            'name': 'East Wing Hospital',
            'total_emissions': 700.2,
            'scope1_emissions': 250.1,
            'scope2_emissions': 350.0,
            'scope3_emissions': 100.1
        },
        {
            'name': 'West Health Center',
            'total_emissions': 600.8,
            'scope1_emissions': 200.3,
            'scope2_emissions': 300.3,
            'scope3_emissions': 100.2
        }
    ]

    # Calculate total emissions and percentages
    total_emissions = sum(f['total_emissions'] for f in facilities_data)
    max_emissions = max(f['total_emissions'] for f in facilities_data)
    
    for facility in facilities_data:
        facility['percentage'] = (facility['total_emissions'] / max_emissions) * 100

    # Prepare emissions data for chart
    emissions_data = {
        'labels': ['Scope 1', 'Scope 2', 'Scope 3'],
        'values': [
            sum(f['scope1_emissions'] for f in facilities_data),
            sum(f['scope2_emissions'] for f in facilities_data),
            sum(f['scope3_emissions'] for f in facilities_data)
        ]
    }

    # Update intervention analysis data with status and timeline information
    intervention_analysis = [
        {
            'name': 'Natural Ventilation Enhancement',
            'facility': 'Central Hospital',
            'status': 'Active',
            'implementation_date': '2024-12-01',
            'time_to_benefit': {
                'initial_benefits': '1 month',
                'full_benefits': '3 months',
                'progress': 75  # Percentage of full benefits achieved
            },
            'financial_metrics': {
                'implementation_cost': 75000,  # Lower cost alternative to HVAC
                'annual_savings': 25000,
                'roi': 33.3,
                'npv': 125000,
                'payback_period': 3.0,
                'carbon_credits': 15000
            },
            'environmental_metrics': {
                'emission_reduction': 2500,
                'trees_saved': 1250,
                'water_saved': 50000
            },
            'policy_metrics': {
                'sdg_impact': {
                    'AFFORDABLE CLEAN ENERGY': 85,
                    'GOOD HEALTH & WELLBEING': 90,
                    'CLIMATE ACTION': 75,
                    'REDUCED INEQUALITIES': 80
                },
                'policy_alignment': {
                    'LOCAL MANUFACTURING': 95,
                    'SKILLS DEVELOPMENT': 85,
                    'COMMUNITY BENEFIT': 90
                }
            }
        },
        {
            'name': 'Solar Water Heating',
            'facility': 'North Clinic',
            'status': 'Planning',
            'implementation_date': '2025-02-01',
            'time_to_benefit': {
                'initial_benefits': '1 month',
                'full_benefits': '2 months',
                'progress': 0  # Not started yet
            },
            'financial_metrics': {
                'implementation_cost': 120000,
                'annual_savings': 45000,
                'roi': 37.5,
                'npv': 185000,
                'payback_period': 2.7,
                'carbon_credits': 25000
            },
            'environmental_metrics': {
                'emission_reduction': 3500,
                'trees_saved': 1750,
                'water_saved': 75000
            },
            'policy_metrics': {
                'sdg_impact': {
                    'AFFORDABLE CLEAN ENERGY': 90,
                    'GOOD HEALTH & WELLBEING': 75,
                    'CLIMATE ACTION': 85,
                    'REDUCED INEQUALITIES': 70
                },
                'policy_alignment': {
                    'LOCAL MANUFACTURING': 90,
                    'SKILLS DEVELOPMENT': 80,
                    'COMMUNITY BENEFIT': 75
                }
            }
        },
        {
            'name': 'Medical Waste Segregation',
            'facility': 'South Medical Center',
            'status': 'Active',
            'implementation_date': '2024-11-15',
            'time_to_benefit': {
                'initial_benefits': 'Immediate',
                'full_benefits': '1 month',
                'progress': 100  # Fully implemented
            },
            'financial_metrics': {
                'implementation_cost': 45000,
                'annual_savings': 20000,
                'roi': 44.4,
                'npv': 95000,
                'payback_period': 2.25,
                'carbon_credits': 10000
            },
            'environmental_metrics': {
                'emission_reduction': 1500,
                'trees_saved': 750,
                'water_saved': 25000
            },
            'policy_metrics': {
                'sdg_impact': {
                    'AFFORDABLE CLEAN ENERGY': 60,
                    'GOOD HEALTH & WELLBEING': 95,
                    'CLIMATE ACTION': 80,
                    'REDUCED INEQUALITIES': 85
                },
                'policy_alignment': {
                    'LOCAL MANUFACTURING': 100,
                    'SKILLS DEVELOPMENT': 90,
                    'COMMUNITY BENEFIT': 85
                }
            }
        },
        {
            'name': 'Energy-Efficient Lighting',
            'facility': 'East Wing Hospital',
            'status': 'Active',
            'implementation_date': '2024-12-15',
            'time_to_benefit': {
                'initial_benefits': 'Immediate',
                'full_benefits': '2 weeks',
                'progress': 100  # Fully implemented
            },
            'financial_metrics': {
                'implementation_cost': 35000,
                'annual_savings': 15000,
                'roi': 42.9,
                'npv': 75000,
                'payback_period': 2.33,
                'carbon_credits': 8000
            },
            'environmental_metrics': {
                'emission_reduction': 1200,
                'trees_saved': 600,
                'water_saved': 20000
            },
            'policy_metrics': {
                'sdg_impact': {
                    'AFFORDABLE CLEAN ENERGY': 85,
                    'GOOD HEALTH & WELLBEING': 70,
                    'CLIMATE ACTION': 75,
                    'REDUCED INEQUALITIES': 80
                },
                'policy_alignment': {
                    'LOCAL MANUFACTURING': 85,
                    'SKILLS DEVELOPMENT': 75,
                    'COMMUNITY BENEFIT': 80
                }
            }
        },
        {
            'name': 'Rainwater Harvesting',
            'facility': 'West Health Center',
            'status': 'Implementation',
            'implementation_date': '2025-01-01',
            'time_to_benefit': {
                'initial_benefits': '1 month',
                'full_benefits': '6 months',  # Depends on rainy season
                'progress': 25  # Recently started
            },
            'financial_metrics': {
                'implementation_cost': 55000,
                'annual_savings': 22000,
                'roi': 40.0,
                'npv': 105000,
                'payback_period': 2.5,
                'carbon_credits': 12000
            },
            'environmental_metrics': {
                'emission_reduction': 1800,
                'trees_saved': 900,
                'water_saved': 150000
            },
            'policy_metrics': {
                'sdg_impact': {
                    'AFFORDABLE CLEAN ENERGY': 70,
                    'GOOD HEALTH & WELLBEING': 85,
                    'CLIMATE ACTION': 80,
                    'REDUCED INEQUALITIES': 90
                },
                'policy_alignment': {
                    'LOCAL MANUFACTURING': 95,
                    'SKILLS DEVELOPMENT': 85,
                    'COMMUNITY BENEFIT': 95
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
                'water_saved': 30000
            },
            'policy_metrics': {
                'sdg_impact': {
                    'AFFORDABLE CLEAN ENERGY': 95,
                    'GOOD HEALTH & WELLBEING': 100,
                    'CLIMATE ACTION': 85,
                    'REDUCED INEQUALITIES': 90
                },
                'policy_alignment': {
                    'LOCAL MANUFACTURING': 80,
                    'SKILLS DEVELOPMENT': 85,
                    'COMMUNITY BENEFIT': 100
                }
            }
        },
        {
            'name': 'Biogas from Medical Waste',
            'facility': 'District Hospital',
            'status': 'Implementation',
            'implementation_date': '2025-01-15',
            'time_to_benefit': {
                'initial_benefits': '2 months',
                'full_benefits': '6 months',
                'progress': 15
            },
            'financial_metrics': {
                'implementation_cost': 180000,
                'annual_savings': 65000,
                'roi': 36.1,
                'npv': 250000,
                'payback_period': 2.8,
                'carbon_credits': 35000
            },
            'environmental_metrics': {
                'emission_reduction': 5500,
                'trees_saved': 2750,
                'water_saved': 45000
            },
            'policy_metrics': {
                'sdg_impact': {
                    'AFFORDABLE CLEAN ENERGY': 90,
                    'GOOD HEALTH & WELLBEING': 85,
                    'CLIMATE ACTION': 95,
                    'REDUCED INEQUALITIES': 75
                },
                'policy_alignment': {
                    'LOCAL MANUFACTURING': 90,
                    'SKILLS DEVELOPMENT': 95,
                    'COMMUNITY BENEFIT': 85
                }
            }
        },
        {
            'name': 'Water-Efficient Medical Equipment',
            'facility': 'Community Clinic',
            'status': 'Active',
            'implementation_date': '2024-12-01',
            'time_to_benefit': {
                'initial_benefits': 'Immediate',
                'full_benefits': '2 weeks',
                'progress': 100
            },
            'financial_metrics': {
                'implementation_cost': 25000,
                'annual_savings': 12000,
                'roi': 48.0,
                'npv': 65000,
                'payback_period': 2.1,
                'carbon_credits': 5000
            },
            'environmental_metrics': {
                'emission_reduction': 800,
                'trees_saved': 400,
                'water_saved': 180000
            },
            'policy_metrics': {
                'sdg_impact': {
                    'AFFORDABLE CLEAN ENERGY': 70,
                    'GOOD HEALTH & WELLBEING': 85,
                    'CLIMATE ACTION': 75,
                    'REDUCED INEQUALITIES': 90
                },
                'policy_alignment': {
                    'LOCAL MANUFACTURING': 100,
                    'SKILLS DEVELOPMENT': 70,
                    'COMMUNITY BENEFIT': 85
                }
            }
        },
        {
            'name': 'Healthcare Waste Composting',
            'facility': 'Primary Health Center',
            'status': 'Planning',
            'implementation_date': '2025-02-15',
            'time_to_benefit': {
                'initial_benefits': '1 month',
                'full_benefits': '3 months',
                'progress': 0
            },
            'financial_metrics': {
                'implementation_cost': 30000,
                'annual_savings': 18000,
                'roi': 60.0,
                'npv': 85000,
                'payback_period': 1.7,
                'carbon_credits': 9000
            },
            'environmental_metrics': {
                'emission_reduction': 1600,
                'trees_saved': 800,
                'water_saved': 15000
            },
            'policy_metrics': {
                'sdg_impact': {
                    'AFFORDABLE CLEAN ENERGY': 75,
                    'GOOD HEALTH & WELLBEING': 90,
                    'CLIMATE ACTION': 85,
                    'REDUCED INEQUALITIES': 85
                },
                'policy_alignment': {
                    'LOCAL MANUFACTURING': 100,
                    'SKILLS DEVELOPMENT': 90,
                    'COMMUNITY BENEFIT': 95
                }
            }
        },
        {
            'name': 'Mobile Solar Medical Units',
            'facility': 'Rural Outreach Program',
            'status': 'Planning',
            'implementation_date': '2025-04-01',
            'time_to_benefit': {
                'initial_benefits': 'Immediate',
                'full_benefits': '1 month',
                'progress': 0
            },
            'financial_metrics': {
                'implementation_cost': 150000,
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

    # Calculate prioritization metrics for each intervention
    for intervention in intervention_analysis:
        # Cost per ton of CO2 reduced (lower is better)
        intervention['prioritization_metrics'] = {
            'cost_per_ton_co2': round(intervention['financial_metrics']['implementation_cost'] / 
                                    (intervention['environmental_metrics']['emission_reduction'] / 1000), 2),
            'annual_savings_per_cost': round((intervention['financial_metrics']['annual_savings'] / 
                                            intervention['financial_metrics']['implementation_cost']) * 100, 2),
            'emission_reduction_score': round((intervention['environmental_metrics']['emission_reduction'] / 1000) * 
                                            (intervention['financial_metrics']['annual_savings'] / 
                                             intervention['financial_metrics']['implementation_cost']), 2),
            'implementation_complexity': 'Low' if intervention['time_to_benefit']['full_benefits'] in ['2 weeks', '1 month'] 
                                      else 'Medium' if intervention['time_to_benefit']['full_benefits'] in ['2 months', '3 months']
                                      else 'High'
        }
    
    # Sort interventions by different metrics
    prioritized_interventions = {
        'cost_effective': sorted(intervention_analysis, 
                               key=lambda x: x['prioritization_metrics']['cost_per_ton_co2']),
        'quick_wins': sorted(intervention_analysis, 
                           key=lambda x: (-x['prioritization_metrics']['annual_savings_per_cost'], 
                                        x['time_to_benefit']['full_benefits'])),
        'highest_impact': sorted(intervention_analysis, 
                               key=lambda x: -x['environmental_metrics']['emission_reduction'])
    }

    context = {
        'total_facilities': len(facilities_data),
        'total_emissions': total_emissions,
        'active_interventions': len(intervention_analysis),
        'potential_savings': sum(i['financial_metrics']['annual_savings'] for i in intervention_analysis),
        'top_facilities': facilities_data,
        'emissions_data': json.dumps(emissions_data),
        'intervention_analysis': intervention_analysis,
        'prioritized_interventions': prioritized_interventions,
        'total_emission_reduction': sum(intervention['environmental_metrics']['emission_reduction'] for intervention in intervention_analysis),
        'total_investment_needed': sum(intervention['financial_metrics']['implementation_cost'] for intervention in intervention_analysis)
    }

    return render(request, 'appname/dashboard.html', context)

def add_facility(request):
    if request.method == 'POST':
        facility_form = FacilityForm(request.POST)
        emission_form = EmissionDataForm(request.POST)
        
        if facility_form.is_valid():
            facility = facility_form.save()
            
            # Create a default emission source for the facility
            emission_source = EmissionSource.objects.create(
                facility=facility,
                code_name=f"{facility.code_name}_main",
                display_name=f"{facility.display_name} Main Source"
            )
            
            if emission_form.is_valid():
                emission_data = emission_form.save(commit=False)
                emission_data.emission_source = emission_source
                emission_data.save()

                intervention_formset = FacilityInterventionFormSet(request.POST, instance=facility)
                if intervention_formset.is_valid():
                    intervention_formset.save()
                    messages.success(request, 'Facility added successfully!')
                    return redirect('dashboard')
                else:
                    messages.error(request, 'Error in intervention data.')
            else:
                messages.error(request, 'Error in emission data.')
                facility.delete()  # Clean up if emission data is invalid
        else:
            messages.error(request, 'Error in facility data.')
    else:
        facility_form = FacilityForm()
        emission_form = EmissionDataForm()
        intervention_formset = FacilityInterventionFormSet()

    return render(request, 'appname/add_facility.html', {
        'facility_form': facility_form,
        'emission_form': emission_form,
        'intervention_formset': intervention_formset
    })

def interventions(request):
    # Update intervention analysis data with status and timeline information
    intervention_analysis = [
        {
            'name': 'Natural Ventilation Enhancement',
            'facility': 'Central Hospital',
            'status': 'Active',
            'implementation_date': '2024-12-01',
            'time_to_benefit': {
                'initial_benefits': '1 month',
                'full_benefits': '3 months',
                'progress': 75  # Percentage of full benefits achieved
            },
            'financial_metrics': {
                'implementation_cost': 75000,
                'annual_savings': 25000,
                'roi': 33.3,
                'npv': 125000,
                'payback_period': 3.0,
                'carbon_credits': 15000
            },
            'environmental_metrics': {
                'emission_reduction': 2500,
                'trees_saved': 1250,
                'water_saved': 50000
            },
            'policy_metrics': {
                'sdg_impact': {
                    'AFFORDABLE CLEAN ENERGY': 85,
                    'GOOD HEALTH & WELLBEING': 90,
                    'CLIMATE ACTION': 75,
                    'REDUCED INEQUALITIES': 80
                },
                'policy_alignment': {
                    'LOCAL MANUFACTURING': 95,
                    'SKILLS DEVELOPMENT': 85,
                    'COMMUNITY BENEFIT': 90
                }
            }
        },
        {
            'name': 'Solar Water Heating',
            'facility': 'North Clinic',
            'status': 'Planning',
            'implementation_date': '2025-02-01',
            'time_to_benefit': {
                'initial_benefits': '1 month',
                'full_benefits': '2 months',
                'progress': 0  # Not started yet
            },
            'financial_metrics': {
                'implementation_cost': 120000,
                'annual_savings': 45000,
                'roi': 37.5,
                'npv': 185000,
                'payback_period': 2.7,
                'carbon_credits': 25000
            },
            'environmental_metrics': {
                'emission_reduction': 3500,
                'trees_saved': 1750,
                'water_saved': 75000
            },
            'policy_metrics': {
                'sdg_impact': {
                    'AFFORDABLE CLEAN ENERGY': 90,
                    'GOOD HEALTH & WELLBEING': 75,
                    'CLIMATE ACTION': 85,
                    'REDUCED INEQUALITIES': 70
                },
                'policy_alignment': {
                    'LOCAL MANUFACTURING': 90,
                    'SKILLS DEVELOPMENT': 80,
                    'COMMUNITY BENEFIT': 75
                }
            }
        },
        {
            'name': 'Medical Waste Segregation',
            'facility': 'South Medical Center',
            'status': 'Active',
            'implementation_date': '2024-11-15',
            'time_to_benefit': {
                'initial_benefits': 'Immediate',
                'full_benefits': '1 month',
                'progress': 100  # Fully implemented
            },
            'financial_metrics': {
                'implementation_cost': 45000,
                'annual_savings': 20000,
                'roi': 44.4,
                'npv': 95000,
                'payback_period': 2.25,
                'carbon_credits': 10000
            },
            'environmental_metrics': {
                'emission_reduction': 1500,
                'trees_saved': 750,
                'water_saved': 25000
            },
            'policy_metrics': {
                'sdg_impact': {
                    'AFFORDABLE CLEAN ENERGY': 60,
                    'GOOD HEALTH & WELLBEING': 95,
                    'CLIMATE ACTION': 80,
                    'REDUCED INEQUALITIES': 85
                },
                'policy_alignment': {
                    'LOCAL MANUFACTURING': 100,
                    'SKILLS DEVELOPMENT': 90,
                    'COMMUNITY BENEFIT': 85
                }
            }
        },
        {
            'name': 'Energy-Efficient Lighting',
            'facility': 'East Wing Hospital',
            'status': 'Active',
            'implementation_date': '2024-12-15',
            'time_to_benefit': {
                'initial_benefits': 'Immediate',
                'full_benefits': '2 weeks',
                'progress': 100  # Fully implemented
            },
            'financial_metrics': {
                'implementation_cost': 35000,
                'annual_savings': 15000,
                'roi': 42.9,
                'npv': 75000,
                'payback_period': 2.33,
                'carbon_credits': 8000
            },
            'environmental_metrics': {
                'emission_reduction': 1200,
                'trees_saved': 600,
                'water_saved': 20000
            },
            'policy_metrics': {
                'sdg_impact': {
                    'AFFORDABLE CLEAN ENERGY': 85,
                    'GOOD HEALTH & WELLBEING': 70,
                    'CLIMATE ACTION': 75,
                    'REDUCED INEQUALITIES': 80
                },
                'policy_alignment': {
                    'LOCAL MANUFACTURING': 85,
                    'SKILLS DEVELOPMENT': 75,
                    'COMMUNITY BENEFIT': 80
                }
            }
        },
        {
            'name': 'Rainwater Harvesting',
            'facility': 'West Health Center',
            'status': 'Implementation',
            'implementation_date': '2025-01-01',
            'time_to_benefit': {
                'initial_benefits': '1 month',
                'full_benefits': '6 months',  # Depends on rainy season
                'progress': 25  # Recently started
            },
            'financial_metrics': {
                'implementation_cost': 55000,
                'annual_savings': 22000,
                'roi': 40.0,
                'npv': 105000,
                'payback_period': 2.5,
                'carbon_credits': 12000
            },
            'environmental_metrics': {
                'emission_reduction': 1800,
                'trees_saved': 900,
                'water_saved': 150000
            },
            'policy_metrics': {
                'sdg_impact': {
                    'AFFORDABLE CLEAN ENERGY': 70,
                    'GOOD HEALTH & WELLBEING': 85,
                    'CLIMATE ACTION': 80,
                    'REDUCED INEQUALITIES': 90
                },
                'policy_alignment': {
                    'LOCAL MANUFACTURING': 95,
                    'SKILLS DEVELOPMENT': 85,
                    'COMMUNITY BENEFIT': 95
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
                'water_saved': 30000
            },
            'policy_metrics': {
                'sdg_impact': {
                    'AFFORDABLE CLEAN ENERGY': 95,
                    'GOOD HEALTH & WELLBEING': 100,
                    'CLIMATE ACTION': 85,
                    'REDUCED INEQUALITIES': 90
                },
                'policy_alignment': {
                    'LOCAL MANUFACTURING': 80,
                    'SKILLS DEVELOPMENT': 85,
                    'COMMUNITY BENEFIT': 100
                }
            }
        },
        {
            'name': 'Biogas from Medical Waste',
            'facility': 'District Hospital',
            'status': 'Implementation',
            'implementation_date': '2025-01-15',
            'time_to_benefit': {
                'initial_benefits': '2 months',
                'full_benefits': '6 months',
                'progress': 15
            },
            'financial_metrics': {
                'implementation_cost': 180000,
                'annual_savings': 65000,
                'roi': 36.1,
                'npv': 250000,
                'payback_period': 2.8,
                'carbon_credits': 35000
            },
            'environmental_metrics': {
                'emission_reduction': 5500,
                'trees_saved': 2750,
                'water_saved': 45000
            },
            'policy_metrics': {
                'sdg_impact': {
                    'AFFORDABLE CLEAN ENERGY': 90,
                    'GOOD HEALTH & WELLBEING': 85,
                    'CLIMATE ACTION': 95,
                    'REDUCED INEQUALITIES': 75
                },
                'policy_alignment': {
                    'LOCAL MANUFACTURING': 90,
                    'SKILLS DEVELOPMENT': 95,
                    'COMMUNITY BENEFIT': 85
                }
            }
        },
        {
            'name': 'Water-Efficient Medical Equipment',
            'facility': 'Community Clinic',
            'status': 'Active',
            'implementation_date': '2024-12-01',
            'time_to_benefit': {
                'initial_benefits': 'Immediate',
                'full_benefits': '2 weeks',
                'progress': 100
            },
            'financial_metrics': {
                'implementation_cost': 25000,
                'annual_savings': 12000,
                'roi': 48.0,
                'npv': 65000,
                'payback_period': 2.1,
                'carbon_credits': 5000
            },
            'environmental_metrics': {
                'emission_reduction': 800,
                'trees_saved': 400,
                'water_saved': 180000
            },
            'policy_metrics': {
                'sdg_impact': {
                    'AFFORDABLE CLEAN ENERGY': 70,
                    'GOOD HEALTH & WELLBEING': 85,
                    'CLIMATE ACTION': 75,
                    'REDUCED INEQUALITIES': 90
                },
                'policy_alignment': {
                    'LOCAL MANUFACTURING': 100,
                    'SKILLS DEVELOPMENT': 70,
                    'COMMUNITY BENEFIT': 85
                }
            }
        },
        {
            'name': 'Healthcare Waste Composting',
            'facility': 'Primary Health Center',
            'status': 'Planning',
            'implementation_date': '2025-02-15',
            'time_to_benefit': {
                'initial_benefits': '1 month',
                'full_benefits': '3 months',
                'progress': 0
            },
            'financial_metrics': {
                'implementation_cost': 30000,
                'annual_savings': 18000,
                'roi': 60.0,
                'npv': 85000,
                'payback_period': 1.7,
                'carbon_credits': 9000
            },
            'environmental_metrics': {
                'emission_reduction': 1600,
                'trees_saved': 800,
                'water_saved': 15000
            },
            'policy_metrics': {
                'sdg_impact': {
                    'AFFORDABLE CLEAN ENERGY': 75,
                    'GOOD HEALTH & WELLBEING': 90,
                    'CLIMATE ACTION': 85,
                    'REDUCED INEQUALITIES': 85
                },
                'policy_alignment': {
                    'LOCAL MANUFACTURING': 100,
                    'SKILLS DEVELOPMENT': 90,
                    'COMMUNITY BENEFIT': 95
                }
            }
        },
        {
            'name': 'Mobile Solar Medical Units',
            'facility': 'Rural Outreach Program',
            'status': 'Planning',
            'implementation_date': '2025-04-01',
            'time_to_benefit': {
                'initial_benefits': 'Immediate',
                'full_benefits': '1 month',
                'progress': 0
            },
            'financial_metrics': {
                'implementation_cost': 150000,
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
    ]

    context = {
        'interventions': intervention_analysis
    }
    
    return render(request, 'appname/interventions.html', context)
