from django.db import models
from django.core.validators import MinValueValidator
from django.utils.translation import gettext_lazy as _

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

    class Meta:
        verbose_name = _('Intervention')
        verbose_name_plural = _('Interventions')
        ordering = ['display_name']

    def __str__(self):
        return self.display_name

class FacilityIntervention(models.Model):
    facility = models.ForeignKey(Facility, related_name='facility_interventions', on_delete=models.CASCADE)
    intervention = models.ForeignKey(Intervention, related_name='facility_interventions', on_delete=models.CASCADE)
    implementation_cost = models.DecimalField(default=0.0, max_digits=10, decimal_places=2, validators=[MinValueValidator(0.0)])
    maintenance_cost = models.DecimalField(default=0.0, max_digits=10, decimal_places=2, validators=[MinValueValidator(0.0)])

    class Meta:
        verbose_name = _('Facility Intervention')
        verbose_name_plural = _('Facility Interventions')
        ordering = ['facility__display_name']

    def __str__(self):
        return f"{self.facility.display_name} - {self.intervention.display_name}"

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
