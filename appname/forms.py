# forms.py

from django import forms
from django.forms import inlineformset_factory
from .models import Facility, EmissionData, FacilityIntervention, Intervention, EmissionSource, Policy, OptimizationScenario

class FacilityForm(forms.ModelForm):
    class Meta:
        model = Facility
        fields = ['code_name', 'display_name', 'country', 'facility_type']
        labels = {
            'code_name': 'Facility Code',
            'display_name': 'Facility Name',
            'country': 'Country',
            'facility_type': 'Facility Type',
        }
        widgets = {
            'code_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g., HOSP001'}),
            'display_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g., Central Hospital'}),
            'country': forms.Select(attrs={'class': 'form-select'}),
            'facility_type': forms.Select(attrs={'class': 'form-select'}),
        }

class EmissionSourceForm(forms.ModelForm):
    class Meta:
        model = EmissionSource
        fields = ['code_name', 'display_name']
        widgets = {
            'code_name': forms.TextInput(attrs={'class': 'form-control'}),
            'display_name': forms.TextInput(attrs={'class': 'form-control'})
        }

class EmissionDataForm(forms.ModelForm):
    class Meta:
        model = EmissionData
        fields = [
            'grid_electricity', 'grid_gas', 'bottled_gas',
            'liquid_fuel', 'vehicle_fuel_owned', 'business_travel',
            'anaesthetic_gases', 'refrigeration_gases',
            'waste_management', 'medical_inhalers', 'contractor_logistics',
        ]
        labels = {
            'grid_electricity':    'Grid Electricity (kWh/yr)',
            'grid_gas':            'Grid Gas (m³/yr)',
            'bottled_gas':         'Bottled Gas / LPG (kg/yr)',
            'liquid_fuel':         'Liquid Fuel (litres/yr)',
            'vehicle_fuel_owned':  'Vehicle Fuel — Owned (litres/yr)',
            'business_travel':     'Business Travel (km/yr)',
            'anaesthetic_gases':   'Anaesthetic Gases (kg/yr)',
            'refrigeration_gases': 'Refrigeration Gases (kg/yr)',
            'waste_management':    'Waste Management (tonnes/yr)',
            'medical_inhalers':    'Medical Inhalers — pMDIs (units/yr)',
            'contractor_logistics': 'Contractor Logistics (km/yr)',
        }
        widgets = {f: forms.NumberInput(attrs={'class': 'form-control', 'placeholder': '0.00'})
                   for f in fields}

class InterventionForm(forms.ModelForm):
    class Meta:
        model = Intervention
        fields = ['code_name', 'display_name']
        widgets = {
            'code_name': forms.TextInput(attrs={'class': 'form-control'}),
            'display_name': forms.TextInput(attrs={'class': 'form-control'})
        }

class FacilityInterventionForm(forms.ModelForm):
    class Meta:
        model = FacilityIntervention
        fields = ['intervention', 'implementation_cost', 'maintenance_cost']
        widgets = {
            'intervention': forms.Select(attrs={'class': 'form-control'}),
            'implementation_cost': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': '0.00'}),
            'maintenance_cost': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': '0.00'})
        }

FacilityInterventionFormSet = inlineformset_factory(
    Facility, 
    FacilityIntervention,
    form=FacilityInterventionForm,
    fields=('intervention', 'implementation_cost', 'maintenance_cost'),
    extra=1,
    can_delete=True
)

class PolicyForm(forms.ModelForm):
    class Meta:
        model = Policy
        fields = ['name', 'description', 'compliance_score', 'implementation_date', 'status']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'compliance_score': forms.NumberInput(attrs={'class': 'form-control', 'min': 0, 'max': 100}),
            'implementation_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'status': forms.Select(attrs={'class': 'form-control'})
        }

class OptimizationScenarioForm(forms.ModelForm):
    class Meta:
        model = OptimizationScenario
        fields = ['name', 'budget', 'target_reduction']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'budget': forms.NumberInput(attrs={'class': 'form-control'}),
            'target_reduction': forms.NumberInput(attrs={'class': 'form-control'})
        }

class EmissionDataUpdateForm(forms.ModelForm):
    class Meta:
        model = EmissionData
        fields = [
            'grid_electricity', 'grid_gas', 'bottled_gas', 'liquid_fuel',
            'vehicle_fuel_owned', 'business_travel', 'anaesthetic_gases',
            'refrigeration_gases', 'waste_management', 'medical_inhalers',
            'contractor_logistics',
        ]
        widgets = {field: forms.NumberInput(attrs={'class': 'form-control'})
                   for field in fields}
