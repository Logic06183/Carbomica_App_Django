from django.shortcuts import render, redirect
from .forms import FacilityForm, EmissionDataForm, FacilityInterventionFormSet

def add_facility(request):
    if request.method == 'POST':
        facility_form = FacilityForm(request.POST)
        if facility_form.is_valid():
            new_facility = facility_form.save()  # Save the facility to get the id for the emission data
            emission_form = EmissionDataForm(request.POST)
            if emission_form.is_valid():
                new_emission_data = emission_form.save(commit=False)
                new_emission_data.facility = new_facility
                new_emission_data.save()

                # If you want to save interventions at the same time
                intervention_formset = FacilityInterventionFormSet(request.POST, instance=new_facility)
                if intervention_formset.is_valid():
                    intervention_formset.save()

                return redirect('some_view_name')  # Redirect to a new URL:
            else:
                # If the emission form is not valid, delete the facility that was created
                new_facility.delete()
    else:
        facility_form = FacilityForm()
        emission_form = EmissionDataForm()
        intervention_formset = FacilityInterventionFormSet()

    return render(request, 'add_facility.html', {
        'facility_form': facility_form,
        'emission_form': emission_form,
        'intervention_formset': intervention_formset
    })


