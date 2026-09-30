from decimal import Decimal

from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from django.contrib.auth.models import User

class Organisation(models.Model):
    """
    A node in an organisational tree whose members share access to facilities.

    Organisations nest, because research groups do. Wits Health Consortium is an
    umbrella over 100+ research entities (Perinatal HIV Research Unit, VIDA,
    Wits RHI, Agincourt, Wits Planetary Health ...), grouped into divisions, and
    the larger entities run their own programmes. A self-referential parent
    models that to any depth rather than hard-coding a fixed consortium →
    entity → site scheme.

    Membership grants access downward: a consortium sustainability lead sees
    every entity beneath them, while an entity's own members see only their
    own subtree.
    """

    ORG_TYPE_CHOICES = [
        ('consortium', 'Consortium / umbrella body'),
        ('division', 'Division / grouping'),
        ('entity', 'Research entity / institute / unit'),
        ('programme', 'Programme / team'),
    ]

    name = models.CharField(max_length=200)
    short_name = models.CharField(
        max_length=40, blank=True,
        help_text='Acronym shown in compact views, e.g. "PHRU", "VIDA".'
    )
    parent = models.ForeignKey(
        'self', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='children',
        help_text='The organisation this one sits under. Blank for a top-level body.'
    )
    org_type = models.CharField(
        max_length=20, choices=ORG_TYPE_CHOICES, default='entity',
        help_text='Where this sits in the hierarchy. Affects roll-up reporting only.'
    )
    created_by = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='owned_organisations'
    )
    members = models.ManyToManyField(
        User, related_name='organisations', blank=True,
        help_text='Users who can access all facilities in this organisation '
                  'and every organisation beneath it.'
    )

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name

    # ------------------------------------------------------------------
    # Tree helpers
    #
    # Walked iteratively in Python rather than with a recursive CTE: the
    # trees are small (hundreds of nodes at most), it stays portable across
    # SQLite and Postgres, and every walk is guarded against cycles, which a
    # self-FK makes possible if a parent is ever set to a descendant.
    # ------------------------------------------------------------------

    def ancestors(self):
        """Parent chain, nearest first. Excludes self."""
        chain, node, seen = [], self.parent, {self.pk}
        while node is not None and node.pk not in seen:
            chain.append(node)
            seen.add(node.pk)
            node = node.parent
        return chain

    def descendant_ids(self, include_self=True):
        """PKs of this organisation and everything beneath it."""
        collected = {self.pk} if include_self else set()
        frontier, seen = [self.pk], {self.pk}
        while frontier:
            child_ids = list(
                Organisation.objects
                .filter(parent_id__in=frontier)
                .exclude(pk__in=seen)
                .values_list('pk', flat=True)
            )
            if not child_ids:
                break
            collected.update(child_ids)
            seen.update(child_ids)
            frontier = child_ids
        return collected

    def descendants(self, include_self=False):
        ids = self.descendant_ids(include_self=include_self)
        return Organisation.objects.filter(pk__in=ids)

    @property
    def depth(self):
        return len(self.ancestors())

    @property
    def display_label(self):
        return f'{self.name} ({self.short_name})' if self.short_name else self.name

    def all_facilities(self):
        """Facilities belonging to this organisation or any beneath it."""
        return Facility.objects.filter(organisation_id__in=self.descendant_ids())

    def is_ancestor_of(self, other):
        return other is not None and other.pk in self.descendant_ids(include_self=False)


class Facility(models.Model):
    COUNTRY_CHOICES = [
        # Sub-Saharan Africa (HIGH Horizons partner countries first)
        ('ZW', 'Zimbabwe'),
        ('ZA', 'South Africa'),
        ('KE', 'Kenya'),
        ('TZ', 'Tanzania'),
        ('UG', 'Uganda'),
        ('NG', 'Nigeria'),
        ('GH', 'Ghana'),
        # South Asia
        ('IN', 'India'),
        ('BD', 'Bangladesh'),
        # Donor / OECD (for grant applicants based in donor countries)
        ('GB', 'United Kingdom'),
        ('US', 'United States'),
        ('EU', 'European Union (avg)'),
        ('OTHER', 'Other'),
    ]

    # Wider facility-type catalogue for Verdex commercial edition.
    # Grouped by sector for legibility — choices are flat values stored in DB.
    FACILITY_TYPE_CHOICES = [
        # Clinical
        ('district_hospital', 'District Hospital'),
        ('provincial_hospital', 'Provincial Hospital'),
        ('central_hospital', 'Central Hospital'),
        ('health_centre', 'Health Centre / Clinic'),
        ('community_clinic', 'Community Clinic'),
        ('specialty_clinic', 'Specialty Clinic (dental, eye, etc.)'),
        ('maternity_unit', 'Maternity Unit'),
        # Research
        ('research_office', 'Research Organisation Office'),
        ('university_lab', 'University Research Lab'),
        ('university_dept', 'University Department / Faculty'),
        # NGO
        ('ngo_office', 'NGO Headquarters Office'),
        ('ngo_field_office', 'NGO Field Office'),
        # Education
        ('school', 'School'),
        # Government / Authority
        ('govt_office', 'Government Office'),
        ('regional_health_authority', 'Regional Health Authority'),
        ('ministry', 'Ministry / Department'),
        # Business
        ('sme_office', 'Small / Medium Business Office'),
        ('corporate_office', 'Corporate Office'),
        ('factory', 'Factory / Manufacturing'),
        ('warehouse', 'Warehouse / Distribution'),
        # Catch-all
        ('other', 'Other'),
    ]

    SECTOR_CHOICES = [
        ('clinical', 'Clinical / Healthcare'),
        ('research', 'Research / Academic'),
        ('ngo', 'NGO / Non-profit'),
        ('education', 'Education'),
        ('government', 'Government / Public Authority'),
        ('business', 'Business / Commercial'),
        ('other', 'Other'),
    ]

    code_name = models.CharField(max_length=100)
    display_name = models.CharField(max_length=100)
    country = models.CharField(max_length=10, choices=COUNTRY_CHOICES, default='OTHER')
    facility_type = models.CharField(
        max_length=50, choices=FACILITY_TYPE_CHOICES, default='district_hospital'
    )
    sector = models.CharField(
        max_length=20,
        choices=SECTOR_CHOICES,
        default='clinical',
        help_text='Higher-level grouping. Used for sector-appropriate intervention curation and grant-report templates.',
    )
    created_by = models.ForeignKey(
        User, null=True, blank=True, on_delete=models.SET_NULL,
        related_name='facilities',
        help_text='User who registered this facility (set automatically on login).'
    )
    organisation = models.ForeignKey(
        'Organisation', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='facilities',
        help_text='Organisation this facility belongs to. All org members can access it.'
    )

    class Meta:
        verbose_name = _('Facility')
        verbose_name_plural = _('Facilities')
        ordering = ['display_name']

    def __str__(self):
        return self.display_name

class EmissionSource(models.Model):
    facility = models.ForeignKey(Facility, related_name='emission_sources', on_delete=models.CASCADE)
    code_name = models.CharField(max_length=100)
    display_name = models.CharField(max_length=100)

    class Meta:
        verbose_name = _('Emission Source')
        verbose_name_plural = _('Emission Sources')
        ordering = ['display_name']

    def __str__(self):
        return self.display_name

class EmissionData(models.Model):
    emission_source = models.ForeignKey(EmissionSource, related_name='emission_data', on_delete=models.CASCADE)
    date = models.DateField(default=timezone.now)
    grid_electricity = models.DecimalField(default=0.0, max_digits=10, decimal_places=2, validators=[MinValueValidator(0.0)])
    grid_gas = models.DecimalField(default=0.0, max_digits=10, decimal_places=2, validators=[MinValueValidator(0.0)])
    bottled_gas = models.DecimalField(default=0.0, max_digits=10, decimal_places=2, validators=[MinValueValidator(0.0)])
    liquid_fuel = models.DecimalField(default=0.0, max_digits=10, decimal_places=2, validators=[MinValueValidator(0.0)])
    vehicle_fuel_owned = models.DecimalField(default=0.0, max_digits=10, decimal_places=2, validators=[MinValueValidator(0.0)])
    business_travel = models.DecimalField(default=0.0, max_digits=10, decimal_places=2, validators=[MinValueValidator(0.0)])
    anaesthetic_gases = models.DecimalField(default=0.0, max_digits=10, decimal_places=2, validators=[MinValueValidator(0.0)])
    refrigeration_gases = models.DecimalField(default=0.0, max_digits=10, decimal_places=2, validators=[MinValueValidator(0.0)])
    waste_management = models.DecimalField(default=0.0, max_digits=10, decimal_places=2, validators=[MinValueValidator(0.0)])
    medical_inhalers = models.DecimalField(default=0.0, max_digits=10, decimal_places=2, validators=[MinValueValidator(0.0)])
    contractor_logistics = models.DecimalField(
        default=0.0, max_digits=10, decimal_places=2, validators=[MinValueValidator(0.0)],
        help_text='Scope 3 — km travelled by contracted vehicles (supply deliveries, waste collection, etc.)'
    )
    flights = models.DecimalField(
        default=0.0, max_digits=12, decimal_places=2, validators=[MinValueValidator(0.0)],
        help_text='Scope 3 — passenger-km flown for work travel (conferences, fieldwork, meetings).'
    )
    lab_consumables = models.DecimalField(
        default=0.0, max_digits=12, decimal_places=2, validators=[MinValueValidator(0.0)],
        help_text='Scope 3 — annual spend (USD) on lab consumables, reagents and equipment '
                  'procurement. Converted with spend-based EEIO factors.'
    )

    class Meta:
        verbose_name = _('Emission Data')
        verbose_name_plural = _('Emission Data Entries')
        ordering = ['-emission_source__display_name']

    def __str__(self):
        return f"{self.emission_source.display_name} Emission Data"

    def total_emissions(self):
        """Sum of raw usage values (not tCO₂e). Use compute_tco2e() from modeling.py for converted totals."""
        return (
            self.grid_electricity + self.grid_gas + self.bottled_gas +
            self.liquid_fuel + self.vehicle_fuel_owned + self.business_travel +
            self.anaesthetic_gases + self.refrigeration_gases +
            self.waste_management + self.medical_inhalers + self.contractor_logistics +
            self.flights + self.lab_consumables
        )

class ProcurementLine(models.Model):
    """
    One line of purchased goods or services for a reporting period.

    Attached to an EmissionData record rather than to the facility directly:
    that record already defines "this site, this period", so lines cannot drift
    out of alignment with the baseline they belong to, and they can be
    prefetched alongside it when computing a footprint.

    When any lines exist for a record they REPLACE that record's single blended
    lab_consumables estimate, so the two can never be counted together.
    """

    SOURCE_CHOICES = [
        ('CSV', 'Imported from spend export'),
        ('MANUAL', 'Entered by hand'),
    ]

    emission_data = models.ForeignKey(
        EmissionData, related_name='procurement_lines', on_delete=models.CASCADE,
    )
    category = models.CharField(
        max_length=40,
        help_text='Key into modeling.PROCUREMENT_CATEGORIES. Unrecognised '
                  'categories are stored as OTHER at import.'
    )
    description = models.CharField(max_length=255, blank=True)
    supplier = models.CharField(
        max_length=255, blank=True,
        help_text='Captured for future supplier-level comparison. Not used in '
                  'the calculation.'
    )
    spend_usd = models.DecimalField(
        max_digits=14, decimal_places=2, validators=[MinValueValidator(0.0)],
        help_text='Spend for this line in USD.'
    )
    source = models.CharField(max_length=10, choices=SOURCE_CHOICES, default='MANUAL')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _('Procurement Line')
        verbose_name_plural = _('Procurement Lines')
        ordering = ['-spend_usd']
        indexes = [models.Index(fields=['emission_data', 'category'])]

    def __str__(self):
        return f'{self.category} — {self.spend_usd}'

    @property
    def spec(self):
        from appname.modeling import PROCUREMENT_CATEGORIES
        return PROCUREMENT_CATEGORIES.get(self.category) or PROCUREMENT_CATEGORIES['OTHER']

    @property
    def category_label(self):
        return self.spec['display_name']

    def tco2e(self):
        return (self.spend_usd or Decimal('0')) * self.spec['factor']


class Intervention(models.Model):
    code_name = models.CharField(max_length=100)
    display_name = models.CharField(max_length=100)
    status = models.CharField(
        max_length=50,
        choices=[
            ('Planned', 'Planned'),
            ('In Progress', 'In Progress'),
            ('Completed', 'Completed'),
            ('Cancelled', 'Cancelled')
        ],
        default='Planned'
    )
    description = models.TextField(blank=True)
    emission_reduction_percentage = models.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        validators=[MinValueValidator(0.0), MaxValueValidator(100.0)],
        help_text="Expected percentage reduction in emissions",
        default=0.0
    )
    payback_period = models.IntegerField(
        validators=[MinValueValidator(0)],
        help_text="Expected payback period in months",
        default=0
    )
    energy_savings = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0.0)],
        help_text="Expected annual energy savings in kWh",
        default=0.0
    )
    sdg_goals = models.CharField(
        max_length=50,
        blank=True,
        default='',
        help_text="Comma-separated SDG numbers this intervention contributes to (e.g. '3,7,13')"
    )
    target_category = models.CharField(
        max_length=200, blank=True, default='',
        help_text="Comma-separated EmissionData field names this intervention targets "
                  "(e.g. 'grid_electricity' or 'grid_electricity,vehicle_fuel_owned'). "
                  "Used by the optimizer to apply reductions to the correct emission category."
    )
    applicable_sectors = models.CharField(
        max_length=100, blank=True, default='',
        help_text="Comma-separated Facility sector keys this intervention applies to "
                  "(e.g. 'clinical'). Empty = applies to every sector."
    )

    def applies_to_sector(self, sector):
        if not self.applicable_sectors:
            return True
        return sector in [s.strip() for s in self.applicable_sectors.split(',')]

    class Meta:
        verbose_name = _('Intervention')
        verbose_name_plural = _('Interventions')
        ordering = ['display_name']

    def __str__(self):
        return self.display_name

class FacilityIntervention(models.Model):
    facility = models.ForeignKey(Facility, related_name='facility_interventions', on_delete=models.CASCADE)
    intervention = models.ForeignKey(Intervention, related_name='facility_interventions', on_delete=models.CASCADE)
    implementation_cost = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        validators=[MinValueValidator(0.0)]
    )
    maintenance_cost = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        validators=[MinValueValidator(0.0)]
    )
    annual_savings = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0.0)],
        default=0.0
    )
    emission_reduction_achieved = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0.0)],
        default=0.0,
        help_text="Actual emission reduction achieved in tCO2e"
    )
    implementation_date = models.DateField(null=True, blank=True)
    roi = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        validators=[MinValueValidator(0.0)],
        default=0.0,
        help_text="Return on Investment percentage"
    )
    cost_source = models.CharField(
        max_length=16,
        default='USER',
        choices=[
            ('USER', 'User-supplied'),
            ('DEFAULT', 'Library default'),
            ('PLACEHOLDER', 'Placeholder median'),
        ],
        help_text="Provenance of cost values — used for rollback and 'verify before reporting' UI badges.",
    )

    class Meta:
        verbose_name = _('Facility Intervention')
        verbose_name_plural = _('Facility Interventions')
        ordering = ['facility__display_name']
        constraints = [
            models.UniqueConstraint(
                fields=['facility', 'intervention'],
                name='uniq_facility_intervention',
            ),
        ]

    def calculate_roi(self):
        """Return computed ROI percentage without mutating the instance."""
        total_cost = (self.implementation_cost or 0) + (self.maintenance_cost or 0)
        if total_cost > 0:
            return (self.annual_savings / total_cost) * 100
        return self.roi

    def __str__(self):
        return f"{self.facility.display_name} - {self.intervention.display_name}"

class InterventionEffect(models.Model):
    intervention = models.ForeignKey(Intervention, related_name='effects', on_delete=models.CASCADE)
    facility = models.ForeignKey(Facility, related_name='intervention_effects', on_delete=models.CASCADE)
    effect_size = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0.0)])

    class Meta:
        verbose_name = _('Intervention Effect')
        verbose_name_plural = _('Intervention Effects')
        ordering = ['facility__display_name']

    def __str__(self):
        return f"{self.facility.display_name} - {self.intervention.display_name}"

class OptimizationScenario(models.Model):
    facility = models.ForeignKey(Facility, related_name='optimization_scenarios', on_delete=models.CASCADE)
    name = models.CharField(max_length=100)
    budget = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(0.0)])
    target_reduction = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        validators=[MinValueValidator(0.0), MaxValueValidator(100.0)],
        help_text="Target emission reduction percentage"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(
        max_length=50,
        choices=[
            ('Draft', 'Draft'),
            ('Optimized', 'Optimized'),
            ('Implemented', 'Implemented')
        ],
        default='Draft'
    )

    class Meta:
        verbose_name = _('Optimization Scenario')
        verbose_name_plural = _('Optimization Scenarios')
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.facility.display_name} - {self.name}"

class OptimizationResult(models.Model):
    scenario = models.ForeignKey(OptimizationScenario, related_name='results', on_delete=models.CASCADE)
    intervention = models.ForeignKey(Intervention, on_delete=models.CASCADE)
    priority = models.IntegerField(validators=[MinValueValidator(1)])
    expected_roi = models.DecimalField(max_digits=6, decimal_places=2)
    emission_reduction = models.DecimalField(max_digits=10, decimal_places=2)
    implementation_cost = models.DecimalField(max_digits=12, decimal_places=2)
    annual_savings = models.DecimalField(max_digits=12, decimal_places=2)
    payback_months = models.IntegerField()

    class Meta:
        verbose_name = _('Optimization Result')
        verbose_name_plural = _('Optimization Results')
        ordering = ['priority']

    def __str__(self):
        return f"{self.scenario.name} - {self.intervention.display_name}"

class EffectSize(models.Model):
    facility = models.ForeignKey(Facility, related_name='effect_sizes', on_delete=models.CASCADE)
    recycling_waste_segregation = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0.0)])
    solar_system_installation = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0.0)])
    # Add other fields as per your 'effect sizes' sheet

    class Meta:
        verbose_name = _('Effect Size')
        verbose_name_plural = _('Effect Sizes')
        ordering = ['facility__display_name']

class ImplementationCost(models.Model):
    facility = models.ForeignKey(Facility, related_name='implementation_costs', on_delete=models.CASCADE)
    recycling_waste_segregation = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0.0)])
    solar_system_installation = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0.0)])
    # Add other fields as per your 'implementation costs' sheet

    class Meta:
        verbose_name = _('Implementation Cost')
        verbose_name_plural = _('Implementation Costs')
        ordering = ['facility__display_name']

class MaintenanceCost(models.Model):
    facility = models.ForeignKey(Facility, related_name='maintenance_costs', on_delete=models.CASCADE)
    recycling_waste_segregation = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0.0)])
    solar_system_installation = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0.0)])
    # Add other fields as per your 'maintenance costs' sheet

    class Meta:
        verbose_name = _('Maintenance Cost')
        verbose_name_plural = _('Maintenance Costs')
        ordering = ['facility__display_name']

class Policy(models.Model):
    name = models.CharField(max_length=200)
    description = models.TextField()
    compliance_score = models.IntegerField(
        validators=[MinValueValidator(0)],
        default=0
    )
    implementation_date = models.DateField()
    status = models.CharField(
        max_length=50,
        choices=[
            ('Draft', 'Draft'),
            ('Active', 'Active'),
            ('Under Review', 'Under Review'),
            ('Archived', 'Archived')
        ],
        default='Draft'
    )

    class Meta:
        verbose_name = _('Policy')
        verbose_name_plural = _('Policies')
        ordering = ['name']

    def __str__(self):
        return self.name
