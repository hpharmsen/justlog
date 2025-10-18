# django_integration.py
import logging
from typing import Optional


def setup_django():
    """
    Checks if Django is present and configures log viewing endpoint.
    Injects /lg URL pattern and creates a view for displaying logs.
    """
    try:
        import django
        from django.conf import settings
    except ImportError:
        # Django not installed, skip setup
        return

    if not settings.configured:
        # Django not properly configured, skip setup
        return

    try:
        from django.urls import path, clear_url_caches

        # Import the view we'll create
        from .django_views import log_viewer_view

        # Get the root URLconf
        urlconf = __import__(settings.ROOT_URLCONF, {}, {}, [''])

        # Add our URL pattern to urlpatterns
        if hasattr(urlconf, 'urlpatterns'):
            # Check if /lg is already registered
            existing_patterns = [str(p.pattern) for p in urlconf.urlpatterns]
            if 'lg/' not in existing_patterns and 'lg' not in existing_patterns:
                new_pattern = path('lg/', log_viewer_view, name='justlog_viewer')
                urlconf.urlpatterns.append(new_pattern)

                # Clear the URL resolver cache so Django picks up the new pattern
                clear_url_caches()

    except Exception as e:
        print(f'Failed to setup Django integration: {e}')
        # Log the error but don't crash the application
        logger = logging.getLogger('app')
        logger.warning(f'Failed to setup Django integration: {e}')
