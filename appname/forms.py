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

# RAW ACTIVITY UNITS for every emission field. Users enter these physical
# quantities — CARBOMICA converts to tCO₂e in the background via the factors
# in modeling.py (see /methodology/). Shared by EmissionDataForm and
# EmissionDataUpdateForm so the unit guidance can never diverge again
# (the 2026-05 incident: one form said "enter tCO₂e directly" while the
# backend expected raw units — users who complied got garbage numbers).
EMISSION_FIELD_LABELS = {
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


class EmissionDataForm(forms.ModelForm):
    class Meta:
        model = EmissionData
        fields = list(EMISSION_FIELD_LABELS)
        labels = EMISSION_FIELD_LABELS
        widgets = {f: forms.NumberInput(attrs={'class': 'form-control', 'placeholder': '0.00'})
                   for f in EMISSION_FIELD_LABELS}

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
    """
    A scenario is constrained by EXACTLY ONE of budget / target_reduction —
    the `mode` radio picks which. Requiring both made no sense (and
    target_reduction wasn't even read by the optimiser): the optimiser
    either maximises reduction within a budget, or finds the cheapest set
    of interventions that achieves a reduction target.
    """
    MODE_CHOICES = [
        ('budget', 'Optimise within a budget'),
        ('target', 'Hit a reduction target'),
    ]
    mode = forms.ChoiceField(
        choices=MODE_CHOICES,
        initial='budget',
        widget=forms.RadioSelect(attrs={'class': 'form-check-input'}),
    )

    class Meta:
        model = OptimizationScenario
        fields = ['name', 'budget', 'target_reduction']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'budget': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0'}),
            'target_reduction': forms.NumberInput(attrs={'class': 'form-control', 'step': '1', 'min': '1', 'max': '100'}),
        }

    def clean(self):
        cleaned = super().clean()
        mode = cleaned.get('mode')
        budget = cleaned.get('budget')
        target = cleaned.get('target_reduction')

        if mode == 'budget':
            if budget in (None, ''):
                self.add_error('budget', 'Enter a budget, or switch to "Hit a reduction target".')
            elif budget <= 0:
                self.add_error('budget', 'Budget must be greater than zero.')
            cleaned['target_reduction'] = None   # explicitly unused in this mode
        elif mode == 'target':
            if target in (None, ''):
                self.add_error('target_reduction', 'Enter a reduction target, or switch to "Optimise within a budget".')
            elif not (0 < target <= 100):
                self.add_error('target_reduction', 'Target must be between 1 and 100 percent.')
            cleaned['budget'] = None             # explicitly unused in this mode
        return cleaned

class EmissionDataUpdateForm(forms.ModelForm):
    class Meta:
        model = EmissionData
        fields = list(EMISSION_FIELD_LABELS)
        labels = EMISSION_FIELD_LABELS
        widgets = {field: forms.NumberInput(attrs={'class': 'form-control'})
                   for field in EMISSION_FIELD_LABELS}
