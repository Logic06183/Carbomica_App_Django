"""
Seed a demo consortium partner organisation with two years of organisational
emission entries and an offset purchase, so the footprint module can be
explored immediately after a fresh local install.

Usage:  python manage.py seed_consortium_demo
Login:  demo@consortium.local / carbomica-demo
"""
from datetime import date
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User

from appname.models import Organisation, OrganisationEmissionEntry, OffsetPurchase


class Command(BaseCommand):
    help = 'Seed demo consortium organisation with sample footprint data.'

    def handle(self, *args, **options):
        user, created = User.objects.get_or_create(
            username='demo_consortium',
            defaults={'email': 'demo@consortium.local'},
        )
        if created:
            user.set_password('carbomica-demo')
            user.save()

        org, _ = Organisation.objects.get_or_create(
            name='Wits PHR (demo partner)', created_by=user,
            defaults={'country': 'ZA'},
        )
        org.country = 'ZA'
        org.save(update_fields=['country'])
        org.members.add(user)

        if org.emission_entries.exists():
            self.stdout.write('Demo org already seeded — skipping entries.')
            return

        entries = [
            # 2025
            (2025, 'flights', 61000, 'JNB-LHR x2 return, JNB-NBO x4 return (annual meetings)'),
            (2025, 'fleet_fuel', 1450, 'Field vehicles, RP1/RP2 site visits'),
            (2025, 'grid_electricity', 9200, 'Office, Hillbrow campus share'),
            (2025, 'commuting', 41000, 'Staff commuting estimate, 12 FTE'),
            # 2026
            (2026, 'flights', 54000, 'JNB-LHR x3 return (consortium annual meeting)'),
            (2026, 'fleet_fuel', 1200, 'Field vehicles'),
            (2026, 'grid_electricity', 8000, 'Office'),
            (2026, 'procurement', 6.5, 'Lab consumables, spend-based estimate'),
        ]
        for year, category, qty, desc in entries:
            OrganisationEmissionEntry.objects.create(
                organisation=org, year=year, category=category,
                quantity=qty, description=desc, created_by=user,
            )

        OffsetPurchase.objects.create(
            organisation=org, year=2025, credits_tco2e=25,
            provider='Tree Planting in South African Townships (Verra #720)',
            registry_reference='VCS-720-2025-DEMO',
            cost_usd=375, purchase_date=date(2026, 2, 10),
            retired=True, created_by=user,
        )

        self.stdout.write(self.style.SUCCESS(
            'Seeded demo consortium org. Login: demo@consortium.local / carbomica-demo'
        ))
