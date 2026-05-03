"""
Custom middleware for the Verdex preview deployment.

`DemoAutoLoginMiddleware` auto-logs every visitor in as a shared
'demo_guest' user when settings.DEMO_MODE is True. This lets the
preview deployment work without configuring Google OAuth for the new
domain — visitors land directly on the app without signing in.

WARNING: Only safe in a deployment where ALL data is treated as
ephemeral / demo. Never enable in production with real users.
"""
from django.conf import settings
from django.contrib.auth import login
from django.contrib.auth.models import User


DEMO_USERNAME = 'demo_guest'
DEMO_EMAIL = 'demo@verdex.local'


class DemoAutoLoginMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if getattr(settings, 'DEMO_MODE', False) and not request.user.is_authenticated:
            user, created = User.objects.get_or_create(
                username=DEMO_USERNAME,
                defaults={
                    'email': DEMO_EMAIL,
                    'first_name': 'Demo',
                    'last_name': 'Guest',
                },
            )
            # Use the ModelBackend explicitly — auto-login bypasses any
            # social-account flow allauth would otherwise enforce.
            login(request, user, backend='django.contrib.auth.backends.ModelBackend')
        return self.get_response(request)
