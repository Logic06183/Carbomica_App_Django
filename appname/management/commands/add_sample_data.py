from django.core.management.base import BaseCommand
from django.utils import timezone
from decimal import Decimal
from appname.models import (
    Facility,
    EmissionSource,
    EmissionData,
    Intervention,
    FacilityIntervention,
    Policy
)

class Command(BaseCommand):
    help = 'Adds sample data to the database'

    def handle(self, *args, **kwargs):
        # Create facilities
        facilities_data = [
            ('HOSP001', 'Central Hospital'),
            ('CLIN001', 'Primary Care Clinic'),
            ('LAB001', 'Medical Laboratory'),
            ('HOSP002', 'Regional Hospital'),
            ('CLIN002', 'Community Health Center')
        ]

        facilities = []
        for code, name in facilities_data:
            facility, created = Facility.objects.get_or_create(
                code_name=code,
                display_name=name
            )
            facilities.append(facility)
            if created:
                self.stdout.write(f'Created facility: {name}')

        # Create interventions
        interventions_data = [
            ('LED001', 'LED Lighting Upgrade', 'In Progress'),
            ('SOLAR001', 'Solar Panel Installation', 'Planned'),
            ('HVAC001', 'HVAC Optimization', 'Completed'),
            ('WASTE001', 'Waste Management Program', 'In Progress'),
            ('WATER001', 'Water Conservation System', 'Planned')
        ]

        interventions = []
        for code, name, status in interventions_data:
            intervention, created = Intervention.objects.get_or_create(
                code_name=code,
                display_name=name,
                defaults={'status': status}
            )
            interventions.append(intervention)
            if created:
                self.stdout.write(f'Created intervention: {name}')

        # Create emission sources and data for each facility
        for facility in facilities:
            source, created = EmissionSource.objects.get_or_create(
                facility=facility,
                code_name=f"{facility.code_name}_main",
                display_name=f"{facility.display_name} Main Source"
            )
            if created:
                self.stdout.write(f'Created emission source for: {facility.display_name}')

            # Create emission data with realistic values
            emission_data = EmissionData.objects.create(
                emission_source=source,
                date=timezone.now(),
                grid_electricity=Decimal(str(50000 + facility.id * 10000)),
                grid_gas=Decimal(str(20000 + facility.id * 5000)),
                bottled_gas=Decimal(str(10000 + facility.id * 2000)),
                liquid_fuel=Decimal(str(15000 + facility.id * 3000)),
                vehicle_fuel_owned=Decimal(str(8000 + facility.id * 1500)),
                business_travel=Decimal(str(5000 + facility.id * 1000)),
                anaesthetic_gases=Decimal(str(3000 + facility.id * 500)),
                refrigeration_gases=Decimal(str(2000 + facility.id * 400)),
                waste_management=Decimal(str(12000 + facility.id * 2500)),
                medical_inhalers=Decimal(str(1000 + facility.id * 200))
            )
            self.stdout.write(f'Created emission data for: {facility.display_name}')

            # Create facility interventions
            for intervention in interventions:
                facility_intervention, created = FacilityIntervention.objects.get_or_create(
                    facility=facility,
                    intervention=intervention,
                    defaults={
                        'implementation_cost': Decimal(str(50000 + facility.id * intervention.id * 1000)),
                        'maintenance_cost': Decimal(str(10000 + facility.id * intervention.id * 200))
                    }
                )
                if created:
                    self.stdout.write(f'Created facility intervention: {facility.display_name} - {intervention.display_name}')

        # Create policies
        policies_data = [
            ('Carbon Reduction Policy', 'Policy aimed at reducing carbon emissions across all facilities', 85),
            ('Waste Management Policy', 'Guidelines for proper medical waste disposal and recycling', 75),
            ('Energy Efficiency Policy', 'Standards for energy usage and conservation in healthcare facilities', 90),
            ('Sustainable Procurement', 'Guidelines for environmentally conscious purchasing decisions', 70),
            ('Green Building Policy', 'Standards for sustainable facility construction and renovation', 80)
        ]

        for name, desc, score in policies_data:
            policy, created = Policy.objects.get_or_create(
                name=name,
                defaults={
                    'description': desc,
                    'compliance_score': score,
                    'implementation_date': timezone.now(),
                    'status': 'Active'
                }
            )
            if created:
                self.stdout.write(f'Created policy: {name}')

        self.stdout.write(self.style.SUCCESS('Successfully added sample data'))
