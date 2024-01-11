from django.contrib import admin
from .models import Facility, EmissionSource, EmissionData, Intervention, FacilityIntervention, EffectSize, ImplementationCost, MaintenanceCost

# Registering each model to the admin site
admin.site.register(Facility)
admin.site.register(EmissionSource)
admin.site.register(EmissionData)
admin.site.register(Intervention)
admin.site.register(FacilityIntervention)
admin.site.register(EffectSize)
admin.site.register(ImplementationCost)
admin.site.register(MaintenanceCost)

