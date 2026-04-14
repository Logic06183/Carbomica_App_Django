"""
CARBOMICA test suite.

Covers:
  1. INTERVENTION_LIBRARY integrity (all entries well-formed)
  2. sync_interventions management command (correct DB state)
  3. compute_tco2e / sum_tco2e emission calculations
  4. CarbomicaOptimizer — three-scenario analysis
"""
from decimal import Decimal

from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import TestCase
from io import StringIO

from appname.models import (
    Facility, EmissionData, EmissionSource,
    Intervention, FacilityIntervention,
)
from appname.modeling import (
    INTERVENTION_LIBRARY,
    EMISSION_FACTORS, ELECTRICITY_EF,
    compute_tco2e, sum_tco2e,
    CarbomicaOptimizer,
)


# ---------------------------------------------------------------------------
# 1. INTERVENTION_LIBRARY structural integrity
# ---------------------------------------------------------------------------

class InterventionLibraryIntegrityTest(TestCase):
    """INTERVENTION_LIBRARY dict must be well-formed for sync_interventions to work."""

    def test_all_entries_have_display_name(self):
        for code, data in INTERVENTION_LIBRARY.items():
            self.assertIn('display_name', data, f"{code} missing 'display_name'")
            self.assertTrue(data['display_name'].strip(), f"{code} has blank display_name")

    def test_all_entries_have_sdg_goals_list(self):
        for code, data in INTERVENTION_LIBRARY.items():
            self.assertIn('sdg_goals', data, f"{code} missing 'sdg_goals'")
            self.assertIsInstance(data['sdg_goals'], list, f"{code} sdg_goals must be a list")

    def test_all_entries_have_reduces_dict(self):
        for code, data in INTERVENTION_LIBRARY.items():
            self.assertIn('reduces', data, f"{code} missing 'reduces'")
            self.assertIsInstance(data['reduces'], dict, f"{code} reduces must be a dict")

    def test_reduces_keys_are_valid_emission_fields(self):
        valid_fields = set(EMISSION_FACTORS.keys())
        for code, data in INTERVENTION_LIBRARY.items():
            for field in data['reduces']:
                self.assertIn(
                    field, valid_fields,
                    f"{code}.reduces has unknown field '{field}'"
                )

    def test_reduces_values_are_decimals_in_range(self):
        for code, data in INTERVENTION_LIBRARY.items():
            for field, val in data['reduces'].items():
                self.assertIsInstance(val, Decimal, f"{code}.reduces[{field}] must be Decimal")
                self.assertGreaterEqual(val, Decimal('0'), f"{code}.reduces[{field}] < 0")
                self.assertLessEqual(val, Decimal('1'), f"{code}.reduces[{field}] > 1")

    def test_no_duplicate_code_names(self):
        codes = list(INTERVENTION_LIBRARY.keys())
        self.assertEqual(len(codes), len(set(codes)), "Duplicate code_names in INTERVENTION_LIBRARY")

    def test_minimum_library_size(self):
        """Must have at least 56 entries after the expansion."""
        self.assertGreaterEqual(
            len(INTERVENTION_LIBRARY), 56,
            f"Expected ≥56 entries, got {len(INTERVENTION_LIBRARY)}"
        )

    def test_new_categories_present(self):
        expected_keys = [
            # LED
            'LED_WATT_5', 'LED_WATT_10', 'LED_WATT_20', 'LED_WATT_50', 'LED_WATT_95',
            # Solar
            'SOLAR_3KVA', 'SOLAR_5KVA', 'SOLAR_10KVA', 'SOLAR_100KWP', 'SOLAR_150KWP', 'SOLAR_600KWP',
            # Biogas
            'BIOGAS_6M3', 'BIOGAS_20M3',
            # Refrigerants
            'REFRIG_R134A_R1234YF', 'REFRIG_R134A_R1234ZE', 'REFRIG_R410A_R1234ZE',
            'REFRIG_R410A_R32', 'REFRIG_R404A_R448A', 'REFRIG_R22_R290',
            'REFRIG_R32_R744', 'REFRIG_R403A_R407A',
            # Anaesthetics
            'ANAES_ISO_SEVO', 'ANAES_NO_AVOID',
            # Inhalers
            'INHALER_DPI', 'INHALER_SMI',
            # Freezers
            'FREEZER_UPRIGHT_S', 'FREEZER_UPRIGHT_M', 'FREEZER_UPRIGHT_L',
            'FREEZER_DEEP_S', 'FREEZER_DEEP_M', 'FREEZER_DEEP_L',
            # AC
            'AC_WINDOW_1TON', 'AC_WINDOW_2TON', 'AC_SPLIT_1TON',
            'AC_SPLIT_2TON', 'AC_SPLIT_3TON', 'AC_CENTRAL_5TON',
            # Heaters
            'HEATER_SPACE_2KW', 'HEATER_INFRARED_1KW', 'HEATER_OIL_RADIATOR',
            'HEATER_BASEBOARD', 'HEATER_CENTRAL_FURNACE',
            # Other
            'INCINERATOR_TAM', 'LAMP_MOTION_SENSOR',
            'HYBRID_LAND_CRUISER', 'HYBRID_PRIUS',
            'WHITE_ROOF_PAINT', 'SUSTAINABILITY_POLICY',
            'TREE_PLANTING', 'TRAINING_AWARENESS', 'EE_LAUNDRY',
        ]
        for key in expected_keys:
            self.assertIn(key, INTERVENTION_LIBRARY, f"Missing expected key: {key}")

    def test_legacy_entries_still_present(self):
        legacy = [
            'SOLAR_PV', 'LOW_GWP_ANAESTHETICS', 'LED_LIGHTING',
            'WASTE_SEGREGATION', 'WATER_EFFICIENT_FIXTURES',
            'HFC_REFRIGERANT_SWAP', 'DPI_INHALER_SWITCH', 'FLEET_OPTIMISATION',
        ]
        for key in legacy:
            self.assertIn(key, INTERVENTION_LIBRARY, f"Legacy key removed: {key}")


# ---------------------------------------------------------------------------
# 2. sync_interventions management command
# ---------------------------------------------------------------------------

class SyncInterventionsCommandTest(TestCase):

    def test_command_creates_all_library_entries(self):
        out = StringIO()
        call_command('sync_interventions', stdout=out)
        created = Intervention.objects.count()
        self.assertEqual(
            created, len(INTERVENTION_LIBRARY),
            f"Expected {len(INTERVENTION_LIBRARY)} Intervention rows, got {created}"
        )

    def test_command_is_idempotent(self):
        """Running sync twice must not create duplicates."""
        call_command('sync_interventions', stdout=StringIO())
        call_command('sync_interventions', stdout=StringIO())
        self.assertEqual(Intervention.objects.count(), len(INTERVENTION_LIBRARY))

    def test_emission_reduction_pct_set(self):
        call_command('sync_interventions', stdout=StringIO())
        solar = Intervention.objects.get(code_name='SOLAR_100KWP')
        self.assertEqual(solar.emission_reduction_percentage, Decimal('70'))

    def test_target_category_set_for_solar(self):
        call_command('sync_interventions', stdout=StringIO())
        solar = Intervention.objects.get(code_name='SOLAR_3KVA')
        self.assertIn('grid_electricity', solar.target_category)

    def test_target_category_set_for_refrigerants(self):
        call_command('sync_interventions', stdout=StringIO())
        refrig = Intervention.objects.get(code_name='REFRIG_R22_R290')
        self.assertIn('refrigeration_gases', refrig.target_category)

    def test_target_category_set_for_anaesthetics(self):
        call_command('sync_interventions', stdout=StringIO())
        anaes = Intervention.objects.get(code_name='ANAES_ISO_SEVO')
        self.assertIn('anaesthetic_gases', anaes.target_category)

    def test_target_category_set_for_inhalers(self):
        call_command('sync_interventions', stdout=StringIO())
        inhaler = Intervention.objects.get(code_name='INHALER_DPI')
        self.assertIn('medical_inhalers', inhaler.target_category)

    def test_target_category_set_for_vehicles(self):
        call_command('sync_interventions', stdout=StringIO())
        car = Intervention.objects.get(code_name='HYBRID_PRIUS')
        self.assertIn('vehicle_fuel_owned', car.target_category)

    def test_energy_savings_set_from_costs(self):
        call_command('sync_interventions', stdout=StringIO())
        sensor = Intervention.objects.get(code_name='LAMP_MOTION_SENSOR')
        self.assertEqual(sensor.energy_savings, Decimal('9276'))

    def test_sdg_goals_stored(self):
        call_command('sync_interventions', stdout=StringIO())
        solar = Intervention.objects.get(code_name='SOLAR_600KWP')
        sdg_list = [int(x) for x in solar.sdg_goals.split(',') if x]
        self.assertIn(7, sdg_list)
        self.assertIn(13, sdg_list)

    def test_tree_planting_has_zero_pct(self):
        """Tree planting is an offset with no direct % reduction."""
        call_command('sync_interventions', stdout=StringIO())
        trees = Intervention.objects.get(code_name='TREE_PLANTING')
        self.assertEqual(trees.emission_reduction_percentage, Decimal('0'))

    def test_legacy_entries_updated(self):
        """Existing legacy entries are updated, not duplicated."""
        call_command('sync_interventions', stdout=StringIO())
        count = Intervention.objects.filter(code_name='SOLAR_PV').count()
        self.assertEqual(count, 1)


# ---------------------------------------------------------------------------
# 3. compute_tco2e / sum_tco2e
# ---------------------------------------------------------------------------

class EmissionCalculationTest(TestCase):

    def _make_emission_data(self, **kwargs):
        """Build an unsaved EmissionData-like object with only the given fields non-zero."""
        defaults = {f: Decimal('0') for f in EMISSION_FACTORS}
        defaults.update(kwargs)

        class FakeED:
            pass

        obj = FakeED()
        for k, v in defaults.items():
            setattr(obj, k, Decimal(str(v)))
        return obj

    def test_zero_emissions_return_zero_total(self):
        ed = self._make_emission_data()
        result = compute_tco2e(ed, country='ZW')
        self.assertEqual(result['total'], Decimal('0'))

    def test_grid_electricity_zw_uses_zesa_ef(self):
        """100 kWh at ZW EF (0.000556 tCO2e/kWh) = 0.0556 tCO2e."""
        ed = self._make_emission_data(grid_electricity=100)
        result = compute_tco2e(ed, country='ZW')
        expected = Decimal('100') * ELECTRICITY_EF['ZW']
        self.assertAlmostEqual(float(result['grid_electricity']), float(expected), places=6)

    def test_grid_electricity_ke_uses_kplc_ef(self):
        """Kenya grid is almost all renewables — EF should be much lower than ZW."""
        ed = self._make_emission_data(grid_electricity=100)
        zw = compute_tco2e(ed, country='ZW')['grid_electricity']
        ke = compute_tco2e(ed, country='KE')['grid_electricity']
        self.assertGreater(zw, ke, "ZW EF should be higher than KE EF")

    def test_grid_electricity_za_uses_eskom_ef(self):
        """SA (coal-heavy) should be even higher than ZW per kWh."""
        ed = self._make_emission_data(grid_electricity=100)
        za = compute_tco2e(ed, country='ZA')['grid_electricity']
        zw = compute_tco2e(ed, country='ZW')['grid_electricity']
        self.assertGreater(za, zw, "ZA Eskom EF should exceed ZW ZESA EF")

    def test_anaesthetic_gases_factor(self):
        """1 kg anaesthetic = 0.802 tCO2e."""
        ed = self._make_emission_data(anaesthetic_gases=1)
        result = compute_tco2e(ed, country='ZW')
        self.assertAlmostEqual(float(result['anaesthetic_gases']), 0.802, places=3)

    def test_refrigeration_gases_factor(self):
        """1 kg refrigerant lost = 1.800 tCO2e."""
        ed = self._make_emission_data(refrigeration_gases=1)
        result = compute_tco2e(ed, country='ZW')
        self.assertAlmostEqual(float(result['refrigeration_gases']), 1.800, places=3)

    def test_medical_inhalers_factor(self):
        """1 pMDI = 0.0189 tCO2e."""
        ed = self._make_emission_data(medical_inhalers=1)
        result = compute_tco2e(ed, country='ZW')
        self.assertAlmostEqual(float(result['medical_inhalers']), 0.0189, places=4)

    def test_total_is_sum_of_categories(self):
        ed = self._make_emission_data(grid_electricity=50, liquid_fuel=10)
        result = compute_tco2e(ed, country='ZW')
        category_sum = sum(v for k, v in result.items() if k != 'total')
        self.assertAlmostEqual(float(result['total']), float(category_sum), places=8)

    def test_unknown_country_falls_back_to_other(self):
        ed = self._make_emission_data(grid_electricity=100)
        result = compute_tco2e(ed, country='XX')
        expected = Decimal('100') * ELECTRICITY_EF['OTHER']
        self.assertAlmostEqual(float(result['grid_electricity']), float(expected), places=6)


# ---------------------------------------------------------------------------
# 4. CarbomicaOptimizer
# ---------------------------------------------------------------------------

class OptimizerTest(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user('testuser', password='pass')
        cls.facility = Facility.objects.create(
            code_name='TEST_FACILITY',
            display_name='Test Hospital',
            country='ZW',
        )
        call_command('sync_interventions', stdout=StringIO())

    def _make_fi(self, code_name, impl_cost, maint_cost, annual_savings=0):
        """Create a FacilityIntervention for a given intervention code_name."""
        intervention = Intervention.objects.get(code_name=code_name)
        return FacilityIntervention.objects.create(
            facility=self.facility,
            intervention=intervention,
            implementation_cost=Decimal(str(impl_cost)),
            maintenance_cost=Decimal(str(maint_cost)),
            annual_savings=Decimal(str(annual_savings)),
        )

    def _make_optimizer(self, fi_list, budget, baseline, category_baselines=None):
        return CarbomicaOptimizer(
            facility_interventions=fi_list,
            budget=budget,
            total_baseline_emissions=baseline,
            category_baselines=category_baselines or {},
        )

    def test_scenario1_includes_all_interventions(self):
        fi1 = self._make_fi('SOLAR_3KVA', 2500, 1875)
        fi2 = self._make_fi('LED_WATT_50', 160, 5)
        optimizer = self._make_optimizer([fi1, fi2], budget=0, baseline=50)
        result = optimizer.full_coverage()
        self.assertEqual(len(result), 2)

    def test_scenario2_respects_budget_zero(self):
        fi1 = self._make_fi('SOLAR_3KVA', 2500, 1875)
        optimizer = self._make_optimizer([fi1], budget=0, baseline=50)
        result = optimizer.fixed_budget()
        self.assertEqual(result, [], "No interventions should fit in $0 budget")

    def test_scenario2_fits_cheap_intervention(self):
        fi_cheap = self._make_fi('LED_WATT_5', 600, 18)
        fi_expensive = self._make_fi('SOLAR_600KWP', 612000, 459000)
        optimizer = self._make_optimizer(
            [fi_cheap, fi_expensive], budget=1000, baseline=100
        )
        result = optimizer.fixed_budget()
        names = [r['intervention_name'] for r in result]
        self.assertIn('LED Lights — 5W Wattage Reduction per Lamp', names)
        self.assertNotIn('Solar PV System — 600 kWp', names)

    def test_scenario3_includes_zero_cost_interventions(self):
        """Zero-cost interventions are always affordable; they appear in optimised()."""
        fi_free = self._make_fi('ANAES_NO_AVOID', 0, 0)
        fi_expensive = self._make_fi('SOLAR_100KWP', 80000, 60000)
        category_baselines = {
            'anaesthetic_gases': Decimal('10'),
            'grid_electricity': Decimal('30'),
        }
        optimizer = self._make_optimizer(
            [fi_free, fi_expensive],
            budget=500,
            baseline=40,
            category_baselines=category_baselines,
        )
        result = optimizer.optimised()
        names = [r['intervention_name'] for r in result]
        self.assertIn('Avoid Nitrous Oxide (N\u2082O)', names,
                      "Zero-cost intervention should always fit within budget")
        self.assertNotIn('Solar PV System — 100 kWp', names,
                         "Expensive intervention should not fit $500 budget")

    def test_emission_reduction_uses_category_baseline(self):
        """_emission_reduction should apply % to the category baseline, not total."""
        fi = self._make_fi('SOLAR_3KVA', 2500, 1875)
        category_baselines = {
            'grid_electricity': Decimal('30.0'),
        }
        optimizer = self._make_optimizer([fi], budget=5000, baseline=50,
                                         category_baselines=category_baselines)
        reduction = optimizer._emission_reduction(fi)
        # SOLAR_3KVA emission_reduction_percentage=9 → 9/100 * 30 = 2.7
        expected = Decimal('9') / 100 * Decimal('30.0')
        self.assertAlmostEqual(float(reduction), float(expected), places=4)

    def test_emission_reduction_falls_back_to_total_baseline(self):
        """When category_baselines is empty, fall back to total baseline."""
        fi = self._make_fi('LED_WATT_95', 200, 6)
        optimizer = self._make_optimizer([fi], budget=1000, baseline=Decimal('100'),
                                         category_baselines={})
        reduction = optimizer._emission_reduction(fi)
        # LED_WATT_95 emission_reduction_percentage=95, no category baselines → uses total
        expected = Decimal('95') / 100 * Decimal('100')
        self.assertAlmostEqual(float(reduction), float(expected), places=4)

    def test_cost_effectiveness_zero_for_zero_cost(self):
        """Current impl returns 0 CE for zero-cost interventions (they still fit via cost<=budget)."""
        fi = self._make_fi('ANAES_NO_AVOID', 0, 0)
        category_baselines = {'anaesthetic_gases': Decimal('10')}
        optimizer = self._make_optimizer([fi], budget=500, baseline=10,
                                         category_baselines=category_baselines)
        ce = optimizer._cost_effectiveness(fi)
        self.assertEqual(ce, Decimal('0'))

    def test_all_three_scenarios_run_without_error(self):
        """Smoke test: running all three scenarios produces lists of dicts."""
        fi1 = self._make_fi('SOLAR_5KVA', 4000, 3000)
        fi2 = self._make_fi('WASTE_SEGREGATION', 2000, 300)
        fi3 = self._make_fi('REFRIG_R22_R290', 0, 0)
        optimizer = self._make_optimizer(
            [fi1, fi2, fi3], budget=10000, baseline=Decimal('200'),
            category_baselines={
                'grid_electricity': Decimal('100'),
                'waste_management': Decimal('50'),
                'refrigeration_gases': Decimal('50'),
            }
        )
        s1 = optimizer.full_coverage()
        s2 = optimizer.fixed_budget()
        s3 = optimizer.optimised()
        self.assertIsInstance(s1, list)
        self.assertIsInstance(s2, list)
        self.assertIsInstance(s3, list)
        # Each result should be a dict with expected keys
        for scenario in [s1, s2, s3]:
            for item in scenario:
                self.assertIn('intervention_name', item)
                self.assertIn('emission_reduction', item)
                self.assertIn('cost', item)

    def test_new_interventions_have_nonzero_reduction_pct(self):
        """All new interventions (except TREE_PLANTING) must have non-zero reduction %."""
        zero_expected = {'TREE_PLANTING'}
        call_command('sync_interventions', stdout=StringIO())  # idempotent
        for code in INTERVENTION_LIBRARY:
            if code in zero_expected:
                continue
            intervention = Intervention.objects.get(code_name=code)
            self.assertGreater(
                intervention.emission_reduction_percentage,
                Decimal('0'),
                f"{code} has emission_reduction_percentage=0 — optimizer will ignore it"
            )
