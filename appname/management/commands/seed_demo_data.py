"""
seed_demo_data — populate CARBOMICA with representative LMIC health facility data.

Data sources:
  - Emission baselines: HIGH Horizons D2.11 Carbon Emission Assessment Report
    (DOI: 10.5281/zenodo.12703876)
  - Intervention costs/savings: CARBOMICA D3.7 Mt Darwin and AKHS Mombasa case studies
    (DOI: 10.5281/zenodo.12730527)
  - SDG alignments: HIGH Horizons D5.7 Protocol for Mitigation Interventions Evaluation

Usage:
    python manage.py seed_demo_data
    python manage.py seed_demo_data --clear   # wipes existing data first
"""
from decimal import Decimal
from datetime import date

from django.core.management.base import BaseCommand
from django.db import transaction

from appname.models import (
    Facility, EmissionSource, EmissionData,
    Intervention, FacilityIntervention,
)


FACILITIES = [
    {
        'code_name': 'MTD_ZW',
        'display_name': 'Mt Darwin District Hospital',
        'country': 'ZW',
        'facility_type': 'district_hospital',
        'emission_source': 'Mt Darwin — Annual Baseline',
        # tCO2e per category (approximate, from D2.11 Zimbabwe data)
        'emissions': {
            'grid_electricity': Decimal('85.4'),
            'grid_gas': Decimal('0.0'),
            'bottled_gas': Decimal('12.3'),
            'liquid_fuel': Decimal('48.7'),
            'vehicle_fuel_owned': Decimal('18.2'),
            'business_travel': Decimal('5.1'),
            'anaesthetic_gases': Decimal('142.0'),
            'refrigeration_gases': Decimal('22.5'),
            'waste_management': Decimal('31.8'),
            'medical_inhalers': Decimal('8.4'),
        },
    },
    {
        'code_name': 'AKHS_KE',
        'display_name': 'Aga Khan Hospital Mombasa',
        'country': 'KE',
        'facility_type': 'provincial_hospital',
        'emission_source': 'AKHS Mombasa — Annual Baseline',
        'emissions': {
            'grid_electricity': Decimal('210.6'),
            'grid_gas': Decimal('0.0'),
            'bottled_gas': Decimal('28.9'),
            'liquid_fuel': Decimal('95.3'),
            'vehicle_fuel_owned': Decimal('31.4'),
            'business_travel': Decimal('12.7'),
            'anaesthetic_gases': Decimal('98.5'),
            'refrigeration_gases': Decimal('44.2'),
            'waste_management': Decimal('56.1'),
            'medical_inhalers': Decimal('14.8'),
        },
    },
    {
        'code_name': 'CHB_ZA',
        'display_name': 'Chris Hani Baragwanath Academic Hospital',
        'country': 'ZA',
        'facility_type': 'central_hospital',
        'emission_source': 'CHB — Annual Baseline',
        'emissions': {
            'grid_electricity': Decimal('1840.0'),
            'grid_gas': Decimal('0.0'),
            'bottled_gas': Decimal('85.0'),
            'liquid_fuel': Decimal('210.0'),
            'vehicle_fuel_owned': Decimal('72.0'),
            'business_travel': Decimal('28.0'),
            'anaesthetic_gases': Decimal('380.0'),
            'refrigeration_gases': Decimal('145.0'),
            'waste_management': Decimal('220.0'),
            'medical_inhalers': Decimal('62.0'),
        },
    },
    {
        'code_name': 'MASH_ZW',
        'display_name': 'Mashonaland Central Provincial Hospital',
        'country': 'ZW',
        'facility_type': 'provincial_hospital',
        'emission_source': 'Mashonaland — Annual Baseline',
        'emissions': {
            'grid_electricity': Decimal('132.0'),
            'grid_gas': Decimal('0.0'),
            'bottled_gas': Decimal('18.5'),
            'liquid_fuel': Decimal('74.2'),
            'vehicle_fuel_owned': Decimal('25.8'),
            'business_travel': Decimal('7.3'),
            'anaesthetic_gases': Decimal('218.0'),
            'refrigeration_gases': Decimal('35.0'),
            'waste_management': Decimal('48.5'),
            'medical_inhalers': Decimal('11.2'),
        },
    },
    {
        'code_name': 'SWH_ZA',
        'display_name': 'Soweto Community Health Centre',
        'country': 'ZA',
        'facility_type': 'health_centre',
        'emission_source': 'Soweto CHC — Annual Baseline',
        'emissions': {
            'grid_electricity': Decimal('95.0'),
            'grid_gas': Decimal('0.0'),
            'bottled_gas': Decimal('8.2'),
            'liquid_fuel': Decimal('22.0'),
            'vehicle_fuel_owned': Decimal('14.5'),
            'business_travel': Decimal('3.8'),
            'anaesthetic_gases': Decimal('18.0'),
            'refrigeration_gases': Decimal('12.0'),
            'waste_management': Decimal('28.0'),
            'medical_inhalers': Decimal('35.0'),
        },
    },
    {
        'code_name': 'KNH_KE',
        'display_name': 'Kenyatta National Hospital Nairobi',
        'country': 'KE',
        'facility_type': 'central_hospital',
        'emission_source': 'KNH — Annual Baseline',
        'emissions': {
            'grid_electricity': Decimal('980.0'),
            'grid_gas': Decimal('0.0'),
            'bottled_gas': Decimal('62.0'),
            'liquid_fuel': Decimal('185.0'),
            'vehicle_fuel_owned': Decimal('55.0'),
            'business_travel': Decimal('22.0'),
            'anaesthetic_gases': Decimal('275.0'),
            'refrigeration_gases': Decimal('88.0'),
            'waste_management': Decimal('142.0'),
            'medical_inhalers': Decimal('38.0'),
        },
    },
]

# CARBOMICA intervention library with realistic LMIC costs (USD)
# Costs derived from D3.7 case studies and regional procurement benchmarks.
INTERVENTIONS = [
    {
        'code_name': 'SOLAR_PV',
        'display_name': 'Solar PV System',
        'status': 'Planned',
        'description': (
            'Install rooftop solar PV to reduce grid dependency. '
            'Protects cold chains and critical equipment from load shedding. '
            'SDG 7 (Affordable Clean Energy), SDG 13 (Climate Action).'
        ),
        'emission_reduction_percentage': Decimal('14.5'),
        'payback_period': 60,
        'energy_savings': Decimal('85000'),
        'sdg_goals': '7,13',
    },
    {
        'code_name': 'LOW_GWP_ANAESTHETICS',
        'display_name': 'Low-GWP Anaesthetic Gases',
        'status': 'Planned',
        'description': (
            'Replace desflurane and sevoflurane with total intravenous anaesthesia (TIVA) '
            'or low-GWP alternatives. Highest impact-per-cost in most LMIC profiles. '
            'SDG 3 (Good Health), SDG 13 (Climate Action).'
        ),
        'emission_reduction_percentage': Decimal('18.2'),
        'payback_period': 18,
        'energy_savings': Decimal('0'),
        'sdg_goals': '3,13',
    },
    {
        'code_name': 'LED_LIGHTING',
        'display_name': 'LED Lighting Upgrade',
        'status': 'In Progress',
        'description': (
            'Retrofit fluorescent and incandescent fittings with LED throughout facility. '
            'SDG 7 (Affordable Clean Energy), SDG 11 (Sustainable Cities).'
        ),
        'emission_reduction_percentage': Decimal('6.8'),
        'payback_period': 24,
        'energy_savings': Decimal('32000'),
        'sdg_goals': '7,11',
    },
    {
        'code_name': 'WASTE_SEGREGATION',
        'display_name': 'Medical Waste Segregation & Management',
        'status': 'In Progress',
        'description': (
            'Separate hazardous from non-hazardous waste to reduce incineration volume '
            'and associated dioxin emissions. '
            'SDG 3 (Good Health), SDG 12 (Responsible Consumption).'
        ),
        'emission_reduction_percentage': Decimal('8.4'),
        'payback_period': 12,
        'energy_savings': Decimal('0'),
        'sdg_goals': '3,12',
    },
    {
        'code_name': 'WATER_EFFICIENT_FIXTURES',
        'display_name': 'Water-Efficient Fixtures',
        'status': 'Planned',
        'description': (
            'Low-flow taps, showers, and cisterns. '
            'Secondary benefit of reduced water-heating energy demand. '
            'SDG 6 (Clean Water), SDG 11 (Sustainable Cities).'
        ),
        'emission_reduction_percentage': Decimal('2.1'),
        'payback_period': 36,
        'energy_savings': Decimal('8500'),
        'sdg_goals': '6,11',
    },
    {
        'code_name': 'HFC_REFRIGERANT_SWAP',
        'display_name': 'Low-GWP Refrigerant Conversion',
        'status': 'Planned',
        'description': (
            'Replace HFC-134a and R-22 in cold-chain and HVAC equipment. '
            'Kigali Amendment compliance. SDG 13 (Climate Action).'
        ),
        'emission_reduction_percentage': Decimal('5.6'),
        'payback_period': 48,
        'energy_savings': Decimal('12000'),
        'sdg_goals': '13',
    },
    {
        'code_name': 'DPI_INHALER_SWITCH',
        'display_name': 'Switch to Dry-Powder Inhalers (DPI)',
        'status': 'Planned',
        'description': (
            'Pressurised MDIs contain HFC propellants with very high GWP (~1400x CO2). '
            'Switch to DPIs where clinically appropriate — WHO-endorsed. '
            'SDG 3 (Good Health), SDG 13 (Climate Action).'
        ),
        'emission_reduction_percentage': Decimal('3.2'),
        'payback_period': 12,
        'energy_savings': Decimal('0'),
        'sdg_goals': '3,13',
    },
    {
        'code_name': 'FLEET_OPTIMISATION',
        'display_name': 'Fleet & Travel Optimisation',
        'status': 'Planned',
        'description': (
            'Route optimisation, preventive vehicle maintenance schedules, '
            'and active travel policy for staff. '
            'SDG 11 (Sustainable Cities), SDG 13 (Climate Action).'
        ),
        'emission_reduction_percentage': Decimal('4.1'),
        'payback_period': 18,
        'energy_savings': Decimal('5000'),
        'sdg_goals': '11,13',
    },
]

# Per-facility intervention costs (USD) — scaled to facility size.
# Format: (facility_code, intervention_code, impl_cost, maint_cost, annual_savings, status)
FACILITY_INTERVENTIONS = [
    # Mt Darwin — small district hospital, ZW
    ('MTD_ZW', 'SOLAR_PV',               85000, 3500, 28000,  'Planned'),
    ('MTD_ZW', 'LOW_GWP_ANAESTHETICS',   12000,  800, 18500,  'Planned'),
    ('MTD_ZW', 'LED_LIGHTING',            8500,  200, 7200,   'In Progress'),
    ('MTD_ZW', 'WASTE_SEGREGATION',       6200,  400, 5800,   'In Progress'),
    ('MTD_ZW', 'DPI_INHALER_SWITCH',      1800,  100, 2200,   'Planned'),

    # AKHS Mombasa — provincial, KE
    ('AKHS_KE', 'SOLAR_PV',             180000, 6500, 68000,  'Planned'),
    ('AKHS_KE', 'LOW_GWP_ANAESTHETICS',  18000, 1200, 32000,  'Planned'),
    ('AKHS_KE', 'LED_LIGHTING',          22000,  500, 18500,  'Completed'),
    ('AKHS_KE', 'WASTE_SEGREGATION',     14000,  800, 12000,  'In Progress'),
    ('AKHS_KE', 'HFC_REFRIGERANT_SWAP',  42000, 1800, 15000,  'Planned'),
    ('AKHS_KE', 'WATER_EFFICIENT_FIXTURES', 8500, 250, 4200,  'Planned'),

    # CHB — large central hospital, ZA
    ('CHB_ZA', 'SOLAR_PV',             950000, 28000, 380000, 'In Progress'),
    ('CHB_ZA', 'LOW_GWP_ANAESTHETICS',  95000,  4500, 145000, 'Planned'),
    ('CHB_ZA', 'LED_LIGHTING',          85000,  2200, 72000,  'Completed'),
    ('CHB_ZA', 'WASTE_SEGREGATION',     48000,  2500, 42000,  'In Progress'),
    ('CHB_ZA', 'HFC_REFRIGERANT_SWAP', 185000,  7500, 62000,  'Planned'),
    ('CHB_ZA', 'DPI_INHALER_SWITCH',    22000,   800, 18000,  'Planned'),
    ('CHB_ZA', 'FLEET_OPTIMISATION',    35000,  1500, 28000,  'Planned'),

    # Mashonaland — provincial, ZW
    ('MASH_ZW', 'SOLAR_PV',            125000,  4800, 42000,  'Planned'),
    ('MASH_ZW', 'LOW_GWP_ANAESTHETICS', 22000,  1100, 32000,  'Planned'),
    ('MASH_ZW', 'WASTE_SEGREGATION',    9500,    500,  8200,  'Planned'),
    ('MASH_ZW', 'LED_LIGHTING',         14000,   380, 11500,  'Planned'),

    # Soweto CHC — health centre, ZA
    ('SWH_ZA', 'LED_LIGHTING',          12000,   300,  9800,  'Completed'),
    ('SWH_ZA', 'DPI_INHALER_SWITCH',     4500,   180,  5200,  'In Progress'),
    ('SWH_ZA', 'WASTE_SEGREGATION',      7800,   400,  6500,  'In Progress'),
    ('SWH_ZA', 'WATER_EFFICIENT_FIXTURES', 5200, 150,  2800,  'Planned'),

    # KNH — central hospital, KE
    ('KNH_KE', 'SOLAR_PV',             620000, 18500, 245000, 'Planned'),
    ('KNH_KE', 'LOW_GWP_ANAESTHETICS',  58000,  2800,  92000, 'Planned'),
    ('KNH_KE', 'LED_LIGHTING',          55000,  1400,  46000, 'In Progress'),
    ('KNH_KE', 'WASTE_SEGREGATION',     32000,  1600,  28000, 'In Progress'),
    ('KNH_KE', 'HFC_REFRIGERANT_SWAP',  98000,  4200,  38000, 'Planned'),
    ('KNH_KE', 'FLEET_OPTIMISATION',    22000,   900,  18000, 'Planned'),
]


class Command(BaseCommand):
    help = 'Seed CARBOMICA with representative LMIC health facility demo data.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Delete all existing facilities, interventions, and emission data first.',
        )

    @transaction.atomic
    def handle(self, *args, **options):
        if options['clear']:
            FacilityIntervention.objects.all().delete()
            EmissionData.objects.all().delete()
            EmissionSource.objects.all().delete()
            Facility.objects.all().delete()
            Intervention.objects.all().delete()
            self.stdout.write(self.style.WARNING('Cleared existing data.'))

        # Interventions
        intervention_map = {}
        for data in INTERVENTIONS:
            obj, created = Intervention.objects.update_or_create(
                code_name=data['code_name'],
                defaults={
                    'display_name': data['display_name'],
                    'status': data['status'],
                    'description': data['description'],
                    'emission_reduction_percentage': data['emission_reduction_percentage'],
                    'payback_period': data['payback_period'],
                    'energy_savings': data['energy_savings'],
                    'sdg_goals': data['sdg_goals'],
                },
            )
            intervention_map[data['code_name']] = obj
            verb = 'Created' if created else 'Updated'
            self.stdout.write(f'  {verb} intervention: {obj.display_name}')

        # Facilities + emissions
        facility_map = {}
        for fdata in FACILITIES:
            facility, _ = Facility.objects.update_or_create(
                code_name=fdata['code_name'],
                defaults={
                    'display_name': fdata['display_name'],
                    'country': fdata['country'],
                    'facility_type': fdata['facility_type'],
                },
            )
            facility_map[fdata['code_name']] = facility

            source, _ = EmissionSource.objects.get_or_create(
                facility=facility,
                code_name=f"{fdata['code_name']}_BASELINE",
                defaults={'display_name': fdata['emission_source']},
            )

            # One annual emission record per facility
            EmissionData.objects.update_or_create(
                emission_source=source,
                date=date(2023, 12, 31),
                defaults=fdata['emissions'],
            )
            self.stdout.write(f'  Seeded facility: {facility.display_name} ({facility.country})')

        # Facility interventions
        for (fcode, icode, impl, maint, savings, status) in FACILITY_INTERVENTIONS:
            facility = facility_map.get(fcode)
            intervention = intervention_map.get(icode)
            if not facility or not intervention:
                self.stdout.write(self.style.WARNING(f'  Skipped {fcode}/{icode}'))
                continue

            intervention.status = status
            intervention.save(update_fields=['status'])

            fi, created = FacilityIntervention.objects.update_or_create(
                facility=facility,
                intervention=intervention,
                defaults={
                    'implementation_cost': Decimal(str(impl)),
                    'maintenance_cost': Decimal(str(maint)),
                    'annual_savings': Decimal(str(savings)),
                    'roi': Decimal('0'),
                },
            )
            fi.roi = fi.calculate_roi()
            fi.save(update_fields=['roi'])

        self.stdout.write(self.style.SUCCESS(
            f'\nDone. Seeded {len(FACILITIES)} facilities, '
            f'{len(INTERVENTIONS)} interventions, '
            f'{len(FACILITY_INTERVENTIONS)} facility-intervention records.'
        ))
