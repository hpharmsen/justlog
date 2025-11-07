# django_integration.py
import logging


def inject_urls():
    """
    Injects /lg URL pattern into Django's URLconf.
    Called by AppConfig.ready() when Django is fully initialized.
    """
    try:
        from django.conf import settings
        from django.urls import path, clear_url_caches
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
                clear_url_caches()

    except Exception as e:
        # Log the error but don't crash the application
        logger = logging.getLogger('justlog')
        logger.warning(f'Failed to inject /lg URL: {e}')


def setup_django():
    """
    Automatically configures Django integration when setup_logging() is called.

    This function:
    1. Detects if Django is available and configured
    2. Adds 'justlog' to INSTALLED_APPS if not already present
    3. Directly injects URLs to ensure /lg/ endpoint is always available

    The URL injection is idempotent and safe to call multiple times.
    If called early (before apps populate), AppConfig.ready() will also inject URLs.
    If called late (during/after apps populate), direct injection ensures /lg/ works.
    """
    try:
        from django.conf import settings
        from django.apps import apps
    except ImportError:
        # Django not installed, skip setup
        return

    try:
        # Add justlog to INSTALLED_APPS if not already present
        if "justlog" not in settings.INSTALLED_APPS:
            settings.INSTALLED_APPS = list(settings.INSTALLED_APPS) + ["justlog"]

        # Only inject URLs if apps are fully loaded
        # Check both apps.ready and apps.app_configs to ensure full initialization
        if apps.ready and apps.app_configs:
            inject_urls()
        # Otherwise, AppConfig.ready() will inject URLs later when apps are ready

    except Exception as e:
        logger = logging.getLogger("justlog")
        logger.warning(f"Failed to setup Django integration: {e}")
