from django.contrib import admin
from .models import (
    Facility,
    EmissionSource,
    EmissionData,
    Intervention,
    FacilityIntervention,
    OptimizationScenario,
    OptimizationResult,
    Policy,
)


@admin.register(Facility)
class FacilityAdmin(admin.ModelAdmin):
    list_display = ('display_name', 'code_name', 'country', 'facility_type')
    list_filter = ('country', 'facility_type')
    search_fields = ('display_name', 'code_name')


@admin.register(EmissionSource)
class EmissionSourceAdmin(admin.ModelAdmin):
    list_display = ('display_name', 'facility')
    list_filter = ('facility',)
    search_fields = ('display_name', 'code_name')


@admin.register(EmissionData)
class EmissionDataAdmin(admin.ModelAdmin):
    list_display = ('emission_source', 'date', 'total_emissions')
    list_filter = ('emission_source__facility', 'date')
    ordering = ('-date',)


@admin.register(Intervention)
class InterventionAdmin(admin.ModelAdmin):
    list_display = ('display_name', 'code_name', 'status', 'emission_reduction_percentage', 'sdg_goals')
    list_filter = ('status',)
    search_fields = ('display_name', 'code_name')


@admin.register(FacilityIntervention)
class FacilityInterventionAdmin(admin.ModelAdmin):
    list_display = ('facility', 'intervention', 'implementation_cost', 'annual_savings', 'roi')
    list_filter = ('facility', 'intervention__status')
    search_fields = ('facility__display_name', 'intervention__display_name')


@admin.register(OptimizationScenario)
class OptimizationScenarioAdmin(admin.ModelAdmin):
    list_display = ('name', 'facility', 'budget', 'target_reduction', 'status', 'created_at')
    list_filter = ('status', 'facility')
    ordering = ('-created_at',)


@admin.register(OptimizationResult)
class OptimizationResultAdmin(admin.ModelAdmin):
    list_display = ('scenario', 'intervention', 'priority', 'emission_reduction', 'expected_roi')
    list_filter = ('scenario',)
    ordering = ('scenario', 'priority')


@admin.register(Policy)
class PolicyAdmin(admin.ModelAdmin):
    list_display = ('name', 'status', 'implementation_date', 'compliance_score')
    list_filter = ('status',)
