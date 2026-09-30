"""
seed_demo_data — populate the database with representative LMIC health facility data.

Data sources:
  - Emission baselines: HIGH Horizons D2.11 Carbon Emission Assessment Report
    (DOI: 10.5281/zenodo.12703876)
  - Intervention costs/savings: HIGH Horizons D3.7 Mt Darwin and AKHS Mombasa case studies
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

from django.contrib.auth.models import User

from appname.models import (
    Facility, EmissionSource, EmissionData,
    Intervention, FacilityIntervention, Organisation,
)
from appname.middleware import DEMO_USERNAME, DEMO_EMAIL


# ---------------------------------------------------------------------------
# Facility baselines.
#
# IMPORTANT — units. Every value below is *activity data* in the physical unit
# the model expects (kWh, m³, kg, litres, km, tonnes, units, passenger-km, USD),
# NOT tCO₂e. modeling.compute_tco2e() applies the published conversion factors.
#
# The clinical figures published in HIGH Horizons D2.11 are stated as tCO₂e, so
# the activity data here is back-calculated by inverting the documented factor
# for each category (activity = published tCO₂e ÷ factor). That preserves the
# published baseline exactly while storing the data in the model's native units.
# The resulting values are physically sensible (e.g. Baragwanath ≈ 2.0 GWh/yr).
# ---------------------------------------------------------------------------
FACILITIES = [
    {
        'code_name': 'MTD_ZW',
        'display_name': 'Mt Darwin District Hospital',
        'country': 'ZW',
        'sector': 'clinical',
        'facility_type': 'district_hospital',
        'organisation': None,
        'emission_source': 'Mt Darwin — Annual Baseline',
        'emissions': {
            'grid_electricity': Decimal('153597'),    # kWh      → 85.4 tCO₂e
            'grid_gas': Decimal('0'),                 # m³
            'bottled_gas': Decimal('4184'),           # kg LPG   → 12.3
            'liquid_fuel': Decimal('18172'),          # litres   → 48.7
            'vehicle_fuel_owned': Decimal('6791'),    # litres   → 18.2
            'business_travel': Decimal('29825'),      # km       → 5.1
            'anaesthetic_gases': Decimal('177'),      # kg agent → 142.0
            'refrigeration_gases': Decimal('12.5'),   # kg       → 22.5
            'waste_management': Decimal('29.6'),      # tonnes   → 31.8
            'medical_inhalers': Decimal('444'),       # pMDI     → 8.4
            'contractor_logistics': Decimal('19800'), # km
        },
    },
    {
        'code_name': 'AKHS_KE',
        'display_name': 'Aga Khan Hospital Mombasa',
        'country': 'KE',
        'sector': 'clinical',
        'facility_type': 'provincial_hospital',
        'organisation': None,
        'emission_source': 'AKHS Mombasa — Annual Baseline',
        'emissions': {
            'grid_electricity': Decimal('6581250'),   # kWh      → 210.6 tCO₂e
            'grid_gas': Decimal('0'),
            'bottled_gas': Decimal('9830'),           # → 28.9
            'liquid_fuel': Decimal('35560'),          # → 95.3
            'vehicle_fuel_owned': Decimal('11716'),   # → 31.4
            'business_travel': Decimal('74269'),      # → 12.7
            'anaesthetic_gases': Decimal('123'),      # → 98.5
            'refrigeration_gases': Decimal('24.6'),   # → 44.2
            'waste_management': Decimal('52.2'),      # → 56.1
            'medical_inhalers': Decimal('783'),       # → 14.8
            'contractor_logistics': Decimal('41200'),
        },
    },
    {
        'code_name': 'CHB_ZA',
        'display_name': 'Chris Hani Baragwanath Academic Hospital',
        'country': 'ZA',
        'sector': 'clinical',
        'facility_type': 'central_hospital',
        'organisation': None,
        'emission_source': 'CHB — Annual Baseline',
        'emissions': {
            'grid_electricity': Decimal('1982759'),   # kWh      → 1840.0 tCO₂e
            'grid_gas': Decimal('0'),
            'bottled_gas': Decimal('28912'),          # → 85.0
            'liquid_fuel': Decimal('78358'),          # → 210.0
            'vehicle_fuel_owned': Decimal('26866'),   # → 72.0
            'business_travel': Decimal('163743'),     # → 28.0
            'anaesthetic_gases': Decimal('474'),      # → 380.0
            'refrigeration_gases': Decimal('80.6'),   # → 145.0
            'waste_management': Decimal('205'),       # → 220.0
            'medical_inhalers': Decimal('3280'),      # → 62.0
            'contractor_logistics': Decimal('128000'),
        },
    },
    {
        'code_name': 'MASH_ZW',
        'display_name': 'Mashonaland Central Provincial Hospital',
        'country': 'ZW',
        'sector': 'clinical',
        'facility_type': 'provincial_hospital',
        'organisation': None,
        'emission_source': 'Mashonaland — Annual Baseline',
        'emissions': {
            'grid_electricity': Decimal('237410'),    # → 132.0 tCO₂e
            'grid_gas': Decimal('0'),
            'bottled_gas': Decimal('6293'),           # → 18.5
            'liquid_fuel': Decimal('27687'),          # → 74.2
            'vehicle_fuel_owned': Decimal('9627'),    # → 25.8
            'business_travel': Decimal('42690'),      # → 7.3
            'anaesthetic_gases': Decimal('272'),      # → 218.0
            'refrigeration_gases': Decimal('19.4'),   # → 35.0
            'waste_management': Decimal('45.2'),      # → 48.5
            'medical_inhalers': Decimal('593'),       # → 11.2
            'contractor_logistics': Decimal('26400'),
        },
    },
    {
        'code_name': 'SWH_ZA',
        'display_name': 'Soweto Community Health Centre',
        'country': 'ZA',
        'sector': 'clinical',
        'facility_type': 'health_centre',
        'organisation': None,
        'emission_source': 'Soweto CHC — Annual Baseline',
        'emissions': {
            'grid_electricity': Decimal('102371'),    # → 95.0 tCO₂e
            'grid_gas': Decimal('0'),
            'bottled_gas': Decimal('2789'),           # → 8.2
            'liquid_fuel': Decimal('8209'),           # → 22.0
            'vehicle_fuel_owned': Decimal('5410'),    # → 14.5
            'business_travel': Decimal('22222'),      # → 3.8
            'anaesthetic_gases': Decimal('22.4'),     # → 18.0
            'refrigeration_gases': Decimal('6.7'),    # → 12.0
            'waste_management': Decimal('26.1'),      # → 28.0
            'medical_inhalers': Decimal('1852'),      # → 35.0
            'contractor_logistics': Decimal('14500'),
        },
    },
    {
        'code_name': 'KNH_KE',
        'display_name': 'Kenyatta National Hospital Nairobi',
        'country': 'KE',
        'sector': 'clinical',
        'facility_type': 'central_hospital',
        'organisation': None,
        'emission_source': 'KNH — Annual Baseline',
        'emissions': {
            'grid_electricity': Decimal('30625000'),  # → 980.0 tCO₂e
            'grid_gas': Decimal('0'),
            'bottled_gas': Decimal('21088'),          # → 62.0
            'liquid_fuel': Decimal('69030'),          # → 185.0
            'vehicle_fuel_owned': Decimal('20522'),   # → 55.0
            'business_travel': Decimal('128655'),     # → 22.0
            'anaesthetic_gases': Decimal('343'),      # → 275.0
            'refrigeration_gases': Decimal('48.9'),   # → 88.0
            'waste_management': Decimal('132'),       # → 142.0
            'medical_inhalers': Decimal('2011'),      # → 38.0
            'contractor_logistics': Decimal('96000'),
        },
    },

    # ── Research sector — Wits Health Consortium demonstration group ─────────
    # Activity data representative of a South African health-research group of
    # this size. Figures are illustrative planning defaults, not audited
    # returns: electricity from floor area × SANS 204 office/lab intensities,
    # generator diesel sized for Eskom load-shedding, procurement spend from
    # typical grant consumables budgets, flights from conference/fieldwork
    # travel patterns. Every value is site-overridable in the app.
    {
        'code_name': 'WHC_PHRU',
        'display_name': 'Wits Planetary Health Research Division',
        'country': 'ZA',
        'sector': 'research',
        'facility_type': 'research_office',
        'organisation': 'Wits Health Consortium',
        'emission_source': 'Planetary Health — 2024 Annual Baseline',
        'emissions': {
            'grid_electricity': Decimal('420000'),    # kWh (≈3,000 m² @ 140 kWh/m²)
            'grid_gas': Decimal('0'),
            'bottled_gas': Decimal('1200'),           # kg
            'liquid_fuel': Decimal('14000'),          # L standby generator
            'vehicle_fuel_owned': Decimal('9000'),    # L fieldwork fleet
            'business_travel': Decimal('120000'),     # km staff vehicles
            'anaesthetic_gases': Decimal('0'),
            'refrigeration_gases': Decimal('45'),     # kg HVAC + cold chain
            'waste_management': Decimal('18'),        # tonnes (landfill route)
            'medical_inhalers': Decimal('0'),
            'contractor_logistics': Decimal('35000'), # km
            'flights': Decimal('950000'),             # passenger-km
            'lab_consumables': Decimal('850000'),     # USD procurement spend
        },
    },
    {
        'code_name': 'WHC_IMMUNO',
        'display_name': 'WHC Immunology & Vaccinology Laboratory',
        'country': 'ZA',
        'sector': 'research',
        'facility_type': 'university_lab',
        'organisation': 'Wits Health Consortium',
        'emission_source': 'Immunology Lab — 2024 Annual Baseline',
        'emissions': {
            'grid_electricity': Decimal('310000'),    # kWh (ULT freezer bank + HVAC)
            'grid_gas': Decimal('0'),
            'bottled_gas': Decimal('4500'),           # kg lab gases
            'liquid_fuel': Decimal('9000'),           # L generator (sample protection)
            'vehicle_fuel_owned': Decimal('2400'),
            'business_travel': Decimal('40000'),
            'anaesthetic_gases': Decimal('0'),
            'refrigeration_gases': Decimal('70'),     # kg — freezer/cold-room heavy
            'waste_management': Decimal('26'),        # tonnes
            'medical_inhalers': Decimal('0'),
            'contractor_logistics': Decimal('22000'),
            'flights': Decimal('280000'),             # passenger-km
            'lab_consumables': Decimal('1400000'),    # USD — reagent-intensive
        },
    },
    {
        'code_name': 'WHC_SPH',
        'display_name': 'Wits School of Public Health',
        'country': 'ZA',
        'sector': 'research',
        'facility_type': 'university_dept',
        'organisation': 'Wits Health Consortium',
        'emission_source': 'School of Public Health — 2024 Annual Baseline',
        'emissions': {
            'grid_electricity': Decimal('560000'),    # kWh
            'grid_gas': Decimal('0'),
            'bottled_gas': Decimal('900'),
            'liquid_fuel': Decimal('18000'),          # L generator
            'vehicle_fuel_owned': Decimal('11000'),   # L fieldwork fleet
            'business_travel': Decimal('180000'),     # km
            'anaesthetic_gases': Decimal('0'),
            'refrigeration_gases': Decimal('30'),
            'waste_management': Decimal('34'),        # tonnes
            'medical_inhalers': Decimal('0'),
            'contractor_logistics': Decimal('48000'),
            'flights': Decimal('1400000'),            # passenger-km — global health travel
            'lab_consumables': Decimal('420000'),     # USD
        },
    },
]

# Intervention library with realistic LMIC costs (USD)
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
    help = 'Seed the database with representative LMIC health facility demo data.'

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
        # Demo owner. Facilities are only visible to a user who either created
        # them or shares an organisation with them (see views._visible_facilities),
        # so seeded data MUST be owned by the account visitors land on. In
        # DEMO_MODE the middleware auto-logs everyone in as `demo_guest`.
        demo_user, _ = User.objects.get_or_create(
            username=DEMO_USERNAME,
            defaults={'email': DEMO_EMAIL, 'first_name': 'Demo', 'last_name': 'Guest'},
        )

        # Organisations referenced by facilities (demo groups like Wits Health
        # Consortium). Created before facilities so the FK is available.
        org_map = {}
        for org_name in dict.fromkeys(
            f['organisation'] for f in FACILITIES if f.get('organisation')
        ):
            org, created = Organisation.objects.get_or_create(
                name=org_name, defaults={'created_by': demo_user},
            )
            org.members.add(demo_user)
            org_map[org_name] = org
            self.stdout.write(
                f"  {'Created' if created else 'Found'} organisation: {org.name}"
            )

        for fdata in FACILITIES:
            facility, _ = Facility.objects.update_or_create(
                code_name=fdata['code_name'],
                defaults={
                    'display_name': fdata['display_name'],
                    'country': fdata['country'],
                    'facility_type': fdata['facility_type'],
                    'sector': fdata['sector'],
                    'organisation': org_map.get(fdata.get('organisation')),
                    'created_by': demo_user,
                },
            )
            facility_map[fdata['code_name']] = facility

            source, _ = EmissionSource.objects.get_or_create(
                facility=facility,
                code_name=f"{fdata['code_name']}_BASELINE",
                defaults={'display_name': fdata['emission_source']},
            )

            # One annual emission record per facility. Research baselines are
            # dated to the 2024 reporting year; the clinical case-study figures
            # remain on their published 2023 baseline.
            period_end = date(2024, 12, 31) if fdata['sector'] == 'research' else date(2023, 12, 31)
            EmissionData.objects.update_or_create(
                emission_source=source,
                date=period_end,
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
