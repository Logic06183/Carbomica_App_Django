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
    Intervention, FacilityIntervention, OptimizationScenario,
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

    def test_scenario3_ranks_zero_cost_interventions_first(self):
        """Zero-cost interventions must be selected first in the greedy knapsack."""
        fi_free = self._make_fi('ANAES_NO_AVOID', 0, 0)
        fi_expensive = self._make_fi('SOLAR_100KWP', 80000, 60000)
        category_baselines = {
            'anaesthetic_gases': Decimal('10'),
            'grid_electricity': Decimal('30'),
        }
        optimizer = self._make_optimizer(
            [fi_expensive, fi_free],   # expensive listed first to confirm ordering matters
            budget=500,
            baseline=40,
            category_baselines=category_baselines,
        )
        result = optimizer.optimised()
        names = [r['intervention_name'] for r in result]
        self.assertIn('Avoid Nitrous Oxide (N\u2082O)', names,
                      "Zero-cost intervention must appear in results")
        self.assertNotIn('Solar PV System — 100 kWp', names,
                         "Expensive intervention must not fit $500 budget")
        # Priority 1 should be the free intervention
        self.assertEqual(result[0]['priority'], 1)
        self.assertEqual(result[0]['intervention_name'], 'Avoid Nitrous Oxide (N\u2082O)')

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

    def test_cost_effectiveness_very_high_for_zero_cost(self):
        """Zero-cost interventions return a sentinel >> any paid-intervention ratio."""
        fi = self._make_fi('ANAES_NO_AVOID', 0, 0)
        fi_paid = self._make_fi('SOLAR_3KVA', 2500, 1875)
        category_baselines = {
            'anaesthetic_gases': Decimal('10'),
            'grid_electricity': Decimal('30'),
        }
        optimizer = self._make_optimizer([fi, fi_paid], budget=5000, baseline=40,
                                         category_baselines=category_baselines)
        ce_free = optimizer._cost_effectiveness(fi)
        ce_paid = optimizer._cost_effectiveness(fi_paid)
        self.assertGreater(ce_free, ce_paid,
                           "Zero-cost intervention must rank above any paid intervention")

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


# ---------------------------------------------------------------------------
# 5. Phase A1 — facility-creation auto-attach + access control
#    (CARBOMICA office-hours design 2026-04-27 — "Tinah Unblocker")
# ---------------------------------------------------------------------------

class AddFacilityAuthTest(TestCase):
    """Bug 1: anonymous users must not be able to create orphan facilities."""

    def test_anonymous_post_redirects_to_login(self):
        response = self.client.post('/add-facility/', {
            'code_name': 'ANON_FAC',
            'display_name': 'Anonymous Facility',
            'country': 'ZA',
            'facility_type': 'health_centre',
        })
        self.assertEqual(response.status_code, 302)
        self.assertIn('/accounts/login/', response['Location'])
        self.assertEqual(Facility.objects.filter(code_name='ANON_FAC').count(), 0)


class FacilityAutoAttachTest(TestCase):
    """Bug 2: every newly-created facility must have all library interventions attached."""

    @classmethod
    def setUpTestData(cls):
        call_command('sync_interventions', stdout=StringIO())
        cls.user = User.objects.create_user('tinah', 'tinah@example.com', 'pw')

    def test_authenticated_post_creates_one_facility_intervention_per_library_entry(self):
        """Opt-IN path: prefill_interventions='on' attaches the full library."""
        self.client.login(username='tinah', password='pw')
        intervention_count = Intervention.objects.count()
        self.assertGreater(intervention_count, 0, 'Sanity: sync_interventions populated the library')

        response = self.client.post('/add-facility/', {
            'code_name': 'TINAH_FAC',
            'display_name': 'Tinah Test Hospital',
            'country': 'ZW',
            'facility_type': 'district_hospital',
            'date': '2026-01-01',
            'grid_electricity': '100000',
            'grid_gas': '0',
            'bottled_gas': '0',
            'liquid_fuel': '0',
            'vehicle_fuel_owned': '0',
            'business_travel': '0',
            'anaesthetic_gases': '0',
            'refrigeration_gases': '0',
            'waste_management': '0',
            'medical_inhalers': '0',
            'contractor_logistics': '0',
            'prefill_interventions': 'on',
        })

        # Form-validation issues would render 200; success is a 302 to facilities.
        self.assertEqual(response.status_code, 302, f'Expected redirect, got {response.status_code} — {response.content[:200] if response.status_code == 200 else ""}')
        facility = Facility.objects.get(code_name='TINAH_FAC')
        self.assertEqual(facility.created_by, self.user)
        attached = FacilityIntervention.objects.filter(facility=facility).count()
        self.assertEqual(
            attached, intervention_count,
            f'Expected {intervention_count} auto-attached rows, got {attached}'
        )
        # cost_source provenance is correctly tagged
        sources = set(FacilityIntervention.objects.filter(facility=facility)
                      .values_list('cost_source', flat=True))
        self.assertTrue(sources.issubset({'DEFAULT', 'PLACEHOLDER'}),
                        f'Unexpected cost_source values: {sources}')

    def _facility_payload(self, code, **overrides):
        payload = {
            'code_name': code,
            'display_name': f'{code} Hospital',
            'country': 'ZW',
            'facility_type': 'district_hospital',
            'date': '2026-01-01',
            'grid_electricity': '100000', 'grid_gas': '0', 'bottled_gas': '0',
            'liquid_fuel': '0', 'vehicle_fuel_owned': '0', 'business_travel': '0',
            'anaesthetic_gases': '0', 'refrigeration_gases': '0',
            'waste_management': '0', 'medical_inhalers': '0', 'contractor_logistics': '0',
        }
        payload.update(overrides)
        return payload

    def test_prefill_checked_attaches_full_library(self):
        """Default path: checkbox ticked → all interventions attached."""
        self.client.login(username='tinah', password='pw')
        resp = self.client.post('/add-facility/',
                                self._facility_payload('PREFILL_ON', prefill_interventions='on'))
        self.assertEqual(resp.status_code, 302)
        facility = Facility.objects.get(code_name='PREFILL_ON')
        self.assertEqual(
            FacilityIntervention.objects.filter(facility=facility).count(),
            Intervention.objects.count(),
        )

    def test_prefill_unchecked_starts_empty(self):
        """
        Opt-out path. With the hidden-field + checkbox pattern, an unticked
        checkbox submits only the hidden value 'off' (the browser drops the
        checkbox's own 'on'). So the realistic unchecked payload is
        prefill_interventions='off'.
        """
        self.client.login(username='tinah', password='pw')
        payload = self._facility_payload('PREFILL_OFF', prefill_interventions='off')
        resp = self.client.post('/add-facility/', payload)
        self.assertEqual(resp.status_code, 302)
        facility = Facility.objects.get(code_name='PREFILL_OFF')
        self.assertEqual(
            FacilityIntervention.objects.filter(facility=facility).count(), 0,
            'Unchecking "Pre-attach" must create the facility with no interventions',
        )

    def test_prefill_absent_defaults_to_empty(self):
        """
        Default flipped 2026-05-24 per user feedback: a payload with no
        prefill field creates the facility with NO interventions attached.
        Users opt IN to the attach-everything behaviour.
        """
        self.client.login(username='tinah', password='pw')
        payload = self._facility_payload('PREFILL_ABSENT')
        payload.pop('prefill_interventions', None)
        resp = self.client.post('/add-facility/', payload)
        self.assertEqual(resp.status_code, 302)
        facility = Facility.objects.get(code_name='PREFILL_ABSENT')
        self.assertEqual(
            FacilityIntervention.objects.filter(facility=facility).count(), 0,
            'New facilities must start empty unless prefill is explicitly on',
        )


class BackfillIdempotentTest(TestCase):
    """The backfill command must be safe to run twice."""

    @classmethod
    def setUpTestData(cls):
        call_command('sync_interventions', stdout=StringIO())
        cls.user = User.objects.create_user('craig', 'craig@example.com', 'pw')
        # Pre-existing facility with NO FacilityInterventions (mirrors the
        # state the seeded study sites were in before Phase A1 shipped).
        cls.facility = Facility.objects.create(
            code_name='LEGACY_FAC',
            display_name='Legacy Facility (pre-A1)',
            country='KE',
            facility_type='central_hospital',
            created_by=cls.user,
        )

    def test_backfill_creates_then_is_idempotent(self):
        self.assertEqual(
            FacilityIntervention.objects.filter(facility=self.facility).count(),
            0, 'Sanity: facility starts with zero interventions'
        )
        intervention_count = Intervention.objects.count()

        call_command('backfill_facility_interventions', stdout=StringIO())
        first_run = FacilityIntervention.objects.filter(facility=self.facility).count()
        self.assertEqual(first_run, intervention_count)

        # Second run must not create duplicates.
        call_command('backfill_facility_interventions', stdout=StringIO())
        second_run = FacilityIntervention.objects.filter(facility=self.facility).count()
        self.assertEqual(second_run, intervention_count, 'Backfill is not idempotent')


class FreshFacilityOptimiserTest(TestCase):
    """The whole point of Phase A1: a freshly-created facility produces a non-empty optimiser result."""

    @classmethod
    def setUpTestData(cls):
        call_command('sync_interventions', stdout=StringIO())
        cls.user = User.objects.create_user('tinah2', 'tinah2@example.com', 'pw')

    def test_optimiser_produces_non_empty_results_for_fresh_facility(self):
        from appname.modeling import CarbomicaOptimizer
        from appname.views import _seed_facility_interventions

        facility = Facility.objects.create(
            code_name='FRESH_FAC',
            display_name='Fresh Facility',
            country='ZA',
            facility_type='district_hospital',
            created_by=self.user,
        )
        _seed_facility_interventions(facility)

        facility_interventions = (
            FacilityIntervention.objects
            .select_related('facility', 'intervention')
            .filter(facility=facility)
        )
        # Run the optimiser exactly as views.optimize_interventions does.
        optimizer = CarbomicaOptimizer(
            facility_interventions=facility_interventions,
            budget=Decimal('50000'),
            total_baseline_emissions=Decimal('1000'),
            category_baselines={'grid_electricity': Decimal('1000')},
        )
        scenarios = optimizer.run_all_scenarios()

        for name in ('full_coverage', 'fixed_budget', 'optimised'):
            self.assertIn(name, scenarios, f'Missing scenario: {name}')
            self.assertGreater(
                len(scenarios[name]['results']), 0,
                f'Scenario "{name}" returned empty results — Bug 2 is back'
            )


class AttachDetachInterventionTest(TestCase):
    """
    Jetina-flow regression coverage: a logged-in facility owner can
    detach and re-attach interventions from their facility detail page.
    Previously impossible — no URL/view existed, so the only way to
    "remove" an intervention was via Django admin.
    """

    @classmethod
    def setUpTestData(cls):
        call_command('sync_interventions', stdout=StringIO())
        cls.owner = User.objects.create_user('owner', 'owner@example.com', 'pw')
        cls.outsider = User.objects.create_user('outsider', 'outsider@example.com', 'pw')
        cls.facility = Facility.objects.create(
            code_name='JET_FAC',
            display_name='Mt Darwin Hospital',
            country='ZW',
            facility_type='district_hospital',
            created_by=cls.owner,
        )
        from appname.views import _seed_facility_interventions
        _seed_facility_interventions(cls.facility)
        cls.intervention = Intervention.objects.first()

    def test_detach_removes_facility_intervention_row(self):
        self.client.login(username='owner', password='pw')
        before = FacilityIntervention.objects.filter(facility=self.facility).count()
        response = self.client.post(
            f'/facilities/{self.facility.id}/interventions/{self.intervention.id}/detach/'
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response['Location'], f'/facilities/{self.facility.id}/')
        after = FacilityIntervention.objects.filter(facility=self.facility).count()
        self.assertEqual(after, before - 1, 'detach should remove exactly one row')
        self.assertFalse(
            FacilityIntervention.objects.filter(
                facility=self.facility, intervention=self.intervention,
            ).exists()
        )

    def test_attach_recreates_row_with_library_defaults(self):
        self.client.login(username='owner', password='pw')
        FacilityIntervention.objects.filter(
            facility=self.facility, intervention=self.intervention,
        ).delete()
        response = self.client.post(
            f'/facilities/{self.facility.id}/interventions/{self.intervention.id}/attach/'
        )
        self.assertEqual(response.status_code, 302)
        fi = FacilityIntervention.objects.get(
            facility=self.facility, intervention=self.intervention,
        )
        self.assertIn(fi.cost_source, ('DEFAULT', 'PLACEHOLDER'))

    def test_attach_is_idempotent_and_does_not_clobber_custom_costs(self):
        """Re-attaching must NOT overwrite a row a user has customised."""
        self.client.login(username='owner', password='pw')
        fi = FacilityIntervention.objects.get(
            facility=self.facility, intervention=self.intervention,
        )
        fi.implementation_cost = Decimal('99999')
        fi.cost_source = 'USER'
        fi.save()

        response = self.client.post(
            f'/facilities/{self.facility.id}/interventions/{self.intervention.id}/attach/'
        )
        self.assertEqual(response.status_code, 302)
        fi.refresh_from_db()
        self.assertEqual(fi.implementation_cost, Decimal('99999'),
                         'Re-attach must NOT overwrite user-customised costs')
        self.assertEqual(fi.cost_source, 'USER',
                         'Re-attach must preserve USER cost_source')

    def test_outsider_cannot_detach_from_someone_elses_facility(self):
        self.client.login(username='outsider', password='pw')
        response = self.client.post(
            f'/facilities/{self.facility.id}/interventions/{self.intervention.id}/detach/'
        )
        self.assertEqual(response.status_code, 404)
        self.assertTrue(
            FacilityIntervention.objects.filter(
                facility=self.facility, intervention=self.intervention,
            ).exists(),
            'Outsider must not be able to detach from another user\'s facility'
        )

    def test_get_is_not_allowed_for_detach(self):
        """Detach must be POST-only to prevent CSRF and link-based mistakes."""
        self.client.login(username='owner', password='pw')
        response = self.client.get(
            f'/facilities/{self.facility.id}/interventions/{self.intervention.id}/detach/'
        )
        self.assertEqual(response.status_code, 405)

    def test_toggle_flips_attached_state(self):
        """The unified toggle endpoint must flip on→off→on cleanly."""
        self.client.login(username='owner', password='pw')
        # Start attached (setUpTestData seeded everything)
        self.assertTrue(FacilityIntervention.objects.filter(
            facility=self.facility, intervention=self.intervention).exists())

        # First toggle → detach
        self.client.post(
            f'/facilities/{self.facility.id}/interventions/{self.intervention.id}/toggle/'
        )
        self.assertFalse(FacilityIntervention.objects.filter(
            facility=self.facility, intervention=self.intervention).exists())

        # Second toggle → re-attach with library defaults
        self.client.post(
            f'/facilities/{self.facility.id}/interventions/{self.intervention.id}/toggle/'
        )
        self.assertTrue(FacilityIntervention.objects.filter(
            facility=self.facility, intervention=self.intervention).exists())

    def test_toggle_outsider_blocked(self):
        """Cross-facility toggle attempts must 404 (same as attach/detach)."""
        self.client.login(username='outsider', password='pw')
        response = self.client.post(
            f'/facilities/{self.facility.id}/interventions/{self.intervention.id}/toggle/'
        )
        self.assertEqual(response.status_code, 404)

    def test_bulk_detach_removes_everything(self):
        self.client.login(username='owner', password='pw')
        before = FacilityIntervention.objects.filter(facility=self.facility).count()
        self.assertGreater(before, 0, 'Sanity: facility starts with interventions attached')
        response = self.client.post(
            f'/facilities/{self.facility.id}/interventions/detach-all/'
        )
        self.assertEqual(response.status_code, 302)
        after = FacilityIntervention.objects.filter(facility=self.facility).count()
        self.assertEqual(after, 0, 'Detach-all must remove every FacilityIntervention row')

    def test_bulk_attach_adds_full_library(self):
        self.client.login(username='owner', password='pw')
        # Start from empty
        FacilityIntervention.objects.filter(facility=self.facility).delete()
        response = self.client.post(
            f'/facilities/{self.facility.id}/interventions/attach-all/'
        )
        self.assertEqual(response.status_code, 302)
        after = FacilityIntervention.objects.filter(facility=self.facility).count()
        self.assertEqual(after, Intervention.objects.count(),
                         'Attach-all must attach exactly the full library')

    def test_bulk_attach_preserves_custom_costs(self):
        """Attach-all must not clobber a row a user has customised."""
        self.client.login(username='owner', password='pw')
        fi = FacilityIntervention.objects.filter(facility=self.facility).first()
        fi.implementation_cost = Decimal('88888')
        fi.cost_source = 'USER'
        fi.save()
        self.client.post(f'/facilities/{self.facility.id}/interventions/attach-all/')
        fi.refresh_from_db()
        self.assertEqual(fi.implementation_cost, Decimal('88888'),
                         'Attach-all must not overwrite user-customised costs')

    def test_bulk_endpoints_are_post_only(self):
        self.client.login(username='owner', password='pw')
        self.assertEqual(
            self.client.get(f'/facilities/{self.facility.id}/interventions/detach-all/').status_code,
            405)
        self.assertEqual(
            self.client.get(f'/facilities/{self.facility.id}/interventions/attach-all/').status_code,
            405)

    def test_facility_detail_renders_unified_intervention_rows(self):
        """
        The new toggle UI passes `intervention_rows` (one per library
        intervention with is_attached flag). Must render with a form-switch
        per row and a CSRF token in each toggle form.
        """
        self.client.login(username='owner', password='pw')
        response = self.client.get(f'/facilities/{self.facility.id}/')
        self.assertEqual(response.status_code, 200)
        body = response.content.decode()
        # All library rows should appear, attached or not.
        n_library = Intervention.objects.count()
        n_switches = body.count('form-check-input')
        self.assertGreaterEqual(
            n_switches, n_library,
            f'Expected one toggle switch per library intervention ({n_library}); '
            f'got {n_switches} on the page.',
        )


class OptimizationResultsRenderTest(TestCase):
    """
    Production 500 on /optimization-results/<id>/ (2026-05-21): the
    _results_table.html partial used `{% for sdg in r.sdg_goals.split:"," %}`,
    which is invalid Django template syntax — Django's template language
    cannot call str methods with arguments. The compiled template raised
    TemplateSyntaxError on first GET, taking down the whole results page.

    This test exists to make any future "split-with-arg" mistake fail
    immediately in CI rather than silently in production.
    """

    @classmethod
    def setUpTestData(cls):
        from appname.models import OptimizationScenario, OptimizationResult
        call_command('sync_interventions', stdout=StringIO())
        cls.user = User.objects.create_user('jay', 'jay@example.com', 'pw')
        cls.facility = Facility.objects.create(
            code_name='RENDER_FAC',
            display_name='Render Test Facility',
            country='KE',
            facility_type='district_hospital',
            created_by=cls.user,
        )
        cls.scenario = OptimizationScenario.objects.create(
            facility=cls.facility,
            name='Render Test',
            budget=Decimal('50000'),
            target_reduction=Decimal('25'),
        )
        intervention = Intervention.objects.first()
        OptimizationResult.objects.create(
            scenario=cls.scenario,
            intervention=intervention,
            priority=1,
            expected_roi=Decimal('15'),
            emission_reduction=Decimal('10'),
            implementation_cost=Decimal('1000'),
            annual_savings=Decimal('500'),
            payback_months=24,
        )

    def test_results_page_renders_with_db_fallback_path(self):
        """No session data — view falls back to persisted OptimizationResult rows."""
        self.client.login(username='jay', password='pw')
        response = self.client.get(f'/optimization-results/{self.scenario.id}/')
        self.assertEqual(
            response.status_code, 200,
            f'Expected 200, got {response.status_code} — likely a TemplateSyntaxError regression',
        )
        # SDG badges should actually render — verifies the split filter works.
        # Default intervention #1 has sdg_goals like "7,13".
        self.assertIn(b'SDG', response.content)

    def test_results_page_handles_empty_sdg_goals(self):
        """An intervention with no SDG goals must render — not a UnicodeDecodeError, not a 500."""
        from appname.models import OptimizationResult
        intervention = Intervention.objects.create(
            code_name='TEST_NO_SDG',
            display_name='No-SDG Test Intervention',
            sdg_goals='',
            emission_reduction_percentage=Decimal('5'),
        )
        OptimizationResult.objects.create(
            scenario=self.scenario,
            intervention=intervention,
            priority=99,
            expected_roi=Decimal('10'),
            emission_reduction=Decimal('5'),
            implementation_cost=Decimal('500'),
            annual_savings=Decimal('100'),
            payback_months=60,
        )
        self.client.login(username='jay', password='pw')
        response = self.client.get(f'/optimization-results/{self.scenario.id}/')
        self.assertEqual(response.status_code, 200)


class OptimiseDoesNotDuplicateEmissionsTest(TestCase):
    """
    Production data corruption (2026-05-21): the optimize_interventions view
    used to unconditionally create a new EmissionData row from the form on
    POST. Because the form was pre-filled with the latest values, simply
    clicking "Run optimisation" without editing anything doubled the
    facility's baseline emissions. A second click tripled them, etc.

    The fix is one line — `if emission_form.has_changed():` around the
    create. This test guards it.
    """

    @classmethod
    def setUpTestData(cls):
        call_command('sync_interventions', stdout=StringIO())
        cls.user = User.objects.create_user('eve', 'eve@example.com', 'pw')
        cls.facility = Facility.objects.create(
            code_name='EVE_FAC',
            display_name='Eve Hospital',
            country='KE',
            facility_type='district_hospital',
            created_by=cls.user,
        )
        cls.source = EmissionSource.objects.create(
            facility=cls.facility,
            code_name='EVE_BASELINE',
            display_name='Eve baseline',
        )
        EmissionData.objects.create(
            emission_source=cls.source,
            date='2026-01-01',
            grid_electricity=Decimal('500000'),
        )

    def _post_optimise(self, **overrides):
        """POST the optimise form with the current baseline values unchanged."""
        # All emission fields must be present; default to the existing baseline.
        payload = {
            'name': 'Repeat-click test',
            'mode': 'budget',
            'budget': '50000',
            'date': '2026-01-01',
            'grid_electricity': '500000',
            'grid_gas': '0',
            'bottled_gas': '0',
            'liquid_fuel': '0',
            'vehicle_fuel_owned': '0',
            'business_travel': '0',
            'anaesthetic_gases': '0',
            'refrigeration_gases': '0',
            'waste_management': '0',
            'medical_inhalers': '0',
            'contractor_logistics': '0',
        }
        payload.update(overrides)
        self.client.login(username='eve', password='pw')
        return self.client.post(f'/optimize/{self.facility.id}/', payload)

    def test_unchanged_form_does_not_create_duplicate_emission_record(self):
        before = EmissionData.objects.filter(emission_source=self.source).count()
        self.assertEqual(before, 1, 'Sanity: setUpTestData created exactly one row')
        response = self._post_optimise()
        self.assertIn(response.status_code, (200, 302),
                      f'Optimise POST failed: {response.status_code}')
        after = EmissionData.objects.filter(emission_source=self.source).count()
        self.assertEqual(
            after, 1,
            'Re-running optimise with unchanged values must NOT create a duplicate '
            'EmissionData row — that was the silent doubling bug.',
        )

    def test_changed_form_creates_a_new_snapshot(self):
        """A genuine update — different kWh value — should be recorded."""
        before = EmissionData.objects.filter(emission_source=self.source).count()
        response = self._post_optimise(grid_electricity='600000')
        self.assertIn(response.status_code, (200, 302))
        after = EmissionData.objects.filter(emission_source=self.source).count()
        self.assertEqual(after, before + 1,
                         'A real edit (500000→600000) must be recorded as a new snapshot')


class HomeScopeTest(TestCase):
    """
    Home page used to show platform-wide counts to logged-in users,
    silently contradicting the user-scoped Dashboard. Now it scopes
    counts to the authenticated user.
    """

    @classmethod
    def setUpTestData(cls):
        call_command('sync_interventions', stdout=StringIO())
        cls.alice = User.objects.create_user('alice', 'alice@example.com', 'pw')
        cls.bob = User.objects.create_user('bob', 'bob@example.com', 'pw')
        # Alice has one facility; Bob has two. Home should show 1 to Alice,
        # 2 to Bob, and 3 to an anonymous visitor.
        Facility.objects.create(
            code_name='ALICE_1', display_name='Alice Hospital', country='ZA',
            facility_type='district_hospital', created_by=cls.alice,
        )
        Facility.objects.create(
            code_name='BOB_1', display_name='Bob Hospital', country='KE',
            facility_type='district_hospital', created_by=cls.bob,
        )
        Facility.objects.create(
            code_name='BOB_2', display_name='Bob Clinic', country='KE',
            facility_type='health_centre', created_by=cls.bob,
        )

    def test_anonymous_sees_platform_wide_count(self):
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['facility_count'], 3)
        self.assertFalse(response.context['is_user_scope'])

    def test_alice_sees_only_her_facility(self):
        self.client.login(username='alice', password='pw')
        response = self.client.get('/')
        self.assertEqual(response.context['facility_count'], 1)
        self.assertTrue(response.context['is_user_scope'])

    def test_bob_sees_only_his_two_facilities(self):
        self.client.login(username='bob', password='pw')
        response = self.client.get('/')
        self.assertEqual(response.context['facility_count'], 2)
        self.assertTrue(response.context['is_user_scope'])


class DashboardCounterConsistencyTest(TestCase):
    """
    Production QA 2026-05-24: Dashboard showed "Linked interventions: 0"
    while Home/Facilities/Interventions portfolio all showed 63 for the
    same user. Root causes:

      (a) Dashboard filtered FacilityIntervention by status='In Progress',
          but seeded rows are status='Planned' with no UI transition →
          always 0.
      (b) Dashboard summed implementation_cost only; Interventions portfolio
          summed implementation + maintenance, producing a $700K gap.

    This test pins both: linked-interventions count and total-investment
    sum on the Dashboard must match the Interventions portfolio's
    aggregates exactly (same user, same DB).
    """

    @classmethod
    def setUpTestData(cls):
        call_command('sync_interventions', stdout=StringIO())
        cls.user = User.objects.create_user('dash', 'dash@example.com', 'pw')
        cls.facility = Facility.objects.create(
            code_name='DASH_FAC',
            display_name='Dashboard Test Hospital',
            country='ZA',
            facility_type='district_hospital',
            created_by=cls.user,
        )
        from appname.views import _seed_facility_interventions
        _seed_facility_interventions(cls.facility)
        # Mark a couple of FacilityInterventions' parent Intervention status
        # variations so we exercise the "no status filter" path properly.
        Intervention.objects.filter(id__in=Intervention.objects.values_list('id', flat=True)[:3]).update(status='In Progress')

    def test_dashboard_linked_count_matches_interventions_portfolio(self):
        self.client.login(username='dash', password='pw')
        dash = self.client.get('/dashboard/')
        portfolio = self.client.get('/interventions/')
        self.assertEqual(dash.status_code, 200)
        self.assertEqual(portfolio.status_code, 200)

        # Dashboard's `active_interventions` must equal portfolio's count.
        dash_count = dash.context['active_interventions']
        portfolio_count = portfolio.context['summary']['count']
        self.assertEqual(
            dash_count, portfolio_count,
            f'Dashboard ({dash_count}) and Interventions portfolio ({portfolio_count}) '
            f'should report the same linked-intervention count',
        )

    def test_dashboard_total_investment_matches_interventions_portfolio(self):
        self.client.login(username='dash', password='pw')
        dash = self.client.get('/dashboard/')
        portfolio = self.client.get('/interventions/')
        dash_invest = dash.context['total_investment']
        portfolio_invest = portfolio.context['summary']['total_investment']
        self.assertEqual(
            dash_invest, portfolio_invest,
            f'Dashboard ({dash_invest}) and Interventions portfolio ({portfolio_invest}) '
            f'should report the same total investment (impl + maint)',
        )


class DeleteFacilityAndScenarioTest(TestCase):
    """
    User feedback (2026-06-10): "it's a one-way street — you add a facility
    and can never take it off again." Facilities and scenarios are now
    deletable, with safety:
      - delete_facility requires the POST to include the facility's
        display_name typed exactly (confirm_name) — a mis-click can't
        destroy data. Cascades to emission records, intervention links,
        scenarios, and results via Django's collector.
      - delete_scenario is a plain confirm (scenarios are cheap snapshots).
    """

    @classmethod
    def setUpTestData(cls):
        call_command('sync_interventions', stdout=StringIO())
        cls.owner = User.objects.create_user('delowner', 'del@example.com', 'pw')
        cls.outsider = User.objects.create_user('deloutsider', 'out@example.com', 'pw')
        cls.facility = Facility.objects.create(
            code_name='DEL_FAC', display_name='Deletable Hospital', country='ZW',
            facility_type='district_hospital', created_by=cls.owner,
        )
        source = EmissionSource.objects.create(
            facility=cls.facility, code_name='DEL_BASE', display_name='Del baseline',
        )
        EmissionData.objects.create(
            emission_source=source, date='2026-01-01', grid_electricity=Decimal('10000'),
        )
        from appname.views import _seed_facility_interventions
        _seed_facility_interventions(cls.facility)
        cls.scenario = OptimizationScenario.objects.create(
            facility=cls.facility, name='Del scenario', budget=Decimal('1000'),
        )

    def test_delete_requires_exact_name_match(self):
        self.client.login(username='delowner', password='pw')
        response = self.client.post(
            f'/facilities/{self.facility.id}/delete/',
            {'confirm_name': 'Wrong Name'},
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Facility.objects.filter(id=self.facility.id).exists(),
                        'Facility must survive a mismatched confirm_name')

    def test_delete_with_correct_name_cascades_everything(self):
        self.client.login(username='delowner', password='pw')
        fid = self.facility.id
        response = self.client.post(
            f'/facilities/{fid}/delete/',
            {'confirm_name': 'Deletable Hospital'},
        )
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Facility.objects.filter(id=fid).exists())
        self.assertFalse(FacilityIntervention.objects.filter(facility_id=fid).exists())
        self.assertFalse(EmissionData.objects.filter(emission_source__facility_id=fid).exists())
        self.assertFalse(OptimizationScenario.objects.filter(facility_id=fid).exists())

    def test_outsider_cannot_delete(self):
        self.client.login(username='deloutsider', password='pw')
        response = self.client.post(
            f'/facilities/{self.facility.id}/delete/',
            {'confirm_name': 'Deletable Hospital'},
        )
        self.assertEqual(response.status_code, 404)
        self.assertTrue(Facility.objects.filter(id=self.facility.id).exists())

    def test_delete_facility_is_post_only(self):
        self.client.login(username='delowner', password='pw')
        response = self.client.get(f'/facilities/{self.facility.id}/delete/')
        self.assertEqual(response.status_code, 405)

    def test_delete_scenario(self):
        self.client.login(username='delowner', password='pw')
        sid = self.scenario.id
        response = self.client.post(f'/scenarios/{sid}/delete/')
        self.assertEqual(response.status_code, 302)
        self.assertFalse(OptimizationScenario.objects.filter(id=sid).exists())
        # The facility itself is untouched
        self.assertTrue(Facility.objects.filter(id=self.facility.id).exists())

    def test_outsider_cannot_delete_scenario(self):
        self.client.login(username='deloutsider', password='pw')
        response = self.client.post(f'/scenarios/{self.scenario.id}/delete/')
        self.assertEqual(response.status_code, 404)
        self.assertTrue(OptimizationScenario.objects.filter(id=self.scenario.id).exists())


class EmissionEntryUnitsGuidanceTest(TestCase):
    """
    Incident (2026-05, reported by Jetina): the manual-entry card on
    /upload/emissions/ instructed users to "Enter tCO₂e values directly.
    All figures in tCO₂e per year" — but the backend stores RAW activity
    units (kWh, litres, kg…) and multiplies by carbon factors at read time.
    Users who followed the instructions got double-converted garbage, and
    concluded (reasonably) that the tool wasn't applying factors at all.

    These tests pin the corrected guidance: raw-units copy, per-field unit
    labels on BOTH emission forms, and the factors JSON that powers the
    live tCO₂e preview.
    """

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user('units', 'units@example.com', 'pw')
        cls.facility = Facility.objects.create(
            code_name='UNIT_FAC', display_name='Units Hospital', country='KE',
            facility_type='district_hospital', created_by=cls.user,
        )

    def test_manual_entry_page_says_raw_units_not_tco2e(self):
        self.client.login(username='units', password='pw')
        response = self.client.get('/upload/emissions/')
        body = response.content.decode()
        self.assertNotIn('Enter emission values directly. All figures in tCO₂e per year', body,
                         'The wrong "enter tCO₂e directly" instruction is back')
        self.assertIn('raw activity data', body)
        # Live preview machinery present
        self.assertIn('emission-factors', body)
        self.assertIn('tco2e-preview', body)

    def test_factors_json_matches_modeling(self):
        """The preview must use the exact same factors as the backend."""
        from appname.views import _emission_factors_json
        from appname.modeling import EMISSION_FACTORS, ELECTRICITY_EF
        data = _emission_factors_json()
        self.assertEqual(data['electricity']['KE'], float(ELECTRICITY_EF['KE']))
        self.assertEqual(data['fields']['liquid_fuel'], float(EMISSION_FACTORS['liquid_fuel']))
        self.assertIsNone(data['fields']['grid_electricity'],
                          'grid_electricity is per-country, not a flat factor')

    def test_add_facility_tour_and_preview_use_raw_units(self):
        """
        Second round of the same incident (2026-06-10): the guided-tour
        overlay on add_facility still said "Enter annual tCO₂e figures"
        even after the upload page was fixed. The tour copy, the country
        help text, and the live preview must all reflect raw-units +
        automatic conversion.
        """
        self.client.login(username='units', password='pw')
        response = self.client.get('/add-facility/')
        body = response.content.decode()
        self.assertNotIn('Enter annual tCO₂e figures', body,
                         'The wrong tour instruction is back on add_facility')
        self.assertIn('RAW annual usage', body)
        # Country → factor linkage is explicit and the preview machinery loads
        self.assertIn('country-factor-note', body)
        self.assertIn('emission-factors', body)

    def test_both_emission_forms_share_unit_labels(self):
        """EmissionDataUpdateForm (optimise page) must carry the same
        unit-suffixed labels as EmissionDataForm — it used to render bare
        field names with no unit guidance at all."""
        from appname.forms import EmissionDataForm, EmissionDataUpdateForm
        f1, f2 = EmissionDataForm(), EmissionDataUpdateForm()
        self.assertEqual(f1.fields['grid_electricity'].label, 'Grid Electricity (kWh/yr)')
        self.assertEqual(f2.fields['grid_electricity'].label, 'Grid Electricity (kWh/yr)')
        for name in f1.fields:
            self.assertEqual(f1.fields[name].label, f2.fields[name].label,
                             f'Label mismatch between the two emission forms for {name}')


class MethodologyPageRigorTest(TestCase):
    """
    The methodology page is the tool's scientific-credibility surface. It
    must render the references (with the D3.7 DOI), the financial
    parameters, the optimisation-algorithm description, and the explicit
    assumptions/limitations section — and stay public (no login) so it can
    be cited.
    """

    def test_methodology_is_public(self):
        response = self.client.get('/methodology/')
        self.assertEqual(response.status_code, 200)

    def test_methodology_contains_scientific_sections(self):
        body = self.client.get('/methodology/').content.decode()
        for needle in [
            'Optimisation algorithm',
            'Assumptions &amp; limitations',
            'References',
            'Financial parameters',
            '10.5281/zenodo.12730527',   # D3.7 DOI
            'IPCC',
            'greedy knapsack',
        ]:
            self.assertIn(needle, body, f'Methodology page missing: {needle}')

    def test_references_carry_dois_or_urls(self):
        from appname.views import SCIENTIFIC_REFERENCES
        self.assertGreaterEqual(len(SCIENTIFIC_REFERENCES), 4)
        for ref in SCIENTIFIC_REFERENCES:
            self.assertTrue(ref.get('citation'))
            self.assertTrue(ref.get('doi') or ref.get('url'),
                            f'Reference {ref["key"]} has neither DOI nor URL')


class BudgetXorTargetTest(TestCase):
    """
    User feedback (2026-05-24, via Jetina): "you shouldn't have a scenario
    where you choose the budget AND the percentage of reduction — it should
    be one or the other." Previously the form required both, but the
    optimiser silently ignored target_reduction entirely.

    Now: OptimizationScenarioForm has a `mode` radio. Budget mode nulls the
    target; target mode nulls the budget; the optimiser honours whichever
    is set (budget = maximise reduction within cap; target = cheapest set
    achieving the goal).
    """

    @classmethod
    def setUpTestData(cls):
        call_command('sync_interventions', stdout=StringIO())
        cls.user = User.objects.create_user('xor', 'xor@example.com', 'pw')
        cls.facility = Facility.objects.create(
            code_name='XOR_FAC', display_name='Xor Hospital', country='ZW',
            facility_type='district_hospital', created_by=cls.user,
        )
        cls.source = EmissionSource.objects.create(
            facility=cls.facility, code_name='XOR_BASE', display_name='Xor baseline',
        )
        EmissionData.objects.create(
            emission_source=cls.source, date='2026-01-01',
            grid_electricity=Decimal('500000'),
        )
        from appname.views import _seed_facility_interventions
        _seed_facility_interventions(cls.facility)

    # ── Form validation ────────────────────────────────────────────────

    def test_budget_mode_clears_target(self):
        from appname.forms import OptimizationScenarioForm
        form = OptimizationScenarioForm({
            'name': 'B', 'mode': 'budget', 'budget': '50000', 'target_reduction': '25',
        })
        self.assertTrue(form.is_valid(), form.errors)
        self.assertIsNone(form.cleaned_data['target_reduction'],
                          'Budget mode must null out target_reduction')

    def test_target_mode_clears_budget(self):
        from appname.forms import OptimizationScenarioForm
        form = OptimizationScenarioForm({
            'name': 'T', 'mode': 'target', 'budget': '50000', 'target_reduction': '25',
        })
        self.assertTrue(form.is_valid(), form.errors)
        self.assertIsNone(form.cleaned_data['budget'],
                          'Target mode must null out budget')

    def test_budget_mode_requires_budget(self):
        from appname.forms import OptimizationScenarioForm
        form = OptimizationScenarioForm({'name': 'B', 'mode': 'budget'})
        self.assertFalse(form.is_valid())
        self.assertIn('budget', form.errors)

    def test_target_mode_requires_target(self):
        from appname.forms import OptimizationScenarioForm
        form = OptimizationScenarioForm({'name': 'T', 'mode': 'target'})
        self.assertFalse(form.is_valid())
        self.assertIn('target_reduction', form.errors)

    # ── Optimizer target mode ──────────────────────────────────────────

    def test_optimizer_target_mode_stops_at_goal(self):
        from appname.modeling import CarbomicaOptimizer
        fis = FacilityIntervention.objects.select_related('facility', 'intervention').filter(
            facility=self.facility)
        opt = CarbomicaOptimizer(
            facility_interventions=fis,
            total_baseline_emissions=Decimal('1000'),
            target_pct=Decimal('10'),
            category_baselines={'grid_electricity': Decimal('1000')},
        )
        scenarios = opt.run_all_scenarios()
        summary = scenarios['optimised']['summary']
        self.assertGreaterEqual(
            summary['pct_of_baseline'], Decimal('10'),
            'Target mode must select interventions until the goal is reached',
        )
        # And it must NOT select everything — cheapest-path means stopping early.
        self.assertLess(
            summary['count'], fis.count(),
            'Target mode should stop once the goal is met, not run the full library',
        )
        self.assertIsNone(summary['budget_remaining'],
                          'budget_remaining is meaningless in target mode')
        self.assertTrue(summary['target_met'])

    def test_optimizer_requires_exactly_one_constraint(self):
        from appname.modeling import CarbomicaOptimizer
        with self.assertRaises(ValueError):
            CarbomicaOptimizer(
                facility_interventions=[],
                total_baseline_emissions=Decimal('1000'),
            )

    # ── End-to-end: target-mode POST renders results ────────────────────

    def test_target_mode_post_runs_and_renders(self):
        self.client.login(username='xor', password='pw')
        payload = {
            'name': 'Target run', 'mode': 'target', 'target_reduction': '20',
            'date': '2026-01-01',
            'grid_electricity': '500000', 'grid_gas': '0', 'bottled_gas': '0',
            'liquid_fuel': '0', 'vehicle_fuel_owned': '0', 'business_travel': '0',
            'anaesthetic_gases': '0', 'refrigeration_gases': '0',
            'waste_management': '0', 'medical_inhalers': '0', 'contractor_logistics': '0',
        }
        resp = self.client.post(f'/optimize/{self.facility.id}/', payload, follow=True)
        self.assertEqual(resp.status_code, 200)
        scenario = OptimizationScenario.objects.get(name='Target run')
        self.assertIsNone(scenario.budget)
        self.assertEqual(scenario.target_reduction, Decimal('20'))
        # Results page renders with the target constraint shown
        self.assertIn(b'reduction target', resp.content)


class PipelineStatusAggregationTest(TestCase):
    """
    Production QA 2026-05-24: Pipeline status widget rendered one row per
    FacilityIntervention ("Planned — 1 projects", repeated 63 times) instead
    of one row per status ("Planned: 63"). Root cause was a classic Django
    ORM trap: `qs.values('intervention__status').annotate(count=...)` was
    called on a QuerySet that already had `.order_by(facility__display_name,
    intervention__display_name)`. Django then appends the order_by columns
    to the GROUP BY clause, producing one row per unique (status, facility,
    intervention) tuple — i.e. one row per FacilityIntervention.

    Fix: insert `.order_by()` (empty) before `.values()` to clear the
    inherited ordering. This test pins that fix in place.
    """

    @classmethod
    def setUpTestData(cls):
        call_command('sync_interventions', stdout=StringIO())
        cls.user = User.objects.create_user('pipe', 'pipe@example.com', 'pw')
        cls.facility = Facility.objects.create(
            code_name='PIPE_FAC',
            display_name='Pipeline Test Hospital',
            country='KE',
            facility_type='district_hospital',
            created_by=cls.user,
        )
        from appname.views import _seed_facility_interventions
        _seed_facility_interventions(cls.facility)

    def test_status_breakdown_aggregates_by_status_not_by_intervention(self):
        self.client.login(username='pipe', password='pw')
        response = self.client.get('/interventions/')
        breakdown = response.context['status_breakdown']

        # Every (FacilityIntervention) row is auto-seeded with parent
        # Intervention.status='Planned' by default. So the breakdown should
        # have AT MOST as many entries as distinct status values exist —
        # which for fresh data is exactly 1 ("Planned").
        distinct_statuses = {entry['status'] for entry in breakdown}
        self.assertLessEqual(
            len(breakdown), len(distinct_statuses) + 1,
            f'Pipeline status breakdown over-fragmented: {len(breakdown)} rows '
            f'for {len(distinct_statuses)} distinct statuses — GROUP BY regression. '
            f'Rows: {breakdown}',
        )

        # And the total count across statuses must equal total FacilityInterventions.
        total_via_breakdown = sum(entry['count'] for entry in breakdown)
        self.assertEqual(
            total_via_breakdown, response.context['summary']['count'],
            f'Status breakdown total ({total_via_breakdown}) does not match '
            f'portfolio count ({response.context["summary"]["count"]})',
        )


class CreateCustomInterventionTest(TestCase):
    """
    Production 404 on the "Add to library" button (reported 2026-05-21):
    upload_interventions had two `if request.method == 'POST'` blocks,
    and the first one called get_object_or_404(_user_facilities, id=None)
    before checking the request's `action` field. The custom-intervention
    form has no `facility` field by design — it adds to the global library —
    so every click 404'd before reaching the create_custom dispatch.

    This test pins the fix in place: POST with action=create_custom MUST
    succeed without a `facility` in the payload, AND must add the row
    to the Intervention library.
    """

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user('janet', 'janet@example.com', 'pw')

    def test_create_custom_intervention_without_facility(self):
        self.client.login(username='janet', password='pw')
        before = Intervention.objects.filter(code_name__startswith='CUSTOM_').count()
        response = self.client.post('/upload/interventions/', {
            'action': 'create_custom',
            'custom_name': 'Biogas digester',
            'custom_target_category': 'liquid_fuel',
            'custom_reduction_pct': '15',
        })
        self.assertEqual(
            response.status_code, 302,
            f'Expected 302 redirect, got {response.status_code} — "Add to library" 404 regression',
        )
        after = Intervention.objects.filter(code_name__startswith='CUSTOM_').count()
        self.assertEqual(after, before + 1, 'Custom intervention row was not created')
        new_row = Intervention.objects.get(code_name='CUSTOM_BIOGAS-DIGESTER')
        self.assertEqual(new_row.display_name, 'Biogas digester')
        self.assertEqual(new_row.emission_reduction_percentage, Decimal('15'))

    def test_blank_name_rejected_with_user_message(self):
        self.client.login(username='janet', password='pw')
        response = self.client.post('/upload/interventions/', {
            'action': 'create_custom',
            'custom_name': '   ',  # whitespace only
        }, follow=True)
        self.assertEqual(response.status_code, 200)
        msgs = [str(m) for m in response.context['messages']]
        self.assertTrue(
            any('name' in m.lower() for m in msgs),
            f'Expected a user-facing "name required" message, got {msgs}',
        )

    def test_success_alert_renders_exactly_once(self):
        """
        Bootstrap-with-duplicate-alerts bug: upload_interventions.html used
        to repeat the messages block already present in base.html, which
        meant Bootstrap initialised two alert components on the same DOM
        and one would silently dismiss the other. The success flash never
        rendered visibly in production. After removing the duplicate the
        success alert must appear exactly once.
        """
        self.client.login(username='janet', password='pw')
        response = self.client.post('/upload/interventions/', {
            'action': 'create_custom',
            'custom_name': 'Duplicate-Alert Regression',
        }, follow=True)
        body = response.content.decode()
        self.assertEqual(body.count('alert-success'), 1,
                         f'Expected exactly one alert-success on the page, got {body.count("alert-success")}')

    def test_category_dropdown_uses_human_labels_not_run_together(self):
        """
        Cosmetic regression: target-category dropdown used to render
        "GridElectricity" (no space) because the template did
        `{{ field|title|cut:"_" }}` — `cut` removes the underscore
        without inserting a space. Now we pass CATEGORY_LABELS from the
        view so the template has nothing to munge.
        """
        self.client.login(username='janet', password='pw')
        response = self.client.get('/upload/interventions/')
        body = response.content.decode()
        # Positive: the human label appears
        self.assertIn('>Grid Electricity</option>', body,
                      'Dropdown should render "Grid Electricity" with a space')
        # Negative: no run-together regression
        self.assertNotIn('GridElectricity', body,
                         'Run-together label leaked back in — dropdown regression')


class SplitFilterTest(TestCase):
    """Unit coverage for the carbomica_extras.split filter."""

    def test_csv_string_split_into_list(self):
        from appname.templatetags.carbomica_extras import split_filter
        self.assertEqual(split_filter('7,13'), ['7', '13'])

    def test_strips_whitespace_around_tokens(self):
        from appname.templatetags.carbomica_extras import split_filter
        self.assertEqual(split_filter(' 7 , 13 '), ['7', '13'])

    def test_drops_empty_tokens(self):
        from appname.templatetags.carbomica_extras import split_filter
        self.assertEqual(split_filter('7,,13,'), ['7', '13'])

    def test_empty_string_returns_empty_list(self):
        from appname.templatetags.carbomica_extras import split_filter
        self.assertEqual(split_filter(''), [])
        self.assertEqual(split_filter(None), [])

    def test_custom_separator(self):
        from appname.templatetags.carbomica_extras import split_filter
        self.assertEqual(split_filter('7|13|17', '|'), ['7', '13', '17'])
