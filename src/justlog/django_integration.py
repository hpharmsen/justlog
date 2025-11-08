# django_integration.py
"""
Django integration for JustLog.

To use JustLog with Django:
1. Add 'justlog.apps.JustLogConfig' to your INSTALLED_APPS in settings.py
2. Call setup_logging() in your settings.py after INSTALLED_APPS
3. The /lg/ endpoint will be automatically available for viewing logs

Example:
    # settings.py
    INSTALLED_APPS = [
        'django.contrib.admin',
        ...
        'justlog.apps.JustLogConfig',
    ]

    from justlog import setup_logging
    setup_logging('logs/django.log')
"""
import logging


def inject_urls():
    """
    Injects /lg URL pattern into Django's URLconf.

    Called by AppConfig.ready() when Django is fully initialized.
    This function is idempotent and safe to call multiple times.
    """
    try:
        from django.conf import settings
        from django.urls import path, clear_url_caches
        from .django_views import log_viewer_view

        # Get the root URLconf module
        urlconf = __import__(settings.ROOT_URLCONF, {}, {}, [''])

        # Add our URL pattern to urlpatterns if not already present
        if hasattr(urlconf, 'urlpatterns'):
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
    Checks if Django is available and attempts to inject the /lg/ endpoint.

    Note: This function requires that 'justlog.apps.JustLogConfig' is added to
    INSTALLED_APPS before setup_logging() is called. If the app is not in
    INSTALLED_APPS, URL injection may fail silently.
    """
    try:
        from django.conf import settings
    except ImportError:
        # Django not installed, skip setup
        return

    # Injection will succeed if called after apps are loaded (via AppConfig.ready)
    # If called too early (during settings import), it will be retried by AppConfig
    try:
        inject_urls()
    except Exception as e:
        # Silently ignore - AppConfig.ready() will retry if needed
        pass
