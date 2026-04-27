"""
backfill_facility_interventions — populate FacilityIntervention rows for
every existing Facility, using the same _seed_facility_interventions
helper that runs on facility creation.

Idempotent: relies on the unique constraint (facility, intervention)
added in migration 0011 + bulk_create(ignore_conflicts=True).

Usage:
    python manage.py backfill_facility_interventions
    python manage.py backfill_facility_interventions --dry-run

Rollback (only deletes auto-attached rows, never user-edited ones):
    python manage.py shell -c "from appname.models import FacilityIntervention; \
        FacilityIntervention.objects.exclude(cost_source='USER').delete()"
"""
from django.core.management.base import BaseCommand
from django.db import transaction

from appname.models import Facility, FacilityIntervention
from appname.views import _seed_facility_interventions


class Command(BaseCommand):
    help = 'Backfill FacilityIntervention rows for every existing Facility.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Report what would be created without writing.',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        facilities = Facility.objects.all()
        self.stdout.write(f'Found {facilities.count()} facilities.')

        total_created = 0
        for facility in facilities:
            existing = FacilityIntervention.objects.filter(facility=facility).count()
            if dry_run:
                self.stdout.write(
                    f'  [DRY] {facility.display_name}: {existing} existing rows, '
                    f'would seed remaining.'
                )
                continue
            with transaction.atomic():
                created, skipped = _seed_facility_interventions(facility)
            total_created += created
            self.stdout.write(
                f'  {facility.display_name}: +{created} created, {skipped} already present.'
            )

        if dry_run:
            self.stdout.write(self.style.WARNING('Dry run — no rows written.'))
        else:
            self.stdout.write(self.style.SUCCESS(
                f'\nDone — {total_created} new FacilityIntervention rows created.'
            ))
