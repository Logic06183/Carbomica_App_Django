"""
Verdex test suite.

Covers:
  1. INTERVENTION_LIBRARY integrity (all entries well-formed)
  2. sync_interventions management command (correct DB state)
  3. compute_tco2e / sum_tco2e emission calculations
  4. CarbomicaOptimizer — three-scenario analysis
"""
from datetime import date
from decimal import Decimal

from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import TestCase
from io import StringIO

from appname.models import (
    Facility, EmissionData, EmissionSource,
    Intervention, FacilityIntervention, Organisation, ProcurementLine,
    Project, ProjectSite, TravelJourney, CreditPurchase,
)
from appname.modeling import (
    INTERVENTION_LIBRARY,
    EMISSION_FACTORS, ELECTRICITY_EF,
    compute_tco2e, sum_tco2e,
    CarbomicaOptimizer,
    PROCUREMENT_CATEGORIES, procurement_breakdown, match_procurement_category,
    project_footprint, AIR_FACTORS, SURFACE_FACTORS, journey_tco2e,
    journey_policy_flags, credit_position, award_checklist,
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
#    (office-hours design 2026-04-27 — "Tinah Unblocker")
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
        self.client.login(username='tinah', password='pw')
        intervention_count = Intervention.objects.count()
        self.assertGreater(intervention_count, 0, 'Sanity: sync_interventions populated the library')

        response = self.client.post('/add-facility/', {
            'code_name': 'TINAH_FAC',
            'display_name': 'Tinah Test Hospital',
            'sector': 'clinical',
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


class OptimizationResultsPageTest(TestCase):
    """Regression: the results page must render on both the session path (fresh
    optimise POST) and the DB-fallback path (session expired). It previously
    500'd on a TemplateSyntaxError in _results_table.html (sdg_goals.split)."""

    @classmethod
    def setUpTestData(cls):
        call_command('sync_interventions', stdout=StringIO())
        cls.user = User.objects.create_user('opter', 'opter@example.com', 'pw')

    def test_results_page_renders_on_both_paths(self):
        self.client.force_login(self.user)
        self.client.post('/add-facility/', {
            'display_name': 'Results Test Facility', 'code_name': 'RES_FAC',
            'sector': 'research', 'country': 'ZW', 'facility_type': 'university_lab',
            'grid_electricity': '320', 'grid_gas': '45', 'bottled_gas': '6',
            'liquid_fuel': '28', 'vehicle_fuel_owned': '22', 'business_travel': '85',
            'anaesthetic_gases': '0', 'refrigeration_gases': '14',
            'waste_management': '12', 'medical_inhalers': '0', 'contractor_logistics': '18',
        })
        facility = Facility.objects.get(code_name='RES_FAC')

        response = self.client.post(f'/optimize/{facility.id}/', {
            'name': 'Regression scenario', 'budget': '50000', 'target_reduction': '30',
            'grid_electricity': '320', 'grid_gas': '45', 'bottled_gas': '6',
            'liquid_fuel': '28', 'vehicle_fuel_owned': '22', 'business_travel': '85',
            'anaesthetic_gases': '0', 'refrigeration_gases': '14',
            'waste_management': '12', 'medical_inhalers': '0', 'contractor_logistics': '18',
        })
        self.assertEqual(response.status_code, 302)
        scenario_id = int(response['Location'].rstrip('/').rsplit('/', 1)[-1])

        # Session path: same client that ran the optimisation.
        response = self.client.get(f'/optimization-results/{scenario_id}/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'rounded-pill')  # SDG badges rendered

        # DB-fallback path: fresh session, no cached scenarios.
        from django.test import Client
        fresh = Client()
        fresh.force_login(self.user)
        response = fresh.get(f'/optimization-results/{scenario_id}/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'rounded-pill')


class ReductionDrawdownTest(TestCase):
    """Regression: multiple interventions targeting the same category must not
    each claim the full category baseline. Total scenario reduction must never
    exceed the facility baseline (previously reported 324% of baseline)."""

    @classmethod
    def setUpTestData(cls):
        call_command('sync_interventions', stdout=StringIO())
        cls.facility = Facility.objects.create(
            code_name='DRAWDOWN_FAC', display_name='Drawdown Facility', country='ZA',
        )

    def _fi(self, code_name, impl=0, maint=0):
        return FacilityIntervention.objects.create(
            facility=self.facility,
            intervention=Intervention.objects.get(code_name=code_name),
            implementation_cost=Decimal(str(impl)),
            maintenance_cost=Decimal(str(maint)),
        )

    def test_same_category_interventions_share_the_baseline(self):
        # Two ~99% refrigerant swaps against a 25 tCO2e refrigerant baseline:
        # naive maths would claim ~49.5 tCO2e; drawdown must keep the sum < 25.
        fis = [self._fi('REFRIG_R134A_R1234YF'), self._fi('REFRIG_R22_R290')]
        optimizer = CarbomicaOptimizer(
            facility_interventions=fis, budget=Decimal('1000'),
            total_baseline_emissions=Decimal('30'),
            category_baselines={'refrigeration_gases': Decimal('25')},
        )
        for scenario in optimizer.run_all_scenarios().values():
            total = sum(r['emission_reduction'] for r in scenario['results'])
            self.assertLess(total, Decimal('25'),
                            'Summed reductions exceed the category baseline — double-counting is back')
            self.assertLessEqual(scenario['summary']['pct_of_baseline'], Decimal('100'))

    def test_full_library_never_exceeds_baseline(self):
        from appname.views import _seed_facility_interventions
        _seed_facility_interventions(self.facility)
        fis = FacilityIntervention.objects.filter(facility=self.facility).select_related('intervention')
        baselines = {
            'grid_electricity': Decimal('10'), 'refrigeration_gases': Decimal('25'),
            'waste_management': Decimal('5'), 'anaesthetic_gases': Decimal('2'),
        }
        optimizer = CarbomicaOptimizer(
            facility_interventions=fis, budget=Decimal('1000000'),
            total_baseline_emissions=Decimal('42'), category_baselines=baselines,
        )
        scenarios = optimizer.run_all_scenarios()
        for name, scenario in scenarios.items():
            total = sum(r['emission_reduction'] for r in scenario['results'])
            self.assertLessEqual(total, Decimal('42'),
                                 f'{name}: reduction {total} exceeds the 42 tCO2e baseline')


class SectorCurationTest(TestCase):
    """Research facilities must not be attached clinical-only interventions
    (anaesthetics, inhalers, medical waste, incinerators, hospital laundry)."""

    @classmethod
    def setUpTestData(cls):
        call_command('sync_interventions', stdout=StringIO())

    def _attached_codes(self, sector):
        from appname.views import _seed_facility_interventions
        facility = Facility.objects.create(
            code_name=f'SECT_{sector.upper()}', display_name=f'{sector} site',
            country='ZA', sector=sector,
        )
        _seed_facility_interventions(facility)
        return set(
            FacilityIntervention.objects.filter(facility=facility)
            .values_list('intervention__code_name', flat=True)
        )

    def test_research_facility_excludes_clinical_only_interventions(self):
        codes = self._attached_codes('research')
        clinical_only = {'ANAES_ISO_SEVO', 'ANAES_NO_AVOID', 'INHALER_DPI', 'INHALER_SMI',
                         'LOW_GWP_ANAESTHETICS', 'DPI_INHALER_SWITCH', 'WASTE_SEGREGATION',
                         'INCINERATOR_TAM', 'EE_LAUNDRY'}
        self.assertFalse(codes & clinical_only,
                         f'Clinical-only interventions attached to research lab: {codes & clinical_only}')
        # Research-relevant Scope-3 interventions must be present.
        self.assertIn('VIRTUAL_FIRST_TRAVEL', codes)
        self.assertIn('GREEN_PROCUREMENT', codes)

    def test_clinical_facility_gets_full_library(self):
        codes = self._attached_codes('clinical')
        self.assertEqual(len(codes), Intervention.objects.count(),
                         'Clinical facilities should receive every intervention')


class ResearchCategoriesTest(TestCase):
    """flights (passenger-km) and lab_consumables (USD spend) must convert to tCO2e."""

    def test_new_categories_convert(self):
        from appname.modeling import compute_tco2e
        facility = Facility.objects.create(
            code_name='RES_CAT', display_name='Research Cat', country='ZA', sector='research')
        source = EmissionSource.objects.create(
            facility=facility, code_name='RES_CAT_SRC', display_name='src')
        data = EmissionData.objects.create(
            emission_source=source,
            flights=Decimal('100000'),        # 100k passenger-km
            lab_consumables=Decimal('200000'),  # $200k spend
        )
        result = compute_tco2e(data, country='ZA')
        self.assertEqual(result['flights'], Decimal('100000') * Decimal('0.00015'))   # 15 tCO2e
        self.assertEqual(result['lab_consumables'], Decimal('200000') * Decimal('0.0005'))  # 100 tCO2e
        self.assertEqual(result['total'], Decimal('115'))


class PageRenderRegressionTest(TestCase):
    """Every data-bearing page must render with a fully-populated research
    facility — catches template errors that only trigger with real data
    (the optimization-results 500 was exactly this class of bug)."""

    @classmethod
    def setUpTestData(cls):
        call_command('sync_interventions', stdout=StringIO())
        cls.user = User.objects.create_user('renderer', 'r@example.com', 'pw')

    def test_all_pages_render_with_populated_research_facility(self):
        self.client.force_login(self.user)
        self.client.post('/add-facility/', {
            'display_name': 'Wits Planetary Health Research Division', 'code_name': 'WITS_PHR',
            'sector': 'research', 'country': 'ZA', 'facility_type': 'university_lab',
            'grid_electricity': '185000', 'liquid_fuel': '2400', 'vehicle_fuel_owned': '5600',
            'business_travel': '38000', 'refrigeration_gases': '8', 'waste_management': '4',
            'contractor_logistics': '9000', 'flights': '420000', 'lab_consumables': '310000',
        })
        facility = Facility.objects.get(code_name='WITS_PHR')

        response = self.client.post(f'/optimize/{facility.id}/', {
            'name': 'Wits FY2026', 'budget': '60000', 'target_reduction': '30',
        })
        self.assertEqual(response.status_code, 302)
        scenario_id = int(response['Location'].rstrip('/').rsplit('/', 1)[-1])

        for path in ['/', '/dashboard/', '/facilities/', f'/facilities/{facility.id}/',
                     '/interventions/', '/organisation/', f'/optimize/{facility.id}/',
                     f'/optimization-results/{scenario_id}/', '/upload/emissions/',
                     '/add-facility/']:
            response = self.client.get(path)
            self.assertEqual(response.status_code, 200, f'{path} did not render')

        # Scope labelling visible on the facility profile
        response = self.client.get(f'/facilities/{facility.id}/')
        self.assertContains(response, 'Scope 2')
        self.assertContains(response, 'GHG Protocol totals')
        # Research-sector funder language present
        self.assertContains(response, 'Concordat')
        # Clinical-only interventions absent for a research division
        self.assertNotContains(response, 'Anaesthetic Switch')


class BaselineNotCumulativeTest(TestCase):
    """Regression: baselines must reflect the latest reporting period, not the
    sum of all historical records (which double-counted every prior period)."""

    @classmethod
    def setUpTestData(cls):
        call_command('sync_interventions', stdout=StringIO())
        cls.user = User.objects.create_user('cumul', 'c@example.com', 'pw')

    def test_second_optimisation_run_does_not_double_the_baseline(self):
        self.client.force_login(self.user)
        emissions = {'grid_electricity': '100000', 'flights': '200000'}
        self.client.post('/add-facility/', {
            'display_name': 'Baseline Facility', 'code_name': 'BASE_FAC',
            'sector': 'research', 'country': 'ZA', 'facility_type': 'university_lab',
            **emissions,
        })
        facility = Facility.objects.get(code_name='BASE_FAC')
        # ZA electricity 0.000928 * 100000 = 92.8; flights 0.00015 * 200000 = 30 → 122.8
        expected = Decimal('122.8')

        for run in (1, 2):   # second run re-posts the same figures (form pre-fill)
            r = self.client.post(f'/optimize/{facility.id}/', {
                'name': f'Run {run}', 'budget': '10000', 'target_reduction': '20',
                **emissions,
            })
            self.assertEqual(r.status_code, 302)
            scenario_id = int(r['Location'].rstrip('/').rsplit('/', 1)[-1])
            r = self.client.get(f'/optimization-results/{scenario_id}/')
            self.assertEqual(r.status_code, 200)

        from appname.models import OptimizationScenario
        scenario = OptimizationScenario.objects.get(name='Run 2')
        results = scenario.results.all()
        self.assertGreater(len(results), 0)
        total_reduction = sum(Decimal(str(res.emission_reduction)) for res in results)
        self.assertLessEqual(total_reduction, expected,
                             'Reductions exceed the single-period baseline — cumulative double-count is back')

    def test_dashboard_total_uses_latest_record_only(self):
        self.client.force_login(self.user)
        self.client.post('/add-facility/', {
            'display_name': 'Dash Facility', 'code_name': 'DASH_FAC',
            'sector': 'research', 'country': 'ZA', 'facility_type': 'university_lab',
            'grid_electricity': '100000',
        })
        facility = Facility.objects.get(code_name='DASH_FAC')
        # Second identical period via optimise re-post: dashboard total must not double.
        self.client.post(f'/optimize/{facility.id}/', {
            'name': 'Dash run', 'budget': '1000', 'target_reduction': '10',
            'grid_electricity': '100000',
        })
        r = self.client.get('/dashboard/')
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, '92.8')      # 100000 kWh * 0.928 kg = 92.8 tCO2e
        self.assertNotContains(r, '185.6')  # the doubled figure


class ScienceValidationTest(TestCase):
    """Emission factors must match their cited published sources, and end-use
    caps must stop device-level interventions claiming a whole category."""

    @classmethod
    def setUpTestData(cls):
        call_command('sync_interventions', stdout=StringIO())
        cls.facility = Facility.objects.create(
            code_name='SCI_FAC', display_name='Science Facility', country='ZA')

    def test_factors_match_published_sources(self):
        from appname.modeling import EMISSION_FACTORS, WASTE_EF
        self.assertEqual(EMISSION_FACTORS['bottled_gas'], Decimal('0.00294'))   # DEFRA 2023 LPG/kg
        self.assertEqual(EMISSION_FACTORS['grid_gas'], Decimal('0.00202'))      # DEFRA 2023 gas/m3
        self.assertEqual(EMISSION_FACTORS['liquid_fuel'], Decimal('0.00268'))   # DEFRA mineral diesel/L
        self.assertEqual(WASTE_EF['clinical'], Decimal('1.074'))                # Rizan 2021 HT incineration
        self.assertEqual(WASTE_EF['default'], Decimal('0.497'))                 # DEFRA municipal landfill

    def test_waste_factor_is_sector_aware(self):
        from appname.modeling import compute_tco2e
        source = EmissionSource.objects.create(
            facility=self.facility, code_name='SCI_SRC', display_name='src')
        data = EmissionData.objects.create(
            emission_source=source, waste_management=Decimal('10'))
        clinical = compute_tco2e(data, 'ZA', 'clinical')['waste_management']
        general = compute_tco2e(data, 'ZA', 'research')['waste_management']
        self.assertEqual(clinical, Decimal('10.74'))
        self.assertEqual(general, Decimal('4.97'))
        self.assertGreater(clinical, general)

    def test_lighting_interventions_capped_at_end_use_share(self):
        # Three aggressive LED entries against 100 tCO2e of electricity:
        # without caps they'd claim ~95 tCO2e; the lighting pool caps the
        # combined claim at 25 tCO2e (25% end-use share).
        fis = []
        for code in ('LED_WATT_95', 'LED_WATT_50', 'LED_WATT_20'):
            fis.append(FacilityIntervention.objects.create(
                facility=self.facility,
                intervention=Intervention.objects.get(code_name=code),
                implementation_cost=Decimal('100'), maintenance_cost=Decimal('0'),
            ))
        optimizer = CarbomicaOptimizer(
            facility_interventions=fis, budget=Decimal('10000'),
            total_baseline_emissions=Decimal('100'),
            category_baselines={'grid_electricity': Decimal('100')},
        )
        for name, scenario in optimizer.run_all_scenarios().items():
            total = sum(r['emission_reduction'] for r in scenario['results'])
            self.assertLessEqual(total, Decimal('25'),
                                 f'{name}: lighting claimed {total} of a 25 tCO2e lighting pool')

    def test_solar_is_not_capped(self):
        fi = FacilityIntervention.objects.create(
            facility=self.facility,
            intervention=Intervention.objects.get(code_name='SOLAR_600KWP'),
            implementation_cost=Decimal('612000'), maintenance_cost=Decimal('0'),
        )
        optimizer = CarbomicaOptimizer(
            facility_interventions=[fi], budget=Decimal('1000000'),
            total_baseline_emissions=Decimal('100'),
            category_baselines={'grid_electricity': Decimal('100')},
        )
        result = optimizer.full_coverage()
        self.assertGreater(result[0]['emission_reduction'], Decimal('90'))  # 99% of 100


class MethodologyPageTest(TestCase):
    """The public methodology page must render from the modelling constants."""

    def test_methodology_page_renders_and_matches_code(self):
        response = self.client.get('/methodology/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'DEFRA 2023')
        self.assertContains(response, '2.93921')          # corrected LPG factor
        self.assertContains(response, 'Rizan et al. 2021') # clinical waste source
        self.assertContains(response, 'End-use share caps')
        self.assertContains(response, 'Known limitations')
        self.assertContains(response, 'Community validation')
        self.assertContains(response, '10.5281/zenodo.12730527')


class PotentialSavingsKPITest(TestCase):
    """Regression: the 'Potential savings' KPI on the facility profile summed
    every linked intervention's headline reduction percentage. With the full
    library attached that sum ran into the hundreds, the min(pct, 100) clamp
    saturated, and the KPI reported the ENTIRE baseline as abatable — while the
    optimisation results page, which applies drawdown, reported roughly half.
    The KPI must use the same bounded full-coverage model."""

    @classmethod
    def setUpTestData(cls):
        call_command('sync_interventions', stdout=StringIO())
        cls.user = User.objects.create_user('kpi', 'kpi@example.com', 'pw')

    def _make_facility(self):
        self.client.force_login(self.user)
        self.client.post('/add-facility/', {
            'display_name': 'KPI Research Division', 'code_name': 'KPI_RES',
            'sector': 'research', 'country': 'ZA', 'facility_type': 'research_office',
            'grid_electricity': '420000', 'bottled_gas': '1200', 'liquid_fuel': '14000',
            'vehicle_fuel_owned': '9000', 'business_travel': '120000',
            'refrigeration_gases': '45', 'waste_management': '18',
            'contractor_logistics': '35000', 'flights': '950000',
            'lab_consumables': '850000',
        })
        return Facility.objects.get(code_name='KPI_RES')

    def test_potential_savings_is_strictly_below_baseline(self):
        facility = self._make_facility()
        response = self.client.get(f'/facilities/{facility.id}/')
        self.assertEqual(response.status_code, 200)
        baseline = response.context['baseline_tco2e']
        potential = response.context['potential_savings_tco2e']

        self.assertGreater(potential, Decimal('0'),
                           'Potential savings collapsed to zero — category keys likely mismatched')
        self.assertLess(potential, baseline,
                        'Potential savings equals or exceeds the baseline — double-counting is back')

    def test_kpi_matches_optimiser_full_coverage_scenario(self):
        """The KPI and the results page must not disagree about the same number."""
        facility = self._make_facility()
        response = self.client.get(f'/facilities/{facility.id}/')
        kpi = response.context['potential_savings_tco2e']

        latest = EmissionData.objects.filter(
            emission_source__facility=facility
        ).order_by('-date', '-id').first()
        categories = compute_tco2e(latest, facility.country, facility.sector)
        baseline = categories.pop('total')
        full_coverage = CarbomicaOptimizer(
            facility_interventions=facility.facility_interventions.select_related(
                'intervention', 'facility'
            ).all(),
            budget=Decimal('0'),
            total_baseline_emissions=baseline,
            category_baselines=categories,
        ).full_coverage()
        expected = sum(r['emission_reduction'] for r in full_coverage)

        self.assertEqual(kpi, expected,
                         'Facility KPI diverges from the optimiser full-coverage scenario')


class FootprintTrendCoverageTest(TestCase):
    """Regression: the dashboard trend summed only the facilities that reported
    in a given month. With clinical sites on a Dec-2023 baseline and research
    sites on Dec-2024, the line fell ~43% purely because a different set of
    facilities was counted. Each point must cover the whole portfolio, with
    facilities carried forward at their last reported baseline."""

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user('trend', 't@example.com', 'pw')

    def _facility_with_record(self, code, kwh, when):
        facility = Facility.objects.create(
            code_name=code, display_name=code, country='ZA',
            sector='research', created_by=self.user,
        )
        source = EmissionSource.objects.create(
            facility=facility, code_name=f'{code}_SRC', display_name=f'{code} baseline',
        )
        EmissionData.objects.create(
            emission_source=source, date=when, grid_electricity=Decimal(str(kwh)),
        )
        return facility

    def test_later_period_includes_earlier_reporting_facilities(self):
        from appname.views import _aggregate_tco2e_all

        # Site A reports only in 2023; site B only in 2024.
        self._facility_with_record('TREND_A', 100000, date(2023, 12, 31))
        self._facility_with_record('TREND_B', 100000, date(2024, 12, 31))

        _, _, monthly, _ = _aggregate_tco2e_all(self.user)
        self.assertEqual(len(monthly), 2)
        (first_month, first_total), (second_month, second_total) = monthly
        self.assertLess(first_month, second_month)

        # The 2024 point must carry site A forward, so it covers both sites and
        # cannot drop below the 2023 point just because A did not re-report.
        self.assertGreater(
            second_total, first_total,
            'Later period lost a facility — trend is tracking reporting coverage, not emissions',
        )
        self.assertEqual(second_total, first_total * 2)

    def test_facility_not_backfilled_before_it_started_reporting(self):
        from appname.views import _aggregate_tco2e_all

        self._facility_with_record('TREND_EARLY', 100000, date(2023, 12, 31))
        self._facility_with_record('TREND_LATE', 500000, date(2024, 12, 31))

        _, _, monthly, _ = _aggregate_tco2e_all(self.user)
        (_, first_total), _ = monthly
        expected_first = Decimal('100000') * ELECTRICITY_EF['ZA']
        self.assertEqual(
            first_total, expected_first,
            'The 2023 point includes a facility that had not started reporting yet',
        )


class EmissionHistoryDeltaTest(TestCase):
    """Regression: the 'vs. latest' column printed each row's own absolute total
    instead of its difference from the latest period, so an unchanged period
    rendered as a reduction the size of the entire footprint."""

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user('delta', 'd@example.com', 'pw')

    def _facility_with_periods(self, values):
        facility = Facility.objects.create(
            code_name='DELTA_FAC', display_name='Delta Facility', country='ZA',
            sector='research', created_by=self.user,
        )
        source = EmissionSource.objects.create(
            facility=facility, code_name='DELTA_SRC', display_name='baseline',
        )
        for when, kwh in values:
            EmissionData.objects.create(
                emission_source=source, date=when, grid_electricity=Decimal(str(kwh)),
            )
        return facility

    def test_unchanged_period_reports_zero_delta(self):
        facility = self._facility_with_periods([
            (date(2023, 12, 31), 100000),
            (date(2024, 12, 31), 100000),
        ])
        self.client.force_login(self.user)
        response = self.client.get(f'/facilities/{facility.id}/')
        records = response.context['records_with_tco2e']
        self.assertEqual(records[1]['delta_vs_latest'], Decimal('0'))
        self.assertContains(response, 'no change')

    def test_delta_is_difference_not_absolute_total(self):
        facility = self._facility_with_periods([
            (date(2023, 12, 31), 200000),   # older, higher
            (date(2024, 12, 31), 100000),   # latest
        ])
        self.client.force_login(self.user)
        records = self.client.get(
            f'/facilities/{facility.id}/'
        ).context['records_with_tco2e']

        older = records[1]
        expected = Decimal('100000') * ELECTRICITY_EF['ZA']    # the drop, not the total
        self.assertEqual(older['delta_vs_latest'], expected)
        self.assertNotEqual(older['delta_vs_latest'], older['total_tco2e'])


class OrganisationHierarchyTest(TestCase):
    """Organisations nest (consortium → division → entity → site). Access
    inherits downward only: a consortium lead sees every entity, an entity's
    own members must NOT see their siblings."""

    @classmethod
    def setUpTestData(cls):
        cls.lead = User.objects.create_user('lead', 'lead@example.com', 'pw')
        cls.phru_user = User.objects.create_user('phru', 'phru@example.com', 'pw')

        cls.consortium = Organisation.objects.create(
            name='Test Health Consortium', short_name='THC',
            org_type='consortium', created_by=cls.lead,
        )
        cls.consortium.members.add(cls.lead)
        cls.division = Organisation.objects.create(
            name='Research Entities', org_type='division',
            parent=cls.consortium, created_by=cls.lead,
        )
        cls.phru = Organisation.objects.create(
            name='Perinatal Unit', short_name='PHRU', org_type='entity',
            parent=cls.division, created_by=cls.lead,
        )
        cls.phru.members.add(cls.phru_user)
        cls.vida = Organisation.objects.create(
            name='Vaccines Unit', short_name='VIDA', org_type='entity',
            parent=cls.division, created_by=cls.lead,
        )

        cls.phru_site = cls._site('PHRU_SITE', cls.phru, 100000)
        cls.vida_site = cls._site('VIDA_SITE', cls.vida, 300000)

    @classmethod
    def _site(cls, code, org, kwh):
        facility = Facility.objects.create(
            code_name=code, display_name=code, country='ZA',
            sector='research', organisation=org,
        )
        source = EmissionSource.objects.create(
            facility=facility, code_name=f'{code}_SRC', display_name=code,
        )
        EmissionData.objects.create(
            emission_source=source, date=date(2024, 12, 31),
            grid_electricity=Decimal(str(kwh)),
        )
        return facility

    # ── Tree shape ────────────────────────────────────────────────────
    def test_descendants_span_the_whole_subtree(self):
        ids = self.consortium.descendant_ids()
        self.assertEqual(
            ids,
            {self.consortium.pk, self.division.pk, self.phru.pk, self.vida.pk},
        )
        self.assertEqual(self.phru.depth, 2)
        self.assertEqual([o.pk for o in self.phru.ancestors()],
                         [self.division.pk, self.consortium.pk])

    def test_cycle_does_not_hang_the_walk(self):
        """A parent pointed at its own descendant must not loop forever."""
        self.consortium.parent = self.phru
        self.consortium.save(update_fields=['parent'])
        try:
            self.assertIn(self.phru.pk, self.phru.descendant_ids())
            self.assertLessEqual(len(self.consortium.ancestors()), 4)
        finally:
            self.consortium.parent = None
            self.consortium.save(update_fields=['parent'])

    # ── Access control ────────────────────────────────────────────────
    def test_consortium_member_sees_every_entity_site(self):
        from appname.views import _user_facilities
        visible = set(_user_facilities(self.lead).values_list('code_name', flat=True))
        self.assertEqual(visible, {'PHRU_SITE', 'VIDA_SITE'})

    def test_entity_member_cannot_see_a_sibling_entity(self):
        from appname.views import _user_facilities
        visible = set(_user_facilities(self.phru_user).values_list('code_name', flat=True))
        self.assertEqual(visible, {'PHRU_SITE'})
        self.assertNotIn('VIDA_SITE', visible, 'Entity member can see a sibling entity')

    def test_entity_member_cannot_reach_a_sibling_facility_page(self):
        self.client.force_login(self.phru_user)
        self.assertEqual(
            self.client.get(f'/facilities/{self.phru_site.id}/').status_code, 200)
        self.assertEqual(
            self.client.get(f'/facilities/{self.vida_site.id}/').status_code, 404,
            'Sibling entity facility page is reachable',
        )

    def test_entity_member_cannot_add_orgs_under_the_consortium(self):
        self.client.force_login(self.phru_user)
        self.client.post('/organisation/', {
            'action': 'create', 'org_name': 'Sneaky Unit',
            'parent_id': self.consortium.id, 'org_type': 'entity',
        })
        self.assertFalse(
            Organisation.objects.filter(name='Sneaky Unit').exists(),
            'A non-manager grafted an organisation onto another consortium',
        )

    # ── Roll-up ───────────────────────────────────────────────────────
    def test_parent_rollup_equals_sum_of_children(self):
        from appname.views import _org_tree_rows
        rows = {r['org'].pk: r for r in _org_tree_rows(self.lead)}
        consortium_row = rows[self.consortium.pk]
        self.assertEqual(consortium_row['facility_count'], 2)
        self.assertEqual(
            consortium_row['tco2e'],
            rows[self.phru.pk]['tco2e'] + rows[self.vida.pk]['tco2e'],
        )

    def test_entity_member_rollup_covers_only_their_subtree(self):
        from appname.views import _org_tree_rows
        rows = _org_tree_rows(self.phru_user)
        self.assertEqual([r['org'].pk for r in rows], [self.phru.pk])
        self.assertEqual(rows[0]['facility_count'], 1)


class FacilityOrganisationPickerTest(TestCase):
    """A new site must be filable directly under the user's own entity, and the
    picker must not expose organisations the user cannot see — otherwise a site
    could be attached to another consortium's entity and leak to its members."""

    @classmethod
    def setUpTestData(cls):
        cls.ours = User.objects.create_user('ours', 'ours@example.com', 'pw')
        cls.theirs = User.objects.create_user('theirs', 'theirs@example.com', 'pw')

        cls.our_consortium = Organisation.objects.create(
            name='Our Consortium', org_type='consortium', created_by=cls.ours,
        )
        cls.our_consortium.members.add(cls.ours)
        cls.our_entity = Organisation.objects.create(
            name='Our Entity', org_type='entity',
            parent=cls.our_consortium, created_by=cls.ours,
        )
        cls.their_entity = Organisation.objects.create(
            name='Their Entity', org_type='entity', created_by=cls.theirs,
        )
        cls.their_entity.members.add(cls.theirs)

    def test_picker_lists_own_subtree_only(self):
        from appname.forms import FacilityForm
        options = set(
            FacilityForm(user=self.ours).fields['organisation'].queryset
            .values_list('name', flat=True)
        )
        self.assertEqual(options, {'Our Consortium', 'Our Entity'})
        self.assertNotIn('Their Entity', options)

    def test_site_created_under_an_entity_is_visible_to_the_consortium(self):
        from appname.views import _user_facilities
        self.client.force_login(self.ours)
        self.client.post('/add-facility/', {
            'display_name': 'Entity Site', 'code_name': 'ENT_SITE',
            'sector': 'research', 'country': 'ZA', 'facility_type': 'university_lab',
            'organisation': self.our_entity.id, 'grid_electricity': '100000',
        })
        facility = Facility.objects.get(code_name='ENT_SITE')
        self.assertEqual(facility.organisation, self.our_entity)
        self.assertIn(facility, _user_facilities(self.ours))
        self.assertNotIn(facility, _user_facilities(self.theirs))

    def test_cannot_file_a_site_under_an_unseen_organisation(self):
        self.client.force_login(self.ours)
        self.client.post('/add-facility/', {
            'display_name': 'Sneaky Site', 'code_name': 'SNEAK',
            'sector': 'research', 'country': 'ZA', 'facility_type': 'university_lab',
            'organisation': self.their_entity.id, 'grid_electricity': '100000',
        })
        sneaky = Facility.objects.filter(code_name='SNEAK').first()
        self.assertIsNone(
            sneaky.organisation if sneaky else None,
            'A site was attached to an organisation the creator cannot see',
        )


class ProcurementItemisationTest(TestCase):
    """Itemised procurement must REPLACE the blended lab_consumables estimate,
    never add to it, and must round-trip through the facility profile."""

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user('proc', 'proc@example.com', 'pw')
        cls.facility = Facility.objects.create(
            code_name='PROC_FAC', display_name='Procurement Facility', country='ZA',
            sector='research', created_by=cls.user,
        )
        cls.source = EmissionSource.objects.create(
            facility=cls.facility, code_name='PROC_SRC', display_name='baseline',
        )
        cls.record = EmissionData.objects.create(
            emission_source=cls.source, date=date(2024, 12, 31),
            lab_consumables=Decimal('1000000'),
        )

    def _breakdown(self):
        return compute_tco2e(self.record, self.facility.country, self.facility.sector)

    def test_blended_figure_used_when_no_lines(self):
        expected = Decimal('1000000') * EMISSION_FACTORS['lab_consumables']
        self.assertEqual(self._breakdown()['lab_consumables'], expected)

    def test_lines_replace_rather_than_add_to_the_blended_figure(self):
        blended = self._breakdown()['lab_consumables']
        ProcurementLine.objects.create(
            emission_data=self.record, category='LAB_REAGENTS',
            spend_usd=Decimal('1000000'), source='CSV',
        )
        itemised = self._breakdown()['lab_consumables']
        expected = Decimal('1000000') * PROCUREMENT_CATEGORIES['LAB_REAGENTS']['factor']

        self.assertEqual(itemised, expected)
        self.assertNotEqual(itemised, blended + expected,
                            'Itemised lines were ADDED to the blended figure — double-counted')
        self.assertLess(itemised, blended,
                        'Classifying low-intensity spend should reduce the estimate')

    def test_zero_spend_lines_are_not_treated_as_missing(self):
        """A record with lines totalling zero must report zero, not fall back."""
        ProcurementLine.objects.create(
            emission_data=self.record, category='LAB_REAGENTS',
            spend_usd=Decimal('0'), source='MANUAL',
        )
        self.assertEqual(self._breakdown()['lab_consumables'], Decimal('0'))

    def test_breakdown_ranks_by_carbon_and_flags_intensity_gap(self):
        # Big spend, low intensity vs small spend, high intensity.
        ProcurementLine.objects.create(
            emission_data=self.record, category='LAB_REAGENTS',
            spend_usd=Decimal('500000'), source='CSV')
        ProcurementLine.objects.create(
            emission_data=self.record, category='LAB_CHEMICALS',
            spend_usd=Decimal('100000'), source='CSV')

        rows = procurement_breakdown(self.record)
        self.assertEqual(rows[0]['category'], 'LAB_CHEMICALS',
                         'Ranking should be by carbon, not by spend')
        self.assertGreater(rows[0]['intensity_gap'], 0)
        self.assertLess(rows[1]['intensity_gap'], 0)
        self.assertAlmostEqual(float(rows[-1]['cumulative_share']), 100.0, places=4)

    def test_facility_profile_shows_hot_spots(self):
        ProcurementLine.objects.create(
            emission_data=self.record, category='LAB_CHEMICALS',
            description='Solvents', spend_usd=Decimal('100000'), source='CSV')
        self.client.force_login(self.user)
        response = self.client.get(f'/facilities/{self.facility.id}/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Procurement hot spots')
        self.assertContains(response, 'Chemicals &amp; solvents')


class ProcurementImportTest(TestCase):
    """The CSV import has to cope with a real finance export: unfamiliar column
    names, currency formatting, credits, blank rows, and categories that do not
    match ours."""

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user('imp', 'imp@example.com', 'pw')
        cls.facility = Facility.objects.create(
            code_name='IMP_FAC', display_name='Import Facility', country='ZA',
            sector='research', created_by=cls.user,
        )

    def _post(self, csv_body, period='2024-12-31'):
        from django.core.files.uploadedfile import SimpleUploadedFile
        self.client.force_login(self.user)
        return self.client.post('/upload/procurement/', {
            'facility': self.facility.id,
            'period': period,
            'csv_file': SimpleUploadedFile('spend.csv', csv_body.encode(), 'text/csv'),
        })

    def test_imports_a_typical_finance_export(self):
        response = self._post(
            'Account Name,Details,Vendor,Net Amount\n'
            'Consumables,Pipette tips 200ul,Thermo Fisher,"42,000.00"\n'
            'Reagents,PCR master mix,Bio-Rad,$86000\n'
            'IT hardware,Workstations,Dell,31000\n'
        )
        self.assertEqual(response.status_code, 200)
        lines = ProcurementLine.objects.filter(
            emission_data__emission_source__facility=self.facility)
        self.assertEqual(lines.count(), 3)
        self.assertEqual(
            set(lines.values_list('category', flat=True)),
            {'LAB_PLASTICS', 'LAB_REAGENTS', 'IT_HARDWARE'},
        )
        self.assertEqual(lines.get(category='LAB_PLASTICS').spend_usd, Decimal('42000'))
        self.assertEqual(lines.get(category='LAB_REAGENTS').supplier, 'Bio-Rad')

    def test_credits_and_blank_rows_are_skipped(self):
        self._post(
            'category,description,supplier,amount\n'
            'Reagents,Master mix,Bio-Rad,50000\n'
            'Reagents,Credit note,Bio-Rad,-5000\n'
            ',,,\n'
            'Reagents,Zero line,Bio-Rad,0\n'
        )
        self.assertEqual(
            ProcurementLine.objects.filter(
                emission_data__emission_source__facility=self.facility).count(),
            1,
        )

    def test_unmatched_categories_fall_back_to_other_and_are_reported(self):
        response = self._post(
            'category,description,supplier,amount\n'
            'ZZ-9911 Sundry,Miscellaneous,Various,25000\n'
        )
        line = ProcurementLine.objects.get(
            emission_data__emission_source__facility=self.facility)
        self.assertEqual(line.category, 'OTHER')
        report = response.context['import_report']
        self.assertEqual(report['unmatched_count'], 1)
        self.assertEqual(report['unclassified_share'], Decimal('100'))

    def test_reimport_replaces_rather_than_duplicates(self):
        body = ('category,description,supplier,amount\n'
                'Reagents,Master mix,Bio-Rad,50000\n')
        self._post(body)
        self._post(body)
        self.assertEqual(
            ProcurementLine.objects.filter(
                emission_data__emission_source__facility=self.facility).count(),
            1,
            'Re-importing the same period duplicated the spend',
        )

    def test_reimport_keeps_hand_entered_lines(self):
        self._post('category,description,supplier,amount\n'
                   'Reagents,Master mix,Bio-Rad,50000\n')
        record = EmissionData.objects.filter(
            emission_source__facility=self.facility).first()
        ProcurementLine.objects.create(
            emission_data=record, category='LAB_GASES',
            description='Hand-added nitrogen', spend_usd=Decimal('9000'),
            source='MANUAL',
        )
        self._post('category,description,supplier,amount\n'
                   'Reagents,Master mix,Bio-Rad,50000\n')
        self.assertTrue(
            ProcurementLine.objects.filter(
                emission_data=record, source='MANUAL').exists(),
            'Re-import deleted a hand-entered line it did not own',
        )

    def test_missing_spend_column_is_rejected(self):
        self._post('category,description,supplier\nReagents,Master mix,Bio-Rad\n')
        self.assertFalse(
            ProcurementLine.objects.filter(
                emission_data__emission_source__facility=self.facility).exists())

    def test_cannot_import_against_another_users_facility(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        stranger = User.objects.create_user('stranger', 's@example.com', 'pw')
        self.client.force_login(stranger)
        response = self.client.post('/upload/procurement/', {
            'facility': self.facility.id, 'period': '2024-12-31',
            'csv_file': SimpleUploadedFile(
                'spend.csv', b'category,amount\nReagents,50000\n', 'text/csv'),
        })
        self.assertEqual(response.status_code, 404)


class ProcurementImportPreservesBaselineTest(TestCase):
    """Regression: importing procurement created a second EmissionData for the
    same period on a dedicated upload source. Because "latest" resolves by
    (-date, -id), that otherwise-empty record won and zeroed the site's
    electricity, flights and fuel. Importing spend must never erase the rest of
    the footprint."""

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user('preserve', 'p@example.com', 'pw')
        cls.facility = Facility.objects.create(
            code_name='KEEP_FAC', display_name='Keep Facility', country='ZA',
            sector='research', created_by=cls.user,
        )
        source = EmissionSource.objects.create(
            facility=cls.facility, code_name='KEEP_SRC', display_name='baseline',
        )
        EmissionData.objects.create(
            emission_source=source, date=date(2024, 12, 31),
            grid_electricity=Decimal('420000'), flights=Decimal('950000'),
        )

    def _import(self, period='2024-12-31'):
        from django.core.files.uploadedfile import SimpleUploadedFile
        self.client.force_login(self.user)
        return self.client.post('/upload/procurement/', {
            'facility': self.facility.id, 'period': period,
            'csv_file': SimpleUploadedFile(
                'spend.csv',
                b'category,description,supplier,amount\n'
                b'Reagents,Master mix,Bio-Rad,50000\n',
                'text/csv'),
        })

    def _latest(self):
        return (EmissionData.objects
                .filter(emission_source__facility=self.facility)
                .order_by('-date', '-id').first())

    def test_import_does_not_create_a_second_record_for_the_period(self):
        self._import()
        self.assertEqual(
            EmissionData.objects.filter(
                emission_source__facility=self.facility,
                date=date(2024, 12, 31)).count(),
            1,
            'Import created a duplicate record for a period that already had one',
        )

    def test_existing_emissions_survive_the_import(self):
        before = compute_tco2e(self._latest(), 'ZA', 'research')
        self._import()
        after_record = self._latest()
        after = compute_tco2e(after_record, 'ZA', 'research')

        self.assertEqual(after_record.grid_electricity, Decimal('420000'))
        self.assertEqual(after['grid_electricity'], before['grid_electricity'])
        self.assertEqual(after['flights'], before['flights'])
        self.assertGreater(after['total'], Decimal('0'))
        self.assertTrue(after_record.procurement_lines.exists())

    def test_period_with_no_record_still_gets_one(self):
        self._import(period='2023-12-31')
        self.assertTrue(
            EmissionData.objects.filter(
                emission_source__facility=self.facility,
                date=date(2023, 12, 31)).exists(),
            'Importing into an unreported period should create the record',
        )


class ProjectAttributionTest(TestCase):
    """An award's footprint is direct spend charged to it plus its stated share
    of shared site emissions. Two awards at the same site must never see each
    other's purchases, and the apportioned pool must shrink as spend is claimed."""

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user('proj', 'proj@example.com', 'pw')
        cls.facility = Facility.objects.create(
            code_name='PRJ_SITE', display_name='Shared Lab', country='ZA',
            sector='research', created_by=cls.user,
        )
        source = EmissionSource.objects.create(
            facility=cls.facility, code_name='PRJ_SRC', display_name='baseline',
        )
        cls.record = EmissionData.objects.create(
            emission_source=source, date=date(2024, 12, 31),
            grid_electricity=Decimal('1000000'),
        )
        cls.alpha = Project.objects.create(name='Award Alpha', created_by=cls.user)
        cls.beta = Project.objects.create(name='Award Beta', created_by=cls.user)
        ProjectSite.objects.create(
            project=cls.alpha, facility=cls.facility,
            share_pct=Decimal('25'), basis_note='10 of 40 FTE')
        ProjectSite.objects.create(
            project=cls.beta, facility=cls.facility,
            share_pct=Decimal('25'), basis_note='10 of 40 FTE')

    def _line(self, project, spend, category='LAB_REAGENTS'):
        return ProcurementLine.objects.create(
            emission_data=self.record, category=category,
            spend_usd=Decimal(str(spend)), project=project, source='CSV',
        )

    def test_shared_emissions_split_by_declared_share(self):
        site_total = compute_tco2e(self.record, 'ZA', 'research')['grid_electricity']
        alpha = project_footprint(self.alpha)
        self.assertEqual(
            alpha['by_category']['grid_electricity'], site_total * Decimal('0.25'))

    def test_direct_spend_is_not_visible_to_another_award(self):
        self._line(self.alpha, 100000)
        beta = project_footprint(self.beta)
        self.assertEqual(beta['direct_total'], Decimal('0'),
                         "Beta picked up Alpha's directly charged spend")
        self.assertEqual(beta['by_category']['lab_consumables'], Decimal('0'),
                         "Alpha's tagged spend leaked into Beta's apportioned pool")

    def test_untagged_spend_is_apportioned_but_tagged_spend_is_not(self):
        self._line(None, 100000)          # shared, untagged
        self._line(self.alpha, 100000)    # charged to Alpha

        alpha = project_footprint(self.alpha)
        beta = project_footprint(self.beta)
        untagged_tco2e = Decimal('100000') * PROCUREMENT_CATEGORIES['LAB_REAGENTS']['factor']

        # Beta only ever sees its share of the untagged pool.
        self.assertEqual(beta['by_category']['lab_consumables'],
                         untagged_tco2e * Decimal('0.25'))
        # Alpha sees its own line in full, plus its share of the untagged pool.
        self.assertEqual(
            alpha['by_category']['lab_consumables'],
            untagged_tco2e + untagged_tco2e * Decimal('0.25'),
        )

    def test_awards_together_never_exceed_the_site_footprint(self):
        self._line(None, 100000)
        self._line(self.alpha, 60000)
        self._line(self.beta, 40000)

        site_total = compute_tco2e(self.record, 'ZA', 'research')['total']
        combined = (project_footprint(self.alpha)['total']
                    + project_footprint(self.beta)['total'])
        self.assertLessEqual(
            combined, site_total,
            'Two awards together attribute more than the site actually emitted',
        )

    def test_blended_procurement_is_apportioned_when_site_is_not_itemised(self):
        self.record.lab_consumables = Decimal('500000')
        self.record.save(update_fields=['lab_consumables'])
        blended = Decimal('500000') * EMISSION_FACTORS['lab_consumables']
        alpha = project_footprint(self.alpha)
        self.assertEqual(alpha['by_category']['lab_consumables'],
                         blended * Decimal('0.25'))

    def test_site_without_emission_data_is_surfaced_not_silently_zero(self):
        empty = Facility.objects.create(
            code_name='PRJ_EMPTY', display_name='Unreported Site', country='ZA',
            sector='research', created_by=self.user,
        )
        ProjectSite.objects.create(
            project=self.alpha, facility=empty, share_pct=Decimal('50'))
        alpha = project_footprint(self.alpha)
        self.assertEqual(len(alpha['sites_missing_data']), 1)
        self.assertTrue(alpha['sites_missing_data'][0]['missing_data'])


class ProjectAccessTest(TestCase):
    """Awards follow the same visibility rules as facilities."""

    @classmethod
    def setUpTestData(cls):
        cls.lead = User.objects.create_user('plead', 'pl@example.com', 'pw')
        cls.outsider = User.objects.create_user('pout', 'po@example.com', 'pw')

        cls.consortium = Organisation.objects.create(
            name='P Consortium', org_type='consortium', created_by=cls.lead)
        cls.consortium.members.add(cls.lead)
        cls.entity = Organisation.objects.create(
            name='P Entity', org_type='entity',
            parent=cls.consortium, created_by=cls.lead)

        cls.facility = Facility.objects.create(
            code_name='P_SITE', display_name='P Site', country='ZA',
            sector='research', organisation=cls.entity)
        cls.project = Project.objects.create(
            name='Consortium Award', organisation=cls.entity, created_by=cls.lead)
        ProjectSite.objects.create(
            project=cls.project, facility=cls.facility, share_pct=Decimal('20'))

    def test_consortium_lead_sees_the_award(self):
        self.client.force_login(self.lead)
        self.assertEqual(
            self.client.get(f'/projects/{self.project.id}/').status_code, 200)

    def test_outsider_cannot_open_the_award(self):
        self.client.force_login(self.outsider)
        self.assertEqual(
            self.client.get(f'/projects/{self.project.id}/').status_code, 404)

    def test_cannot_attach_a_facility_you_cannot_see(self):
        theirs = Facility.objects.create(
            code_name='THEIR_SITE', display_name='Their Site', country='ZA',
            sector='research', created_by=self.outsider)
        self.client.force_login(self.lead)
        self.client.post(f'/projects/{self.project.id}/', {
            'action': 'add_site', 'facility': theirs.id, 'share_pct': '50',
        })
        self.assertFalse(
            ProjectSite.objects.filter(project=self.project, facility=theirs).exists(),
            'An award absorbed a site its owner cannot see',
        )

    def test_report_page_carries_the_audit_record(self):
        self.project.allocation_note = '3.2 of 41.0 FTE, 2024 timesheet return.'
        self.project.save(update_fields=['allocation_note'])
        self.client.force_login(self.lead)
        response = self.client.get(f'/projects/{self.project.id}/')
        self.assertContains(response, 'Statement of method')
        self.assertContains(response, '3.2 of 41.0 FTE')


class TravelJourneyTest(TestCase):
    """Award travel log: each journey uses the DEFRA 2026 factor for its mode,
    and logged journeys replace the award's apportioned share of site travel so
    no trip is counted twice."""

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user('trav', 'trav@example.com', 'pw')
        cls.outsider = User.objects.create_user('trout', 'tro@example.com', 'pw')
        cls.facility = Facility.objects.create(
            code_name='TRV_SITE', display_name='Travel Lab', country='ZA',
            sector='research', created_by=cls.user,
        )
        source = EmissionSource.objects.create(
            facility=cls.facility, code_name='TRV_SRC', display_name='baseline',
        )
        cls.record = EmissionData.objects.create(
            emission_source=source, date=date(2025, 12, 31),
            grid_electricity=Decimal('100000'),
            flights=Decimal('400000'),
            business_travel=Decimal('50000'),
        )
        cls.project = Project.objects.create(name='Travel Award', created_by=cls.user)
        ProjectSite.objects.create(
            project=cls.project, facility=cls.facility, share_pct=Decimal('25'))

    def _journey(self, **kw):
        fields = dict(
            project=self.project, date=date(2026, 3, 1), origin='A',
            destination='B', mode='rail_national', distance_km=Decimal('100'),
        )
        fields.update(kw)
        journey = TravelJourney(**fields)
        journey.full_clean()
        journey.save()
        return journey

    def test_every_surface_mode_uses_its_defra_factor(self):
        for mode, (factor, per_passenger) in SURFACE_FACTORS.items():
            people = 3 if per_passenger else 1
            expected = Decimal('100') * people * factor / Decimal('1000')
            self.assertEqual(journey_tco2e(mode, Decimal('100'), 3), expected, mode)

    def test_every_published_air_combination_uses_its_factor(self):
        for (haul, cabin), factor in AIR_FACTORS.items():
            self.assertEqual(
                journey_tco2e('air', Decimal('1000'), 2, haul, cabin),
                Decimal('2000') * factor / Decimal('1000'),
                f'{haul}/{cabin}',
            )

    def test_spot_check_against_published_value(self):
        # DEFRA 2026, Long-haul to/from UK, Economy, With RF: 0.11704 kg/pkm.
        self.assertEqual(
            journey_tco2e('air', Decimal('10000'), 1, 'long_haul_uk', 'economy'),
            Decimal('1.17040'),
        )

    def test_car_is_per_vehicle_not_per_passenger(self):
        self.assertEqual(
            journey_tco2e('car', Decimal('100'), 4),
            journey_tco2e('car', Decimal('100'), 1),
        )

    def test_blank_cabin_falls_back_to_average_passenger(self):
        journey = self._journey(mode='air', air_haul='domestic_uk', cabin_class='')
        self.assertEqual(journey.cabin_class, 'average')

    def test_unpublished_air_combinations_are_rejected(self):
        from django.core.exceptions import ValidationError
        for haul, cabin in [('short_haul_uk', 'first'),
                            ('short_haul_uk', 'premium_economy'),
                            ('domestic_uk', 'business')]:
            with self.assertRaises(ValidationError, msg=f'{haul}/{cabin}'):
                self._journey(mode='air', air_haul=haul, cabin_class=cabin)

    def test_flight_without_haul_is_rejected(self):
        from django.core.exceptions import ValidationError
        with self.assertRaises(ValidationError):
            self._journey(mode='air', air_haul='')

    def test_surface_journey_drops_flight_only_fields(self):
        journey = self._journey(
            mode='coach', air_haul='long_haul_uk', cabin_class='business',
            rail_hours=Decimal('4'))
        self.assertEqual((journey.air_haul, journey.cabin_class, journey.rail_hours),
                         ('', '', None))

    def test_without_journeys_site_travel_is_still_apportioned(self):
        full = compute_tco2e(self.record, 'ZA', 'research')
        fp = project_footprint(self.project)
        self.assertEqual(fp['by_category']['flights'], full['flights'] * Decimal('0.25'))
        self.assertFalse(fp['travel_logged'])

    def test_logged_journeys_replace_apportioned_site_travel(self):
        journey = self._journey(mode='air', air_haul='international_non_uk',
                                cabin_class='economy', distance_km=Decimal('2900'))
        full = compute_tco2e(self.record, 'ZA', 'research')
        fp = project_footprint(self.project)

        self.assertEqual(fp['by_category']['flights'], Decimal('0'))
        self.assertEqual(fp['by_category']['business_travel'], Decimal('0'))
        self.assertEqual(fp['by_category']['award_travel'], journey.tco2e())
        # Non-travel overheads are still apportioned as before.
        self.assertEqual(fp['by_category']['grid_electricity'],
                         full['grid_electricity'] * Decimal('0.25'))
        # Travel counts as direct, and the total is the sum of its parts.
        self.assertEqual(fp['direct_total'], journey.tco2e())
        self.assertEqual(fp['total'], fp['direct_total'] + fp['apportioned_total'])

    def test_award_page_logs_and_shows_a_journey(self):
        self.client.force_login(self.user)
        self.client.post(f'/projects/{self.project.id}/', {
            'action': 'add_journey', 'date': '2026-04-02', 'origin': 'Johannesburg',
            'destination': 'Nairobi', 'mode': 'air', 'air_haul': 'international_non_uk',
            'cabin_class': 'economy', 'distance_km': '2900', 'passengers': '2',
            'purpose': 'Consortium meeting',
        })
        journey = TravelJourney.objects.get(project=self.project)
        self.assertEqual(journey.created_by, self.user)
        response = self.client.get(f'/projects/{self.project.id}/')
        self.assertContains(response, 'Johannesburg → Nairobi')
        self.assertContains(response, 'Travel is attributed per journey')

    def test_invalid_journey_is_not_saved(self):
        self.client.force_login(self.user)
        self.client.post(f'/projects/{self.project.id}/', {
            'action': 'add_journey', 'date': '2026-04-02', 'origin': 'A',
            'destination': 'B', 'mode': 'air', 'air_haul': 'short_haul_uk',
            'cabin_class': 'first', 'distance_km': '900', 'passengers': '1',
        })
        self.assertFalse(TravelJourney.objects.filter(project=self.project).exists())

    def test_outsider_cannot_log_travel_on_the_award(self):
        self.client.force_login(self.outsider)
        response = self.client.post(f'/projects/{self.project.id}/', {
            'action': 'add_journey', 'date': '2026-04-02', 'origin': 'A',
            'destination': 'B', 'mode': 'coach', 'distance_km': '50', 'passengers': '1',
        })
        self.assertEqual(response.status_code, 404)
        self.assertFalse(TravelJourney.objects.exists())

    def test_cannot_remove_a_journey_from_another_award(self):
        other = Project.objects.create(name='Other Award', created_by=self.user)
        journey = self._journey(project=other)
        self.client.force_login(self.user)
        self.client.post(f'/projects/{self.project.id}/', {
            'action': 'remove_journey', 'journey_id': journey.id,
        })
        self.assertTrue(TravelJourney.objects.filter(id=journey.id).exists())

    def test_methodology_page_lists_travel_factors_and_source(self):
        response = self.client.get('/methodology/')
        self.assertContains(response, 'Conversion Factors for Company Reporting 2026')
        self.assertContains(response, '0.11704')


class JourneyPolicyFlagsTest(TestCase):
    """Wellcome travel rules: train for trips up to 10 h door to door, economy by
    default, no business class, and every journey justified."""

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user('flag', 'flag@example.com', 'pw')
        cls.project = Project.objects.create(name='Flag Award', created_by=cls.user)

    def _flight(self, **kw):
        fields = dict(
            project=self.project, date=date(2026, 5, 1), origin='London',
            destination='Edinburgh', mode='air', air_haul='domestic_uk',
            cabin_class='average', distance_km=Decimal('530'),
            rail_hours=Decimal('12'), purpose='Advisory board meeting',
        )
        fields.update(kw)
        journey = TravelJourney(**fields)
        journey.full_clean()
        journey.save()
        return journey

    def _codes(self, journey):
        return [f['code'] for f in journey_policy_flags(journey)]

    def test_compliant_flight_has_no_flags(self):
        self.assertEqual(self._codes(self._flight()), [])

    def test_rail_at_exactly_ten_hours_is_flagged(self):
        self.assertIn('rail_feasible', self._codes(self._flight(rail_hours=Decimal('10.0'))))

    def test_rail_just_over_ten_hours_is_not_flagged(self):
        self.assertNotIn('rail_feasible', self._codes(self._flight(rail_hours=Decimal('10.1'))))

    def test_missing_rail_time_is_info_not_a_breach(self):
        flags = journey_policy_flags(self._flight(rail_hours=None))
        self.assertEqual([(f['code'], f['severity']) for f in flags],
                         [('rail_unknown', 'info')])

    def test_business_class_fails_and_quotes_the_policy(self):
        flags = journey_policy_flags(self._flight(
            air_haul='long_haul_uk', cabin_class='business'))
        business = [f for f in flags if f['code'] == 'business_class']
        self.assertEqual(business[0]['severity'], 'fail')
        self.assertEqual(business[0]['quote'],
                         'Wellcome does not fund business class flights.')

    def test_first_and_premium_economy_are_warned_not_failed(self):
        for cabin in ('first', 'premium_economy'):
            flags = journey_policy_flags(self._flight(
                air_haul='long_haul_uk', cabin_class=cabin))
            self.assertEqual([(f['code'], f['severity']) for f in flags],
                             [('not_economy', 'warn')], cabin)

    def test_economy_and_unknown_cabin_are_not_flagged(self):
        for cabin in ('economy', 'average'):
            journey = self._flight(air_haul='long_haul_uk', cabin_class=cabin)
            self.assertNotIn('not_economy', self._codes(journey))
            self.assertNotIn('business_class', self._codes(journey))

    def test_unjustified_journey_is_flagged_for_any_mode(self):
        coach = TravelJourney.objects.create(
            project=self.project, date=date(2026, 5, 2), origin='A', destination='B',
            mode='coach', distance_km=Decimal('80'), purpose='   ')
        self.assertEqual(self._codes(coach), ['no_justification'])

    def test_surface_journeys_never_get_flight_flags(self):
        rail = TravelJourney.objects.create(
            project=self.project, date=date(2026, 5, 2), origin='A', destination='B',
            mode='rail_national', distance_km=Decimal('600'), purpose='Fieldwork')
        self.assertEqual(self._codes(rail), [])

    def test_report_summarises_flags_worst_first(self):
        self._flight(air_haul='long_haul_uk', cabin_class='business', purpose='')
        self._flight(rail_hours=Decimal('6'))
        summary = project_footprint(self.project)['travel_flag_summary']
        self.assertEqual([e['code'] for e in summary],
                         ['business_class', 'no_justification', 'rail_feasible'])
        self.assertTrue(all(e['count'] == 1 for e in summary))

    def test_award_page_shows_flags(self):
        self._flight(air_haul='long_haul_uk', cabin_class='business')
        self.client.force_login(self.user)
        response = self.client.get(f'/projects/{self.project.id}/')
        self.assertContains(response, 'Wellcome travel checks')
        self.assertContains(response, 'Business class is not fundable by Wellcome.')


class CreditPositionTest(TestCase):
    """Credits for an award's remaining travel: whole credits (1 = 1 tCO2e),
    net of purchases, from accredited standards, retired on the registry."""

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user('cred', 'cred@example.com', 'pw')
        cls.outsider = User.objects.create_user('credout', 'co@example.com', 'pw')
        cls.project = Project.objects.create(name='Credit Award', created_by=cls.user)
        # 10,000 pkm long-haul economy at 0.11704 kg/pkm = 1.1704 t -> 2 credits.
        TravelJourney.objects.create(
            project=cls.project, date=date(2026, 2, 1), origin='JNB', destination='LHR',
            mode='air', air_haul='long_haul_uk', cabin_class='economy',
            distance_km=Decimal('10000'), purpose='Review meeting')

    def _buy(self, credits, registry='verra', retired=False):
        return CreditPurchase.objects.create(
            project=self.project, credits_tco2e=Decimal(str(credits)),
            provider='Test provider', registry=registry, retired=retired)

    def _position(self):
        return credit_position(self.project, project_footprint(self.project))

    def test_requirement_rounds_up_to_whole_credits(self):
        pos = self._position()
        self.assertEqual(pos['travel_tco2e'], Decimal('1.17040'))
        self.assertEqual(pos['required'], Decimal('2'))
        self.assertEqual(pos['basis'], 'logged')

    def test_under_purchase_leaves_credits_outstanding(self):
        self._buy('1.5')
        pos = self._position()
        self.assertEqual(pos['outstanding'], Decimal('0.5'))
        self.assertEqual(pos['surplus'], Decimal('0'))
        self.assertFalse(pos['covered'])

    def test_exact_purchase_covers_the_award(self):
        self._buy(2)
        pos = self._position()
        self.assertTrue(pos['covered'])
        self.assertEqual((pos['outstanding'], pos['surplus']), (Decimal('0'), Decimal('0')))

    def test_over_purchase_is_surplus_not_negative(self):
        self._buy(3)
        pos = self._position()
        self.assertEqual(pos['outstanding'], Decimal('0'))
        self.assertEqual(pos['surplus'], Decimal('1'))

    def test_award_without_travel_needs_no_credits(self):
        empty = Project.objects.create(name='No Travel', created_by=self.user)
        pos = credit_position(empty, project_footprint(empty))
        self.assertEqual((pos['required'], pos['basis'], pos['covered']),
                         (Decimal('0'), 'none', False))

    def test_apportioned_site_travel_is_used_when_nothing_is_logged(self):
        facility = Facility.objects.create(
            code_name='CRD_SITE', display_name='Credit Site', country='ZA',
            sector='research', created_by=self.user)
        source = EmissionSource.objects.create(
            facility=facility, code_name='CRD_SRC', display_name='baseline')
        record = EmissionData.objects.create(
            emission_source=source, date=date(2025, 12, 31), flights=Decimal('100000'))
        award = Project.objects.create(name='Apportioned Award', created_by=self.user)
        ProjectSite.objects.create(project=award, facility=facility, share_pct=Decimal('10'))
        pos = credit_position(award, project_footprint(award))
        site_flights = compute_tco2e(record, 'ZA', 'research')['flights']
        self.assertEqual(pos['basis'], 'apportioned')
        self.assertEqual(pos['travel_tco2e'], site_flights * Decimal('0.10'))

    def test_unaccredited_purchase_is_reported(self):
        good = self._buy(1)
        bad = self._buy(1, registry='other')
        pos = self._position()
        self.assertEqual(pos['unaccredited'], [bad])
        self.assertTrue(good.is_accredited)

    def test_unaccredited_credits_do_not_count_as_cover(self):
        self._buy(5, registry='other')
        pos = self._position()
        self.assertEqual(pos['purchased'], Decimal('0'))
        self.assertEqual(pos['not_counted'], Decimal('5'))
        self.assertEqual(pos['outstanding'], Decimal('2'))
        self.assertFalse(pos['covered'])

    def test_unretired_purchases_are_reported(self):
        self._buy(1, retired=True)
        pending = self._buy(1)
        self.assertEqual(self._position()['unretired'], [pending])

    def test_zero_credit_purchase_is_rejected(self):
        self.client.force_login(self.user)
        self.client.post(f'/projects/{self.project.id}/', {
            'action': 'add_purchase', 'credits_tco2e': '0', 'provider': 'X',
            'registry': 'verra',
        })
        self.assertFalse(CreditPurchase.objects.exists())

    def test_purchase_can_be_recorded_and_retired_on_the_page(self):
        self.client.force_login(self.user)
        self.client.post(f'/projects/{self.project.id}/', {
            'action': 'add_purchase', 'credits_tco2e': '2', 'provider': 'Gold project',
            'registry': 'gold_standard', 'registry_reference': 'GS-1-2-3',
        })
        purchase = CreditPurchase.objects.get(project=self.project)
        self.client.post(f'/projects/{self.project.id}/', {
            'action': 'retire_purchase', 'purchase_id': purchase.id,
        })
        purchase.refresh_from_db()
        self.assertTrue(purchase.retired)
        response = self.client.get(f'/projects/{self.project.id}/')
        self.assertContains(response, 'Carbon credits for travel')
        self.assertContains(response, 'GS-1-2-3')

    def test_cannot_retire_or_remove_another_awards_purchase(self):
        other = Project.objects.create(name='Other', created_by=self.user)
        theirs = CreditPurchase.objects.create(
            project=other, credits_tco2e=Decimal('1'), provider='P')
        self.client.force_login(self.user)
        for action in ('retire_purchase', 'remove_purchase'):
            self.client.post(f'/projects/{self.project.id}/', {
                'action': action, 'purchase_id': theirs.id,
            })
        theirs.refresh_from_db()
        self.assertFalse(theirs.retired)

    def test_outsider_cannot_record_credits(self):
        self.client.force_login(self.outsider)
        response = self.client.post(f'/projects/{self.project.id}/', {
            'action': 'add_purchase', 'credits_tco2e': '2', 'provider': 'X',
            'registry': 'verra',
        })
        self.assertEqual(response.status_code, 404)
        self.assertFalse(CreditPurchase.objects.exists())


class AwardChecklistTest(TestCase):
    """Each Wellcome alignment row reaches every state it can, and quotes the
    policy line it tests (or says plainly that it is good practice)."""

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user('check', 'check@example.com', 'pw')

    def setUp(self):
        self.project = Project.objects.create(name='Checklist Award', created_by=self.user)

    def _states(self):
        fp = project_footprint(self.project)
        rows = award_checklist(self.project, fp, credit_position(self.project, fp))
        return {r['key']: r['state'] for r in rows}

    def _flight(self, **kw):
        fields = dict(project=self.project, date=date(2026, 6, 1), origin='JNB',
                      destination='LHR', mode='air', air_haul='long_haul_uk',
                      cabin_class='economy', distance_km=Decimal('9000'),
                      rail_hours=Decimal('60'), purpose='Annual review')
        fields.update(kw)
        return TravelJourney.objects.create(**fields)

    def _buy(self, credits, registry='verra', retired=False):
        return CreditPurchase.objects.create(
            project=self.project, credits_tco2e=Decimal(str(credits)),
            provider='P', registry=registry, retired=retired)

    def test_empty_award_fails_assessment_and_rest_not_applicable(self):
        states = self._states()
        self.assertEqual(states.pop('assessed'), 'fail')
        self.assertEqual(set(states.values()), {'na'})

    def test_site_without_data_warns_assessment(self):
        facility = Facility.objects.create(
            code_name='CHK_SITE', display_name='Empty', country='ZA',
            sector='research', created_by=self.user)
        ProjectSite.objects.create(project=self.project, facility=facility,
                                   share_pct=Decimal('10'))
        self.assertEqual(self._states()['assessed'], 'warn')

    def test_compliant_flight_passes_travel_rows(self):
        self._flight()
        states = self._states()
        for key in ('assessed', 'justified', 'rail', 'business'):
            self.assertEqual(states[key], 'pass', key)

    def test_unjustified_journey_warns(self):
        self._flight(purpose='')
        self.assertEqual(self._states()['justified'], 'warn')

    def test_rail_within_ten_hours_or_unknown_warns(self):
        for hours in (Decimal('8'), None):
            TravelJourney.objects.all().delete()
            self._flight(rail_hours=hours)
            self.assertEqual(self._states()['rail'], 'warn', hours)

    def test_surface_only_travel_leaves_flight_rows_not_applicable(self):
        TravelJourney.objects.create(
            project=self.project, date=date(2026, 6, 1), origin='A', destination='B',
            mode='rail_national', distance_km=Decimal('300'), purpose='Fieldwork')
        states = self._states()
        self.assertEqual((states['rail'], states['business']), ('na', 'na'))
        self.assertEqual(states['justified'], 'pass')

    def test_business_class_fails(self):
        self._flight(cabin_class='business')
        self.assertEqual(self._states()['business'], 'fail')

    def test_credit_rows_across_states(self):
        self._flight()                       # 9,000 pkm x 0.11704 = 1.05 t -> 2 credits
        states = self._states()
        self.assertEqual(states['mitigated'], 'warn')
        self.assertEqual((states['accredited'], states['retired']), ('na', 'na'))

        purchase = self._buy(2)
        states = self._states()
        self.assertEqual((states['mitigated'], states['accredited'], states['retired']),
                         ('pass', 'pass', 'warn'))

        purchase.retired = True
        purchase.save(update_fields=['retired'])
        self.assertEqual(self._states()['retired'], 'pass')

        self._buy(1, registry='other')
        self.assertEqual(self._states()['accredited'], 'fail')

    def test_rows_quote_policy_except_good_practice(self):
        fp = project_footprint(self.project)
        rows = award_checklist(self.project, fp, credit_position(self.project, fp))
        for r in rows:
            if r['key'] == 'retired':
                self.assertIsNone(r['quote'])
            else:
                self.assertTrue(r['quote'], r['key'])

    def test_award_page_shows_checklist(self):
        self.client.force_login(self.user)
        response = self.client.get(f'/projects/{self.project.id}/')
        self.assertContains(response, 'Wellcome alignment')
        self.assertContains(response, 'Good practice; the policy does not mention this.')

