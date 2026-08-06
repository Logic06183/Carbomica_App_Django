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


from .models import Organisation, OrganisationEmissionEntry, OffsetPurchase


@admin.register(Organisation)
class OrganisationAdmin(admin.ModelAdmin):
    list_display = ('name', 'country', 'created_by')
    list_filter = ('country',)
    search_fields = ('name',)


@admin.register(OrganisationEmissionEntry)
class OrganisationEmissionEntryAdmin(admin.ModelAdmin):
    list_display = ('organisation', 'year', 'category', 'quantity', 'created_by', 'created_at')
    list_filter = ('organisation', 'year', 'category')


@admin.register(OffsetPurchase)
class OffsetPurchaseAdmin(admin.ModelAdmin):
    list_display = ('organisation', 'year', 'credits_tco2e', 'provider', 'retired', 'purchase_date')
    list_filter = ('organisation', 'year', 'retired')


from .models import ReductionTarget


@admin.register(ReductionTarget)
class ReductionTargetAdmin(admin.ModelAdmin):
    list_display = ('organisation', 'baseline_year', 'target_year', 'reduction_pct', 'created_at')
    list_filter = ('organisation',)
