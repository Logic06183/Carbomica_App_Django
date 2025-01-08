from django.core.management.base import BaseCommand
from appname.models import (
    Facility, 
    EmissionSource, 
    EmissionData, 
    Intervention, 
    FacilityIntervention
)
from decimal import Decimal

class Command(BaseCommand):
    help = 'Adds dummy data for testing'

    def handle(self, *args, **kwargs):
        # Create test facilities
        facilities = [
            {
                'code_name': 'HOSP001',
                'display_name': 'Central Hospital',
                'emissions': {
                    'grid_electricity': 500000,  # kWh
                    'grid_gas': 25000,          # m³
                    'bottled_gas': 1000,        # kg
                    'liquid_fuel': 5000,        # L
                    'vehicle_fuel_owned': 8000,  # L
                    'business_travel': 50000,    # km
                    'anaesthetic_gases': 100,    # kg
                    'refrigeration_gases': 200,  # kg
                    'waste_management': 15000,   # kg
                    'medical_inhalers': 5000     # units
                }
            },
            {
                'code_name': 'CLINIC001',
                'display_name': 'Community Clinic',
                'emissions': {
                    'grid_electricity': 150000,  # kWh
                    'grid_gas': 8000,           # m³
                    'bottled_gas': 300,         # kg
                    'liquid_fuel': 1500,        # L
                    'vehicle_fuel_owned': 2000,  # L
                    'business_travel': 15000,    # km
                    'anaesthetic_gases': 20,     # kg
                    'refrigeration_gases': 50,   # kg
                    'waste_management': 5000,    # kg
                    'medical_inhalers': 2000     # units
                }
            }
        ]

        # Create or get interventions
        solar_intervention, _ = Intervention.objects.get_or_create(
            code_name='SOLAR',
            display_name='Solar System Installation'
        )
        waste_intervention, _ = Intervention.objects.get_or_create(
            code_name='WASTE',
            display_name='Recycling and Waste Segregation'
        )

        # Add facilities with their emissions and interventions
        for facility_data in facilities:
            # Create facility
            facility = Facility.objects.create(
                code_name=facility_data['code_name'],
                display_name=facility_data['display_name']
            )

            # Create emission source
            emission_source = EmissionSource.objects.create(
                facility=facility,
                code_name=f"{facility.code_name}_main",
                display_name=f"{facility.display_name} Main Source"
            )

            # Create emission data
            EmissionData.objects.create(
                emission_source=emission_source,
                **{k: Decimal(str(v)) for k, v in facility_data['emissions'].items()}
            )

            # Add interventions
            FacilityIntervention.objects.create(
                facility=facility,
                intervention=solar_intervention,
                implementation_cost=Decimal('500000.00'),
                maintenance_cost=Decimal('25000.00')
            )

            FacilityIntervention.objects.create(
                facility=facility,
                intervention=waste_intervention,
                implementation_cost=Decimal('100000.00'),
                maintenance_cost=Decimal('10000.00')
            )

        self.stdout.write(self.style.SUCCESS('Successfully added dummy data'))
