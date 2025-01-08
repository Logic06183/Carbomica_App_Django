from django.contrib import admin
from .models import (
    Facility, 
    EmissionSource, 
    EmissionData, 
    Intervention, 
    FacilityIntervention,
    EffectSize,
    ImplementationCost,
    MaintenanceCost
)

@admin.register(Facility)
class FacilityAdmin(admin.ModelAdmin):
    list_display = ('display_name', 'code_name')
    search_fields = ('display_name', 'code_name')

@admin.register(EmissionSource)
class EmissionSourceAdmin(admin.ModelAdmin):
    list_display = ('display_name', 'facility')
    list_filter = ('facility',)
    search_fields = ('display_name', 'code_name')

@admin.register(EmissionData)
class EmissionDataAdmin(admin.ModelAdmin):
    list_display = ('emission_source', 'total_emissions')
    list_filter = ('emission_source__facility',)

@admin.register(Intervention)
class InterventionAdmin(admin.ModelAdmin):
    list_display = ('display_name', 'code_name')
    search_fields = ('display_name', 'code_name')

@admin.register(FacilityIntervention)
class FacilityInterventionAdmin(admin.ModelAdmin):
    list_display = ('facility', 'intervention', 'implementation_cost', 'maintenance_cost')
    list_filter = ('facility', 'intervention')

@admin.register(EffectSize)
class EffectSizeAdmin(admin.ModelAdmin):
    list_display = ('facility', 'recycling_waste_segregation', 'solar_system_installation')
    list_filter = ('facility',)

@admin.register(ImplementationCost)
class ImplementationCostAdmin(admin.ModelAdmin):
    list_display = ('facility', 'recycling_waste_segregation', 'solar_system_installation')
    list_filter = ('facility',)

@admin.register(MaintenanceCost)
class MaintenanceCostAdmin(admin.ModelAdmin):
    list_display = ('facility', 'recycling_waste_segregation', 'solar_system_installation')
    list_filter = ('facility',)
