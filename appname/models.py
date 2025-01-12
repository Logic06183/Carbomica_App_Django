from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils.translation import gettext_lazy as _
from django.utils import timezone

class Facility(models.Model):
    code_name = models.CharField(max_length=100)
    display_name = models.CharField(max_length=100)

    class Meta:
        verbose_name = _('Facility')
        verbose_name_plural = _('Facilities')
        ordering = ['display_name']

    def __str__(self):
        return self.display_name

class EmissionSource(models.Model):
    facility = models.ForeignKey(Facility, related_name='emission_sources', on_delete=models.CASCADE)
    code_name = models.CharField(max_length=100)
    display_name = models.CharField(max_length=100)

    class Meta:
        verbose_name = _('Emission Source')
        verbose_name_plural = _('Emission Sources')
        ordering = ['display_name']

    def __str__(self):
        return self.display_name

class EmissionData(models.Model):
    emission_source = models.ForeignKey(EmissionSource, related_name='emission_data', on_delete=models.CASCADE)
    date = models.DateField(default=timezone.now)
    grid_electricity = models.DecimalField(default=0.0, max_digits=10, decimal_places=2, validators=[MinValueValidator(0.0)])
    grid_gas = models.DecimalField(default=0.0, max_digits=10, decimal_places=2, validators=[MinValueValidator(0.0)])
    bottled_gas = models.DecimalField(default=0.0, max_digits=10, decimal_places=2, validators=[MinValueValidator(0.0)])
    liquid_fuel = models.DecimalField(default=0.0, max_digits=10, decimal_places=2, validators=[MinValueValidator(0.0)])
    vehicle_fuel_owned = models.DecimalField(default=0.0, max_digits=10, decimal_places=2, validators=[MinValueValidator(0.0)])
    business_travel = models.DecimalField(default=0.0, max_digits=10, decimal_places=2, validators=[MinValueValidator(0.0)])
    anaesthetic_gases = models.DecimalField(default=0.0, max_digits=10, decimal_places=2, validators=[MinValueValidator(0.0)])
    refrigeration_gases = models.DecimalField(default=0.0, max_digits=10, decimal_places=2, validators=[MinValueValidator(0.0)])
    waste_management = models.DecimalField(default=0.0, max_digits=10, decimal_places=2, validators=[MinValueValidator(0.0)])
    medical_inhalers = models.DecimalField(default=0.0, max_digits=10, decimal_places=2, validators=[MinValueValidator(0.0)])

    class Meta:
        verbose_name = _('Emission Data')
        verbose_name_plural = _('Emission Data Entries')
        ordering = ['-emission_source__display_name']

    def __str__(self):
        return f"{self.emission_source.display_name} Emission Data"

    def total_emissions(self):
        total = (
            self.grid_electricity + self.grid_gas + self.bottled_gas +
            self.liquid_fuel + self.vehicle_fuel_owned + self.business_travel +
            self.anaesthetic_gases + self.refrigeration_gases +
            self.waste_management + self.medical_inhalers
        )
        return total

class Intervention(models.Model):
    code_name = models.CharField(max_length=100)
    display_name = models.CharField(max_length=100)
    status = models.CharField(
        max_length=50,
        choices=[
            ('Planned', 'Planned'),
            ('In Progress', 'In Progress'),
            ('Completed', 'Completed'),
            ('Cancelled', 'Cancelled')
        ],
        default='Planned'
    )
    description = models.TextField(blank=True)
    emission_reduction_percentage = models.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        validators=[MinValueValidator(0.0), MaxValueValidator(100.0)],
        help_text="Expected percentage reduction in emissions",
        default=0.0
    )
    payback_period = models.IntegerField(
        validators=[MinValueValidator(0)],
        help_text="Expected payback period in months",
        default=0
    )
    energy_savings = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0.0)],
        help_text="Expected annual energy savings in kWh",
        default=0.0
    )

    class Meta:
        verbose_name = _('Intervention')
        verbose_name_plural = _('Interventions')
        ordering = ['display_name']

    def __str__(self):
        return self.display_name

class FacilityIntervention(models.Model):
    facility = models.ForeignKey(Facility, related_name='facility_interventions', on_delete=models.CASCADE)
    intervention = models.ForeignKey(Intervention, related_name='facility_interventions', on_delete=models.CASCADE)
    implementation_cost = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        validators=[MinValueValidator(0.0)]
    )
    maintenance_cost = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        validators=[MinValueValidator(0.0)]
    )
    annual_savings = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0.0)],
        default=0.0
    )
    emission_reduction_achieved = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0.0)],
        default=0.0,
        help_text="Actual emission reduction achieved in tCO2e"
    )
    implementation_date = models.DateField(null=True, blank=True)
    roi = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        validators=[MinValueValidator(0.0)],
        default=0.0,
        help_text="Return on Investment percentage"
    )

    class Meta:
        verbose_name = _('Facility Intervention')
        verbose_name_plural = _('Facility Interventions')
        ordering = ['facility__display_name']

    def calculate_roi(self):
        total_cost = self.implementation_cost + self.maintenance_cost
        if total_cost > 0:
            self.roi = (self.annual_savings / total_cost) * 100
        return self.roi

    def __str__(self):
        return f"{self.facility.display_name} - {self.intervention.display_name}"

class InterventionEffect(models.Model):
    intervention = models.ForeignKey(Intervention, related_name='effects', on_delete=models.CASCADE)
    facility = models.ForeignKey(Facility, related_name='intervention_effects', on_delete=models.CASCADE)
    effect_size = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0.0)])

    class Meta:
        verbose_name = _('Intervention Effect')
        verbose_name_plural = _('Intervention Effects')
        ordering = ['facility__display_name']

    def __str__(self):
        return f"{self.facility.display_name} - {self.intervention.display_name}"

class OptimizationScenario(models.Model):
    facility = models.ForeignKey(Facility, related_name='optimization_scenarios', on_delete=models.CASCADE)
    name = models.CharField(max_length=100)
    budget = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(0.0)])
    target_reduction = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        validators=[MinValueValidator(0.0), MaxValueValidator(100.0)],
        help_text="Target emission reduction percentage"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(
        max_length=50,
        choices=[
            ('Draft', 'Draft'),
            ('Optimized', 'Optimized'),
            ('Implemented', 'Implemented')
        ],
        default='Draft'
    )

    class Meta:
        verbose_name = _('Optimization Scenario')
        verbose_name_plural = _('Optimization Scenarios')
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.facility.display_name} - {self.name}"

class OptimizationResult(models.Model):
    scenario = models.ForeignKey(OptimizationScenario, related_name='results', on_delete=models.CASCADE)
    intervention = models.ForeignKey(Intervention, on_delete=models.CASCADE)
    priority = models.IntegerField(validators=[MinValueValidator(1)])
    expected_roi = models.DecimalField(max_digits=6, decimal_places=2)
    emission_reduction = models.DecimalField(max_digits=10, decimal_places=2)
    implementation_cost = models.DecimalField(max_digits=12, decimal_places=2)
    annual_savings = models.DecimalField(max_digits=12, decimal_places=2)
    payback_months = models.IntegerField()

    class Meta:
        verbose_name = _('Optimization Result')
        verbose_name_plural = _('Optimization Results')
        ordering = ['priority']

    def __str__(self):
        return f"{self.scenario.name} - {self.intervention.display_name}"

class EffectSize(models.Model):
    facility = models.ForeignKey(Facility, related_name='effect_sizes', on_delete=models.CASCADE)
    recycling_waste_segregation = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0.0)])
    solar_system_installation = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0.0)])
    # Add other fields as per your 'effect sizes' sheet

    class Meta:
        verbose_name = _('Effect Size')
        verbose_name_plural = _('Effect Sizes')
        ordering = ['facility__display_name']

class ImplementationCost(models.Model):
    facility = models.ForeignKey(Facility, related_name='implementation_costs', on_delete=models.CASCADE)
    recycling_waste_segregation = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0.0)])
    solar_system_installation = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0.0)])
    # Add other fields as per your 'implementation costs' sheet

    class Meta:
        verbose_name = _('Implementation Cost')
        verbose_name_plural = _('Implementation Costs')
        ordering = ['facility__display_name']

class MaintenanceCost(models.Model):
    facility = models.ForeignKey(Facility, related_name='maintenance_costs', on_delete=models.CASCADE)
    recycling_waste_segregation = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0.0)])
    solar_system_installation = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0.0)])
    # Add other fields as per your 'maintenance costs' sheet

    class Meta:
        verbose_name = _('Maintenance Cost')
        verbose_name_plural = _('Maintenance Costs')
        ordering = ['facility__display_name']

class Policy(models.Model):
    name = models.CharField(max_length=200)
    description = models.TextField()
    compliance_score = models.IntegerField(
        validators=[MinValueValidator(0)],
        default=0
    )
    implementation_date = models.DateField()
    status = models.CharField(
        max_length=50,
        choices=[
            ('Draft', 'Draft'),
            ('Active', 'Active'),
            ('Under Review', 'Under Review'),
            ('Archived', 'Archived')
        ],
        default='Draft'
    )

    class Meta:
        verbose_name = _('Policy')
        verbose_name_plural = _('Policies')
        ordering = ['name']

    def __str__(self):
        return self.name
