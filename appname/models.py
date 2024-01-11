from django.db import models

class Facility(models.Model):
    code_name = models.CharField(max_length=100)
    display_name = models.CharField(max_length=100)
    # Other fields as necessary

class EmissionSource(models.Model):
    code_name = models.CharField(max_length=100)
    display_name = models.CharField(max_length=100)

class EmissionData(models.Model):
    facility = models.OneToOneField(Facility, on_delete=models.CASCADE)
    grid_electricity = models.FloatField(default=0.0)
    grid_gas = models.FloatField(default=0.0)
    bottled_gas = models.FloatField(default=0.0)
    liquid_fuel = models.FloatField(default=0.0)
    vehicle_fuel_owned = models.FloatField(default=0.0)
    business_travel = models.FloatField(default=0.0)
    anaesthetic_gases = models.FloatField(default=0.0)
    refrigeration_gases = models.FloatField(default=0.0)
    waste_management = models.FloatField(default=0.0)
    medical_inhalers = models.FloatField(default=0.0)


class Intervention(models.Model):
    code_name = models.CharField(max_length=100)
    display_name = models.CharField(max_length=100)

class FacilityIntervention(models.Model):
    facility = models.ForeignKey(Facility, on_delete=models.CASCADE)
    intervention = models.ForeignKey(Intervention, on_delete=models.CASCADE)
    implementation_cost = models.FloatField(default=0)
    maintenance_cost = models.FloatField(default=0)


class EffectSize(models.Model):
    facility = models.OneToOneField(Facility, on_delete=models.CASCADE)
    recycling_waste_segregation = models.FloatField()
    solar_system_installation = models.FloatField()
    # Add other fields as per your 'effect sizes' sheet

class ImplementationCost(models.Model):
    facility = models.OneToOneField(Facility, on_delete=models.CASCADE)
    recycling_waste_segregation = models.FloatField()
    solar_system_installation = models.FloatField()
    # Add other fields as per your 'implementation costs' sheet

class MaintenanceCost(models.Model):
    facility = models.OneToOneField(Facility, on_delete=models.CASCADE)
    recycling_waste_segregation = models.FloatField()
    solar_system_installation = models.FloatField()
    # Add other fields as per your 'maintenance costs' sheet

