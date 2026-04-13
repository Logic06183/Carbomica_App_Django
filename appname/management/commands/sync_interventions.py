"""
sync_interventions — seed / refresh the Intervention table from INTERVENTION_LIBRARY.

Creates missing interventions and updates existing ones if the display name matches.
Safe to run multiple times (idempotent).

Usage:
    python manage.py sync_interventions
"""
from django.core.management.base import BaseCommand
from django.db import transaction

from appname.models import Intervention
from appname.modeling import INTERVENTION_LIBRARY


# Default cost assumptions (USD) for each intervention type.
# Users can override these per-facility in Upload data → Facility interventions.
DEFAULT_COSTS = {
    'SOLAR_PV':             {'impl': 45000, 'maint': 1500, 'savings': 8000},
    'LOW_GWP_ANAESTHETICS': {'impl': 3500,  'maint': 500,  'savings': 6000},
    'LED_LIGHTING':         {'impl': 8000,  'maint': 200,  'savings': 2500},
    'WASTE_SEGREGATION':    {'impl': 2000,  'maint': 300,  'savings': 1200},
    'WATER_EFFICIENT_FIXTURES': {'impl': 3000, 'maint': 100, 'savings': 600},
    'HFC_REFRIGERANT_SWAP': {'impl': 5000,  'maint': 400,  'savings': 1800},
    'DPI_INHALER_SWITCH':   {'impl': 1000,  'maint': 0,    'savings': 3500},
    'FLEET_OPTIMISATION':   {'impl': 2500,  'maint': 300,  'savings': 1400},
}

# Emission reduction percentages per intervention (applied to the target category).
# These represent conservative LMIC estimates from HIGH Horizons D3.7.
REDUCTION_PCT = {
    'SOLAR_PV':             70,
    'LOW_GWP_ANAESTHETICS': 85,
    'LED_LIGHTING':         30,
    'WASTE_SEGREGATION':    60,
    'WATER_EFFICIENT_FIXTURES': 5,
    'HFC_REFRIGERANT_SWAP': 75,
    'DPI_INHALER_SWITCH':   70,
    'FLEET_OPTIMISATION':   25,
}


class Command(BaseCommand):
    help = 'Seed Intervention table from the CARBOMICA intervention library in modeling.py'

    def handle(self, *args, **options):
        created_count = 0
        updated_count = 0

        with transaction.atomic():
            for code, data in INTERVENTION_LIBRARY.items():
                costs = DEFAULT_COSTS.get(code, {})
                sdg_str = ','.join(str(g) for g in data.get('sdg_goals', []))

                target_cats = ','.join(data.get('reduces', {}).keys())

                obj, created = Intervention.objects.update_or_create(
                    code_name=code,
                    defaults={
                        'display_name':               data['display_name'],
                        'description':                data.get('notes', ''),
                        'sdg_goals':                  sdg_str,
                        'emission_reduction_percentage': REDUCTION_PCT.get(code, 0),
                        'energy_savings':             costs.get('savings', 0),
                        'status':                     'Planned',
                        'target_category':            target_cats,
                    },
                )
                if created:
                    created_count += 1
                    self.stdout.write(f'  Created: {data["display_name"]}')
                else:
                    updated_count += 1
                    self.stdout.write(f'  Updated: {data["display_name"]}')

        self.stdout.write(self.style.SUCCESS(
            f'\nDone — {created_count} created, {updated_count} updated.'
        ))
        self.stdout.write(
            'Next: go to Upload data → Facility interventions to attach these to a facility '
            'with site-specific costs.'
        )
