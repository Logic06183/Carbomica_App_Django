# forms.py

from decimal import Decimal

from django import forms
from django.forms import inlineformset_factory
from .models import Facility, EmissionData, FacilityIntervention, Intervention, EmissionSource, Policy, OptimizationScenario, Organisation

class FacilityForm(forms.ModelForm):
    class Meta:
        model = Facility
        fields = ['code_name', 'display_name', 'sector', 'country', 'facility_type',
                  'organisation']
        labels = {
            'code_name': 'Code',
            'display_name': 'Name',
            'sector': 'Sector',
            'country': 'Country',
            'facility_type': 'Type',
            'organisation': 'Belongs to',
        }
        help_texts = {
            'organisation': 'Which entity owns this site. Everyone in that '
                            'organisation, and anyone above it, will see it.',
        }
        widgets = {
            'code_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g., HOSP001 / NGO_KE / LAB_42'}),
            'display_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g., Mt Darwin Hospital / Climate Research Unit'}),
            'sector': forms.Select(attrs={'class': 'form-select'}),
            'country': forms.Select(attrs={'class': 'form-select'}),
            'facility_type': forms.Select(attrs={'class': 'form-select'}),
            'organisation': forms.Select(attrs={'class': 'form-select'}),
        }

    def __init__(self, *args, user=None, **kwargs):
        """
        Scope the organisation picker to what this user may file a site under.

        Without the filter the dropdown would list every organisation in the
        database, letting anyone attach a site to another consortium's entity
        and expose its data to that consortium's members.
        """
        super().__init__(*args, **kwargs)
        field = self.fields['organisation']
        field.required = False
        field.empty_label = '— Not part of an organisation —'
        if user is not None:
            from appname.views import _visible_org_ids
            field.queryset = Organisation.objects.filter(
                pk__in=_visible_org_ids(user)
            ).order_by('name')
        else:
            field.queryset = Organisation.objects.none()

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
            'flights', 'lab_consumables',
        ]
        labels = {
            'grid_electricity':    'Grid Electricity (kWh/yr)',
            'grid_gas':            'Grid Gas (m³/yr)',
            'bottled_gas':         'Bottled Gas / LPG (kg/yr)',
            'liquid_fuel':         'Liquid Fuel (litres/yr)',
            'vehicle_fuel_owned':  'Vehicle Fuel — Owned (litres/yr)',
            'business_travel':     'Business Travel — Road (km/yr)',
            'anaesthetic_gases':   'Anaesthetic Gases (kg/yr)',
            'refrigeration_gases': 'Refrigeration Gases (kg/yr)',
            'waste_management':    'Waste Management (tonnes/yr)',
            'medical_inhalers':    'Medical Inhalers — pMDIs (units/yr)',
            'contractor_logistics': 'Contractor Logistics (km/yr)',
            'flights':             'Flights (passenger-km/yr)',
            'lab_consumables':     'Lab Consumables & Procurement (USD spend/yr)',
        }
        widgets = {f: forms.NumberInput(attrs={'class': 'form-control', 'placeholder': '0.00'})
                   for f in fields}

    def __init__(self, *args, **kwargs):
        # Every category is optional — "enter 0 for what you don't track yet".
        # Missing/blank values are coerced to 0 in clean() below.
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.required = False

    def clean(self):
        cleaned = super().clean()
        for name in self.Meta.fields:
            if cleaned.get(name) in (None, ''):
                cleaned[name] = Decimal('0')
        return cleaned

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
            'contractor_logistics', 'flights', 'lab_consumables',
        ]
        widgets = {field: forms.NumberInput(attrs={'class': 'form-control'})
                   for field in fields}

    def __init__(self, *args, **kwargs):
        # Optional baseline refresh — blank/zero means "keep the saved figures".
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.required = False

    def clean(self):
        cleaned = super().clean()
        for name in self.Meta.fields:
            if cleaned.get(name) in (None, ''):
                cleaned[name] = Decimal('0')
        return cleaned

    def has_any_value(self):
        """True if at least one category was given a non-zero figure."""
        return any(self.cleaned_data.get(name) for name in self.Meta.fields)
