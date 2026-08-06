"""
Seed the REAL consortium structure — no synthetic activity data.

Creates the Wits Planetary Health partner organisation for the Southern
Africa Consortium for Climate Change and Health (Wellcome Climate Science
and Policy Centres Africa, grant ref 336423/Z/25/Z), with:
  - country ZA (IEA electricity factor)
  - the consortium's selected interim offset provider noted in help text
    (Tree Planting in South African Townships, Verra registry project #720;
    transition to GreenPop planned once accredited)
  - NO emission entries and NO purchases: actuals are entered by the team.

A local login user is created so the module can be opened immediately.
Usage:  python manage.py seed_consortium [--email you@example.org]
"""
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User

from appname.models import Organisation


class Command(BaseCommand):
    help = 'Seed the real consortium partner structure (no synthetic data).'

    def add_arguments(self, parser):
        parser.add_argument('--email', default='craig.parker@witsphr.org',
                            help='Email for the local login user.')

    def handle(self, *args, **options):
        email = options['email']
        username = email.split('@')[0].replace('.', '_')
        user, created = User.objects.get_or_create(
            username=username, defaults={'email': email},
        )
        if created:
            user.set_password('carbomica-local')
            user.save()

        org, org_created = Organisation.objects.get_or_create(
            name='Wits Planetary Health',
            created_by=user,
            defaults={
                'country': 'ZA',
                'wellcome_grant_ref': '336423/Z/25/Z',
            },
        )
        org.members.add(user)
        if not org_created:
            org.country = 'ZA'
            org.wellcome_grant_ref = '336423/Z/25/Z'
            org.save(update_fields=['country', 'wellcome_grant_ref'])

        self.stdout.write(self.style.SUCCESS(
            f'Consortium structure ready. Login: {email} / carbomica-local\n'
            'No activity data was seeded — enter real flights, fleet, electricity, '
            'commuting and procurement figures on the footprint page.\n'
            'Interim offset provider per the consortium decision: '
            'Tree Planting in South African Townships (Verra registry project #720); '
            'transition to GreenPop planned once accredited.'
        ))
