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
    has_laboratory = models.BooleanField(
        default=False,
        help_text='The site has laboratories. Wellcome expects labs to hold LEAF, '
                  'My Green Lab or equivalent accreditation.'
    )

    class Meta:
        verbose_name = _('Facility')
        verbose_name_plural = _('Facilities')
        ordering = ['display_name']

    def __str__(self):
        return self.display_name

    @property
    def is_laboratory(self):
        return self.has_laboratory or self.facility_type == 'university_lab'

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

class Project(models.Model):
    """
    A funded award — the unit funders actually care about.

    Organisations answer "who owns the building"; projects answer "what the
    money is for". They cross-cut: one grant runs across several entities, and
    one entity runs many grants. Wellcome's environmental sustainability funding
    policy makes staff time to "assess, measure and report on the award's
    emissions and resource usage" an eligible cost, so the award — not the
    organisation — is what has to be reportable.
    """

    FUNDER_CHOICES = [
        ('wellcome', 'Wellcome Trust'),
        ('nih', 'NIH'),
        ('ukri', 'UKRI'),
        ('gates', 'Gates Foundation'),
        ('eu', 'European Commission'),
        ('samrc', 'South African MRC'),
        ('nrf', 'National Research Foundation (SA)'),
        ('other', 'Other'),
    ]

    # How a project's share of a site's SHARED emissions is derived.
    # Wellcome requires "an auditable record of their time on the project" where
    # staff span multiple awards, so staff FTE is the default: it is the basis
    # the funder has already asked grant holders to keep records for.
    BASIS_FTE = 'fte'
    ALLOCATION_BASIS_CHOICES = [
        (BASIS_FTE, 'Staff FTE share'),
        ('budget', 'Share of site budget'),
        ('space', 'Share of floor / bench space'),
        ('stated', 'Directly stated share'),
    ]

    name = models.CharField(max_length=255)
    grant_reference = models.CharField(
        max_length=100, blank=True,
        help_text='The funder\'s award number, e.g. "225000/Z/22/Z".'
    )
    funder = models.CharField(max_length=20, choices=FUNDER_CHOICES, default='other')
    funder_other = models.CharField(
        max_length=200, blank=True,
        help_text='Funder name when "Other" is selected.'
    )
    principal_investigator = models.CharField(max_length=200, blank=True)
    organisation = models.ForeignKey(
        'Organisation', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='projects',
        help_text='Lead entity holding the award.'
    )
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    budget_usd = models.DecimalField(
        max_digits=14, decimal_places=2, null=True, blank=True,
        validators=[MinValueValidator(0.0)],
        help_text='Total award value in USD.'
    )
    allocation_basis = models.CharField(
        max_length=20, choices=ALLOCATION_BASIS_CHOICES, default=BASIS_FTE,
        help_text='How shared site emissions are apportioned to this award.'
    )
    allocation_note = models.TextField(
        blank=True,
        help_text='The auditable record behind the shares — e.g. "3.2 FTE of '
                  '41.0 FTE at the Bara laboratory, from the 2024 timesheet '
                  'return". Reproduced on the funder report.'
    )
    # Application-stage estimate
    credit_price_usd = models.DecimalField(
        max_digits=8, decimal_places=2, null=True, blank=True,
        validators=[MinValueValidator(0.0)],
        help_text='Price per credit quoted by your provider, used to budget for '
                  'mitigating planned travel. Left blank, no cost is estimated.'
    )
    reduction_measures = models.JSONField(
        default=list, blank=True,
        help_text='Keys from modeling.REDUCTION_MEASURES the award commits to.'
    )
    reduction_notes = models.TextField(
        blank=True, help_text='Other measures, in the applicant\'s own words.'
    )
    created_by = models.ForeignKey(
        User, null=True, blank=True, on_delete=models.SET_NULL,
        related_name='projects',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _('Project')
        verbose_name_plural = _('Projects')
        ordering = ['name']

    def __str__(self):
        return self.name

    @property
    def funder_label(self):
        if self.funder == 'other':
            return self.funder_other or 'Other'
        return self.get_funder_display()

    @property
    def reference_label(self):
        return f'{self.funder_label} · {self.grant_reference}' if self.grant_reference else self.funder_label


class ProjectSite(models.Model):
    """
    A facility an award runs at, and the award's share of that site's shared
    emissions.

    The share applies only to emissions that cannot be attributed directly —
    electricity, waste, shared travel. Procurement lines tagged to this project
    are counted in full instead, and lines tagged to a DIFFERENT project are
    excluded from the pool this share is taken from, so nothing is counted twice.
    """

    project = models.ForeignKey(Project, related_name='sites', on_delete=models.CASCADE)
    facility = models.ForeignKey(
        'Facility', related_name='project_sites', on_delete=models.CASCADE,
    )
    share_pct = models.DecimalField(
        max_digits=6, decimal_places=3,
        validators=[MinValueValidator(0.0), MaxValueValidator(100.0)],
        help_text='Percentage of this site\'s shared emissions attributable to the award.'
    )
    basis_note = models.CharField(
        max_length=255, blank=True,
        help_text='Evidence for this share, e.g. "3.2 of 41.0 FTE".'
    )

    class Meta:
        verbose_name = _('Project Site')
        verbose_name_plural = _('Project Sites')
        ordering = ['-share_pct']
        constraints = [
            models.UniqueConstraint(
                fields=['project', 'facility'], name='unique_project_facility',
            ),
        ]

    def __str__(self):
        return f'{self.project} @ {self.facility} ({self.share_pct}%)'


class TravelJourney(models.Model):
    """
    One journey made for an award.

    Logged journeys are attributed to the award directly. Once an award has any,
    they replace its apportioned share of the site's flights and road travel
    (modeling.SITE_TRAVEL_FIELDS), so the same trip is never counted twice.
    Factors come from DEFRA's 2026 business-travel tables (modeling.AIR_FACTORS,
    modeling.SURFACE_FACTORS); combinations DEFRA does not publish are rejected.
    """

    MODE_CHOICES = [
        ('air', 'Flight'),
        ('rail_national', 'Rail (national)'),
        ('rail_international', 'Rail (international)'),
        ('light_rail', 'Light rail / tram'),
        ('underground', 'Underground / metro'),
        ('bus', 'Local bus'),
        ('coach', 'Coach'),
        ('taxi', 'Taxi'),
        ('car', 'Car (per vehicle)'),
    ]
    HAUL_CHOICES = [
        ('domestic_uk', 'Domestic, within the UK'),
        ('short_haul_uk', 'Short-haul, to/from the UK'),
        ('long_haul_uk', 'Long-haul, to/from the UK'),
        ('international_non_uk', 'International, not touching the UK'),
    ]
    CABIN_CHOICES = [
        ('average', 'Unknown / average'),
        ('economy', 'Economy'),
        ('premium_economy', 'Premium economy'),
        ('business', 'Business'),
        ('first', 'First'),
    ]

    project = models.ForeignKey(Project, related_name='journeys', on_delete=models.CASCADE)
    date = models.DateField()
    traveller = models.CharField(
        max_length=120, blank=True,
        help_text='Role or name, e.g. "PI" or "field coordinator".'
    )
    origin = models.CharField(max_length=120)
    destination = models.CharField(max_length=120)
    mode = models.CharField(max_length=20, choices=MODE_CHOICES)
    air_haul = models.CharField(
        max_length=24, choices=HAUL_CHOICES, blank=True,
        help_text='Flights only. DEFRA factors differ by haul and by whether the '
                  'flight starts or ends in the UK.'
    )
    cabin_class = models.CharField(
        max_length=20, choices=CABIN_CHOICES, blank=True,
        help_text='Flights only.'
    )
    distance_km = models.DecimalField(
        max_digits=10, decimal_places=1, validators=[MinValueValidator(0.1)],
        help_text='Distance of this journey. Log a return trip as two journeys.'
    )
    passengers = models.PositiveIntegerField(
        default=1, validators=[MinValueValidator(1)],
        help_text='People travelling together on this journey. Ignored for car, '
                  'whose factor is per vehicle.'
    )
    rail_hours = models.DecimalField(
        max_digits=5, decimal_places=1, null=True, blank=True,
        validators=[MinValueValidator(0.0)],
        help_text='Flights only: door-to-door time the same trip would take by rail, '
                  'including connections. Wellcome expects rail for trips up to 10 hours.'
    )
    purpose = models.TextField(
        blank=True,
        help_text='Why the trip was needed. Wellcome asks that all travel be justified.'
    )
    is_planned = models.BooleanField(
        default=False,
        help_text='A trip planned in the application, not yet made. Planned trips '
                  'feed the estimate only, never the reported footprint.'
    )
    created_by = models.ForeignKey(
        User, null=True, blank=True, on_delete=models.SET_NULL,
        related_name='journeys',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _('Travel Journey')
        verbose_name_plural = _('Travel Journeys')
        ordering = ['-date', '-id']

    def __str__(self):
        return f'{self.origin} → {self.destination} ({self.get_mode_display()}, {self.date})'

    def clean(self):
        from appname.modeling import journey_factor
        from django.core.exceptions import ValidationError

        if self.mode == 'air':
            if not self.air_haul:
                raise ValidationError({'air_haul': 'Choose the flight type.'})
            self.cabin_class = self.cabin_class or 'average'
            if journey_factor('air', self.air_haul, self.cabin_class) is None:
                raise ValidationError({
                    'cabin_class': (
                        f'DEFRA publishes no factor for {self.get_cabin_class_display()} '
                        f'on a {self.get_air_haul_display().lower()} flight. '
                        'Choose the nearest class it does publish.'
                    ),
                })
        else:
            self.air_haul = ''
            self.cabin_class = ''
            self.rail_hours = None

    def tco2e(self):
        from appname.modeling import journey_tco2e
        return journey_tco2e(
            self.mode, self.distance_km, self.passengers,
            self.air_haul, self.cabin_class,
        )

    def policy_flags(self):
        from appname.modeling import journey_policy_flags
        return journey_policy_flags(self)


class PlannedSpend(models.Model):
    """
    Purchases planned in the application, by procurement category, so the
    estimate can be built before any spend is charged to the award. Uses the
    same spend-based factors as itemised procurement.
    """

    project = models.ForeignKey(Project, related_name='planned_spend', on_delete=models.CASCADE)
    category = models.CharField(
        max_length=40, help_text='Key into modeling.PROCUREMENT_CATEGORIES.'
    )
    description = models.CharField(max_length=255, blank=True)
    spend_usd = models.DecimalField(
        max_digits=14, decimal_places=2, validators=[MinValueValidator(Decimal('0.01'))],
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _('Planned Spend')
        verbose_name_plural = _('Planned Spend')
        ordering = ['-spend_usd']

    def __str__(self):
        return f'{self.category} — {self.spend_usd}'

    def clean(self):
        from appname.modeling import PROCUREMENT_CATEGORIES
        from django.core.exceptions import ValidationError
        if self.category not in PROCUREMENT_CATEGORIES:
            raise ValidationError({'category': 'Unknown procurement category.'})

    @property
    def category_label(self):
        from appname.modeling import PROCUREMENT_CATEGORIES
        return PROCUREMENT_CATEGORIES[self.category]['display_name']

    def tco2e(self):
        from appname.modeling import PROCUREMENT_CATEGORIES
        return self.spend_usd * PROCUREMENT_CATEGORIES[self.category]['factor']


class SustainabilityCost(models.Model):
    """
    A sustainability cost budgeted on the award, under one of the headings
    Wellcome's policy lists as fundable (modeling.ELIGIBLE_COSTS).
    """

    project = models.ForeignKey(
        Project, related_name='sustainability_costs', on_delete=models.CASCADE,
    )
    kind = models.CharField(max_length=40, help_text='Key into modeling.ELIGIBLE_COSTS.')
    description = models.CharField(max_length=255, blank=True)
    amount_usd = models.DecimalField(
        max_digits=12, decimal_places=2, validators=[MinValueValidator(Decimal('0.01'))],
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _('Sustainability Cost')
        verbose_name_plural = _('Sustainability Costs')
        ordering = ['kind', '-amount_usd']

    def __str__(self):
        return f'{self.kind} — {self.amount_usd}'

    def clean(self):
        from appname.modeling import ELIGIBLE_COSTS
        from django.core.exceptions import ValidationError
        if self.kind not in ELIGIBLE_COSTS:
            raise ValidationError({'kind': 'Not a cost heading Wellcome lists.'})

    @property
    def label(self):
        from appname.modeling import ELIGIBLE_COSTS
        return ELIGIBLE_COSTS[self.kind][0]


class LabAccreditation(models.Model):
    """
    A green-lab accreditation held by a site.

    Wellcome: labs should "achieve the minimum level of accreditation offered by
    LEAF, My Green Lab or equivalent by the end of 2025", so any level counts.
    Levels: LEAF awards Bronze, Silver and Gold (UCL LEAF programme page); My
    Green Lab awards "Bronze, Silver, Gold, Platinum, or Green" and
    "Recertification occurs 2 years after certification date" (mygreenlab.org
    green-lab-certification, read 2026-10-17). LEAF validity is not stated on
    its primary page, so a LEAF award lapses only on an expiry date the user
    enters.
    """

    SCHEME_CHOICES = [
        ('leaf', 'LEAF'),
        ('my_green_lab', 'My Green Lab'),
        ('other', 'Other (equivalent scheme)'),
    ]
    LEVEL_CHOICES = [
        ('bronze', 'Bronze'),
        ('silver', 'Silver'),
        ('gold', 'Gold'),
        ('platinum', 'Platinum'),
        ('green', 'Green'),
        ('other', 'Other / not graded'),
    ]
    SCHEME_LEVELS = {
        'leaf': {'bronze', 'silver', 'gold'},
        'my_green_lab': {'bronze', 'silver', 'gold', 'platinum', 'green'},
    }
    MGL_RECERTIFY_YEARS = 2

    facility = models.ForeignKey(
        Facility, related_name='lab_accreditations', on_delete=models.CASCADE,
    )
    lab_name = models.CharField(
        max_length=200, blank=True, help_text='Which lab, if the site has several.'
    )
    scheme = models.CharField(max_length=20, choices=SCHEME_CHOICES)
    level = models.CharField(max_length=20, choices=LEVEL_CHOICES)
    awarded_on = models.DateField()
    expires_on = models.DateField(
        null=True, blank=True,
        help_text='Leave blank for My Green Lab to use its 2-year recertification date.'
    )
    evidence_url = models.URLField(blank=True, help_text='Certificate or listing.')
    created_by = models.ForeignKey(
        User, null=True, blank=True, on_delete=models.SET_NULL,
        related_name='lab_accreditations',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _('Lab Accreditation')
        verbose_name_plural = _('Lab Accreditations')
        ordering = ['-awarded_on', '-id']

    def __str__(self):
        return f'{self.get_scheme_display()} {self.get_level_display()} — {self.facility}'

    def clean(self):
        from django.core.exceptions import ValidationError
        allowed = self.SCHEME_LEVELS.get(self.scheme)
        if allowed is not None and self.level not in allowed:
            raise ValidationError({'level': (
                f'{self.get_scheme_display()} does not award '
                f'{self.get_level_display()}.'
            )})
        if self.expires_on and self.awarded_on and self.expires_on < self.awarded_on:
            raise ValidationError({'expires_on': 'Expiry is before the award date.'})

    @property
    def valid_until(self):
        if self.expires_on:
            return self.expires_on
        if self.scheme == 'my_green_lab' and self.awarded_on:
            try:
                return self.awarded_on.replace(
                    year=self.awarded_on.year + self.MGL_RECERTIFY_YEARS)
            except ValueError:  # 29 February
                return self.awarded_on.replace(
                    year=self.awarded_on.year + self.MGL_RECERTIFY_YEARS, day=28)
        return None

    def is_current(self, on_date):
        until = self.valid_until
        return self.awarded_on <= on_date and (until is None or until >= on_date)


class CreditPurchase(models.Model):
    """
    Carbon credits bought to mitigate an award's remaining travel emissions.

    Wellcome's policy asks grant holders to "Mitigate the remaining carbon
    emissions of all journeys using accredited carbon credits" and makes the
    cost eligible. One credit is counted as one tonne CO₂e: Verra states each
    Verified Carbon Unit "represents a reduction or removal of one tonne of
    CO2e" (VCS Program Details, read 2026-10-17).
    """

    REGISTRY_CHOICES = [
        ('verra', 'Verra (VCS)'),
        ('gold_standard', 'Gold Standard'),
        ('plan_vivo', 'Plan Vivo'),
        ('woodland_carbon_code', 'Woodland Carbon Code'),
        ('other', 'Other / not accredited'),
    ]
    # The four standards Wellcome names as examples of third-party accreditation.
    ACCREDITED_REGISTRIES = {'verra', 'gold_standard', 'plan_vivo', 'woodland_carbon_code'}

    project = models.ForeignKey(
        Project, related_name='credit_purchases', on_delete=models.CASCADE,
    )
    credits_tco2e = models.DecimalField(
        max_digits=10, decimal_places=2, validators=[MinValueValidator(Decimal('0.01'))],
        help_text='Credits bought (1 credit = 1 tCO₂e).'
    )
    provider = models.CharField(
        max_length=200, help_text='Project or broker the credits came from.'
    )
    registry = models.CharField(max_length=32, choices=REGISTRY_CHOICES, default='verra')
    registry_reference = models.CharField(
        max_length=255, blank=True,
        help_text='Registry serial or retirement reference, for audit.'
    )
    cost_usd = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True,
        validators=[MinValueValidator(0.0)],
    )
    purchase_date = models.DateField(null=True, blank=True)
    retired = models.BooleanField(
        default=False, help_text='Credits retired on the registry in the award\'s name.'
    )
    created_by = models.ForeignKey(
        User, null=True, blank=True, on_delete=models.SET_NULL,
        related_name='credit_purchases',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _('Credit Purchase')
        verbose_name_plural = _('Credit Purchases')
        ordering = ['-purchase_date', '-id']

    def __str__(self):
        return f'{self.credits_tco2e} credits — {self.provider}'

    @property
    def is_accredited(self):
        return self.registry in self.ACCREDITED_REGISTRIES


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
    project = models.ForeignKey(
        Project, null=True, blank=True, on_delete=models.SET_NULL,
        related_name='procurement_lines',
        help_text='Award this purchase was charged to. Tagged lines are '
                  'attributed to that award in full rather than apportioned.'
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
