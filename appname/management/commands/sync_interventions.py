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
# Sources: CARBOMICA D3.7 Carbon Saving Calculator + Cost Saving Calculator.
# impl = unit CapEx (USD), maint = annual maintenance (USD), savings = annual cost saving (USD).
DEFAULT_COSTS = {
    # ── Legacy / generic entries ──────────────────────────────────────────────
    'SOLAR_PV':             {'impl': 45000, 'maint': 1500,  'savings': 8000},
    'LOW_GWP_ANAESTHETICS': {'impl': 3500,  'maint': 500,   'savings': 6000},
    'LED_LIGHTING':         {'impl': 8000,  'maint': 200,   'savings': 2500},
    'WASTE_SEGREGATION':    {'impl': 2000,  'maint': 300,   'savings': 1200},
    'WATER_EFFICIENT_FIXTURES': {'impl': 3000, 'maint': 100, 'savings': 600},
    'HFC_REFRIGERANT_SWAP': {'impl': 5000,  'maint': 400,   'savings': 1800},
    'DPI_INHALER_SWITCH':   {'impl': 1000,  'maint': 0,     'savings': 3500},
    'FLEET_OPTIMISATION':   {'impl': 2500,  'maint': 300,   'savings': 1400},

    # ── 1. LED Lights ─────────────────────────────────────────────────────────
    'LED_WATT_5':           {'impl': 600,   'maint': 18,    'savings': 920},    # 100 lamps
    'LED_WATT_10':          {'impl': 40,    'maint': 1,     'savings': 184},    # 20 lamps
    'LED_WATT_20':          {'impl': 160,   'maint': 5,     'savings': 368},    # 20 lamps
    'LED_WATT_50':          {'impl': 160,   'maint': 5,     'savings': 920},    # 20 lamps
    'LED_WATT_95':          {'impl': 200,   'maint': 6,     'savings': 1748},   # 20 lamps

    # ── 2. Solar Systems ──────────────────────────────────────────────────────
    'SOLAR_3KVA':           {'impl': 2500,  'maint': 1875,  'savings': 1555},
    'SOLAR_5KVA':           {'impl': 4000,  'maint': 3000,  'savings': 2136},
    'SOLAR_10KVA':          {'impl': 11000, 'maint': 8250,  'savings': 3362},
    'SOLAR_100KWP':         {'impl': 80000, 'maint': 60000, 'savings': 30917},
    'SOLAR_150KWP':         {'impl': 153000,'maint': 114750,'savings': 43716},
    'SOLAR_600KWP':         {'impl': 612000,'maint': 459000,'savings': 172690},

    # ── 3. Biogas Digestors ───────────────────────────────────────────────────
    'BIOGAS_6M3':           {'impl': 2000,  'maint': 300,   'savings': 526},
    'BIOGAS_20M3':          {'impl': 5000,  'maint': 750,   'savings': 2316},

    # ── 4. Low-GWP Refrigerants ───────────────────────────────────────────────
    # (no CapEx — cost is refrigerant purchase price delta; savings can be negative)
    'REFRIG_R134A_R1234YF': {'impl': 0,     'maint': 0,     'savings': -300},   # HFO premium
    'REFRIG_R134A_R1234ZE': {'impl': 0,     'maint': 0,     'savings': 400},
    'REFRIG_R410A_R1234ZE': {'impl': 0,     'maint': 0,     'savings': -200},
    'REFRIG_R410A_R32':     {'impl': 0,     'maint': 0,     'savings': 700},
    'REFRIG_R404A_R448A':   {'impl': 0,     'maint': 0,     'savings': 300},
    'REFRIG_R22_R290':      {'impl': 0,     'maint': 0,     'savings': 5250},
    'REFRIG_R32_R744':      {'impl': 0,     'maint': 0,     'savings': -600},
    'REFRIG_R403A_R407A':   {'impl': 0,     'maint': 0,     'savings': 700},

    # ── 5. Anaesthetic Gases ──────────────────────────────────────────────────
    'ANAES_ISO_SEVO':       {'impl': 0,     'maint': 0,     'savings': -400},   # sevo costs more
    'ANAES_NO_AVOID':       {'impl': 0,     'maint': 0,     'savings': 200},

    # ── 6 & 7. Inhalers ───────────────────────────────────────────────────────
    'INHALER_DPI':          {'impl': 0,     'maint': 0,     'savings': -500},   # DPI costs more
    'INHALER_SMI':          {'impl': 0,     'maint': 0,     'savings': -300},

    # ── 8. Energy-Efficient Refrigerators ─────────────────────────────────────
    'FREEZER_UPRIGHT_S':    {'impl': 350,   'maint': 53,    'savings': 56},
    'FREEZER_UPRIGHT_M':    {'impl': 700,   'maint': 105,   'savings': 77},
    'FREEZER_UPRIGHT_L':    {'impl': 1000,  'maint': 150,   'savings': 81},
    'FREEZER_DEEP_S':       {'impl': 400,   'maint': 60,    'savings': 49},
    'FREEZER_DEEP_M':       {'impl': 600,   'maint': 90,    'savings': 57},
    'FREEZER_DEEP_L':       {'impl': 900,   'maint': 135,   'savings': 61},

    # ── 9. Energy-Efficient AC Splits ─────────────────────────────────────────
    'AC_WINDOW_1TON':       {'impl': 800,   'maint': 120,   'savings': 130},
    'AC_WINDOW_2TON':       {'impl': 1200,  'maint': 180,   'savings': 326},
    'AC_SPLIT_1TON':        {'impl': 800,   'maint': 120,   'savings': 130},
    'AC_SPLIT_2TON':        {'impl': 1200,  'maint': 180,   'savings': 326},
    'AC_SPLIT_3TON':        {'impl': 2000,  'maint': 300,   'savings': 509},
    'AC_CENTRAL_5TON':      {'impl': 6000,  'maint': 900,   'savings': 371},

    # ── 10. Energy-Efficient Heaters ──────────────────────────────────────────
    'HEATER_SPACE_2KW':     {'impl': 150,   'maint': 23,    'savings': 164},
    'HEATER_INFRARED_1KW':  {'impl': 250,   'maint': 38,    'savings': 296},
    'HEATER_OIL_RADIATOR':  {'impl': 200,   'maint': 30,    'savings': 188},
    'HEATER_BASEBOARD':     {'impl': 200,   'maint': 30,    'savings': 372},
    'HEATER_CENTRAL_FURNACE':{'impl': 6000, 'maint': 900,   'savings': 1425},

    # ── 11. Incinerator ───────────────────────────────────────────────────────
    'INCINERATOR_TAM':      {'impl': 37000, 'maint': 5550,  'savings': 668},

    # ── 12. Motion Sensors ────────────────────────────────────────────────────
    'LAMP_MOTION_SENSOR':   {'impl': 10000, 'maint': 1500,  'savings': 9276},  # 200 sensors

    # ── 13. Hybrid Cars ───────────────────────────────────────────────────────
    'HYBRID_LAND_CRUISER':  {'impl': 60000, 'maint': 9000,  'savings': 484},
    'HYBRID_PRIUS':         {'impl': 26000, 'maint': 3900,  'savings': 503},

    # ── 14–18. Other ──────────────────────────────────────────────────────────
    'WHITE_ROOF_PAINT':     {'impl': 400,   'maint': 60,    'savings': 348},    # 20 m²
    'SUSTAINABILITY_POLICY':{'impl': 10000, 'maint': 0,     'savings': -2000},  # net staff cost
    'TREE_PLANTING':        {'impl': 500,   'maint': 0,     'savings': -20},    # 100 trees
    'TRAINING_AWARENESS':   {'impl': 2500,  'maint': 225,   'savings': -908},   # net staff cost
    'EE_LAUNDRY':           {'impl': 1800,  'maint': 54,    'savings': 600},
}

# Emission reduction percentages per intervention (applied to the target category).
# For per-unit interventions (LED, refrigerants) the % is relative to the device baseline.
# For facility-level interventions (solar) it is relative to a typical 55,158 kWh/year facility.
# Users should set FacilityIntervention.emission_reduction_achieved for site-specific values.
# Sources: CARBOMICA D3.7 Carbon Saving + Cost Saving Calculators (ZW baseline).
REDUCTION_PCT = {
    # ── Legacy entries ────────────────────────────────────────────────────────
    'SOLAR_PV':             70,
    'LOW_GWP_ANAESTHETICS': 85,
    'LED_LIGHTING':         30,
    'WASTE_SEGREGATION':    60,
    'WATER_EFFICIENT_FIXTURES': 5,
    'HFC_REFRIGERANT_SWAP': 75,
    'DPI_INHALER_SWITCH':   70,
    'FLEET_OPTIMISATION':   25,

    # ── 1. LED Lights ─────────────────────────────────────────────────────────
    'LED_WATT_5':           20,   # saves 20 % of lamp electricity (25W→20W)
    'LED_WATT_10':          50,   # 20W→10W
    'LED_WATT_20':          80,   # 25W→5W
    'LED_WATT_50':          50,   # 100W→50W
    'LED_WATT_95':          95,   # 100W→5W

    # ── 2. Solar Systems (% of 55,158 kWh/year typical hospital baseline) ─────
    'SOLAR_3KVA':           9,
    'SOLAR_5KVA':           15,
    'SOLAR_10KVA':          30,
    'SOLAR_100KWP':         70,
    'SOLAR_150KWP':         85,
    'SOLAR_600KWP':         99,

    # ── 3. Biogas ─────────────────────────────────────────────────────────────
    'BIOGAS_6M3':           50,   # replaces ~50 % of LPG use
    'BIOGAS_20M3':          70,

    # ── 4. Refrigerants (% GWP reduction per kg swapped) ──────────────────────
    'REFRIG_R134A_R1234YF': 99,
    'REFRIG_R134A_R1234ZE': 99,
    'REFRIG_R410A_R1234ZE': 99,
    'REFRIG_R410A_R32':     68,
    'REFRIG_R404A_R448A':   68,
    'REFRIG_R22_R290':      99,
    'REFRIG_R32_R744':      99,
    'REFRIG_R403A_R407A':   56,

    # ── 5 & 6. Anaesthetic gases ──────────────────────────────────────────────
    'ANAES_ISO_SEVO':       75,   # (510-130)/510 GWP reduction
    'ANAES_NO_AVOID':       100,

    # ── 7. Inhalers ───────────────────────────────────────────────────────────
    'INHALER_DPI':          100,
    'INHALER_SMI':          100,

    # ── 8. Energy-Efficient Refrigerators (% saving of appliance electricity) ─
    'FREEZER_UPRIGHT_S':    46,
    'FREEZER_UPRIGHT_M':    53,
    'FREEZER_UPRIGHT_L':    57,
    'FREEZER_DEEP_S':       45,
    'FREEZER_DEEP_M':       54,
    'FREEZER_DEEP_L':       58,

    # ── 9. AC Splits (% saving of unit electricity) ───────────────────────────
    'AC_WINDOW_1TON':       43,
    'AC_WINDOW_2TON':       47,
    'AC_SPLIT_1TON':        43,
    'AC_SPLIT_2TON':        47,
    'AC_SPLIT_3TON':        52,
    'AC_CENTRAL_5TON':      39,

    # ── 10. Heaters ───────────────────────────────────────────────────────────
    'HEATER_SPACE_2KW':     46,
    'HEATER_INFRARED_1KW':  50,
    'HEATER_OIL_RADIATOR':  48,
    'HEATER_BASEBOARD':     51,
    'HEATER_CENTRAL_FURNACE': 47,

    # ── 11–18. Other ──────────────────────────────────────────────────────────
    'INCINERATOR_TAM':      67,   # 1,200/1,800 L fuel saved
    'LAMP_MOTION_SENSOR':   3,    # ~3 % of lighting electricity
    'HYBRID_LAND_CRUISER':  39,   # 1,577/4,032 L fuel saved
    'HYBRID_PRIUS':         44,   # 792/1,800 L fuel saved
    'WHITE_ROOF_PAINT':     10,   # ~10 % A/C energy saving
    'SUSTAINABILITY_POLICY': 10,  # midpoint of 4–15 % evidence range
    'TREE_PLANTING':        0,    # carbon offset — no direct emission reduction
    'TRAINING_AWARENESS':   6,    # midpoint of 4–8 % evidence range
    'EE_LAUNDRY':           25,   # ENERGY STAR: 25 % less energy
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
