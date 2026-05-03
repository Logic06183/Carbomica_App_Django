"""
Template context processors that expose deployment-time brand and mode
flags to every rendered template.

Configured in settings.TEMPLATES[0]['OPTIONS']['context_processors'].
"""
from django.conf import settings


def brand(request):
    """Expose brand_name, brand_edition, demo_mode to templates."""
    return {
        'BRAND_NAME': getattr(settings, 'BRAND_NAME', 'CARBOMICA'),
        'BRAND_EDITION': getattr(settings, 'BRAND_EDITION', 'eu'),
        'DEMO_MODE': getattr(settings, 'DEMO_MODE', False),
    }
