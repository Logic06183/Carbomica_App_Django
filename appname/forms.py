# forms.py

from django import forms
from django.forms import inlineformset_factory
from .models import Facility, EmissionData, FacilityIntervention, Intervention

class FacilityForm(forms.ModelForm):
    class Meta:
        model = Facility
        fields = ['code_name', 'display_name']
        labels = {
            'code_name': 'Code Name',
            'display_name': 'Display Name',
        }

class EmissionDataForm(forms.ModelForm):
    class Meta:
        model = EmissionData
        fields = ['grid_electricity', 'grid_gas', 'bottled_gas', 'liquid_fuel', 'vehicle_fuel_owned', 'business_travel', 'anaesthetic_gases', 'refrigeration_gases', 'waste_management', 'medical_inhalers']
        labels = {
            'grid_electricity': 'Grid Electricity',
            'grid_gas': 'Grid Gas',
            # ... continue for each field ...
        }

FacilityInterventionFormSet = inlineformset_factory(
    Facility, 
    FacilityIntervention, 
    fields=('intervention', 'implementation_cost', 'maintenance_cost'), 
    extra=1, 
    can_delete=True
)

class InterventionForm(forms.ModelForm):
    class Meta:
        model = Intervention
        fields = ['code_name', 'display_name']
        labels = {
            'code_name': 'Code Name',
            'display_name': 'Display Name',
        }
