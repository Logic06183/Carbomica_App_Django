"""
setup_google_auth — configure the Django Sites framework domain and
optionally create the Google SocialApp from environment variables.

Run this once after deployment, before users try to sign in.

Usage:
    python manage.py setup_google_auth
    python manage.py setup_google_auth --domain carbomica-tool.web.app

Environment variables required for full setup:
    GOOGLE_CLIENT_ID   — from GCP Console → APIs & Services → Credentials
    GOOGLE_SECRET      — from GCP Console → APIs & Services → Credentials

How to get Google credentials:
    1. Go to https://console.cloud.google.com/apis/credentials
       (project: carbomica-tool)
    2. Click "Create Credentials" → "OAuth 2.0 Client ID"
    3. Application type: Web application
    4. Add authorised redirect URI:
         https://carbomica-tool.web.app/accounts/google/login/callback/
         http://localhost:8000/accounts/google/login/callback/   (dev)
    5. Copy Client ID and Client Secret to .env or Cloud Run secrets
"""
import os
from django.core.management.base import BaseCommand
from django.contrib.sites.models import Site


class Command(BaseCommand):
    help = 'Configure Sites framework domain for django-allauth Google OAuth'

    def add_arguments(self, parser):
        parser.add_argument(
            '--domain',
            default=os.getenv('SITE_DOMAIN', 'carbomica-tool.web.app'),
            help='The public domain of this deployment (default: carbomica-tool.web.app)',
        )

    def handle(self, *args, **options):
        domain = options['domain']

        # ── 1. Update the Django Sites record ──────────────────────────────
        site, created = Site.objects.update_or_create(
            id=1,
            defaults={'domain': domain, 'name': 'CARBOMICA'},
        )
        action = 'Created' if created else 'Updated'
        self.stdout.write(self.style.SUCCESS(f'{action} Site: {site.domain}'))

        # ── 2. Report credential status ────────────────────────────────────
        client_id = os.getenv('GOOGLE_CLIENT_ID', '')
        secret    = os.getenv('GOOGLE_SECRET', '')

        if client_id and secret:
            self.stdout.write(self.style.SUCCESS(
                'GOOGLE_CLIENT_ID and GOOGLE_SECRET are set in environment.'
            ))
            self.stdout.write(
                'Credentials are used directly from settings — no SocialApp '
                'database entry needed (allauth v65 APP config).'
            )
        else:
            self.stdout.write(self.style.WARNING(
                '\nGOOGLE_CLIENT_ID or GOOGLE_SECRET not found in environment.\n'
                'Google login will not work until these are set.\n'
            ))
            self.stdout.write(self.style.HTTP_INFO(
                'Steps to activate Google login:\n'
                '  1. Go to https://console.cloud.google.com/apis/credentials\n'
                '     (project: carbomica-tool)\n'
                '  2. Create Credentials → OAuth 2.0 Client ID → Web application\n'
                '  3. Add authorised redirect URI:\n'
                f'       https://{domain}/accounts/google/login/callback/\n'
                '       http://localhost:8000/accounts/google/login/callback/\n'
                '  4. Set in .env:\n'
                '       GOOGLE_CLIENT_ID=your-client-id.apps.googleusercontent.com\n'
                '       GOOGLE_SECRET=your-client-secret\n'
                '  5. Re-run: python manage.py setup_google_auth\n'
            ))

        self.stdout.write('\n' + self.style.SUCCESS(
            f'OAuth callback URL to register in GCP:\n'
            f'  https://{domain}/accounts/google/login/callback/\n'
            f'  http://localhost:8000/accounts/google/login/callback/  (local dev)'
        ))
