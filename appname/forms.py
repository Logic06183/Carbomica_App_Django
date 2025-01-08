# forms.py

from django import forms
from django.forms import inlineformset_factory
from .models import Facility, EmissionData, FacilityIntervention, Intervention, EmissionSource

class FacilityForm(forms.ModelForm):
    class Meta:
        model = Facility
        fields = ['code_name', 'display_name']
        labels = {
            'code_name': 'Facility Code',
            'display_name': 'Facility Name',
        }
        widgets = {
            'code_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g., HOSP001'}),
            'display_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g., Central Hospital'})
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
            'waste_management', 'medical_inhalers'
        ]
        labels = {
            'grid_electricity': 'Grid Electricity (kWh)',
            'grid_gas': 'Grid Gas (m³)',
            'bottled_gas': 'Bottled Gas (kg)',
            'liquid_fuel': 'Liquid Fuel (L)',
            'vehicle_fuel_owned': 'Vehicle Fuel - Owned (L)',
            'business_travel': 'Business Travel (km)',
            'anaesthetic_gases': 'Anaesthetic Gases (kg)',
            'refrigeration_gases': 'Refrigeration Gases (kg)',
            'waste_management': 'Waste Management (kg)',
            'medical_inhalers': 'Medical Inhalers (units)'
        }
        widgets = {
            'grid_electricity': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': '0.00'}),
            'grid_gas': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': '0.00'}),
            'bottled_gas': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': '0.00'}),
            'liquid_fuel': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': '0.00'}),
            'vehicle_fuel_owned': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': '0.00'}),
            'business_travel': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': '0.00'}),
            'anaesthetic_gases': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': '0.00'}),
            'refrigeration_gases': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': '0.00'}),
            'waste_management': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': '0.00'}),
            'medical_inhalers': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': '0.00'})
        }

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
