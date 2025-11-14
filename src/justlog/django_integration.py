# django_integration.py
"""
Django integration for JustLog.

To use JustLog with Django:
1. Add 'justlog.apps.JustLogConfig' to your INSTALLED_APPS in settings.py
2. Add 'justlog.middleware.JustLogMiddleware' to your MIDDLEWARE in settings.py
3. Call setup_logging() in your settings.py after INSTALLED_APPS

Example:
    # settings.py
    INSTALLED_APPS = [
        'django.contrib.admin',
        ...
        'justlog.apps.JustLogConfig',
    ]

    MIDDLEWARE = [
        'django.middleware.security.SecurityMiddleware',
        ...
        'justlog.middleware.JustLogMiddleware',
    ]

    from justlog import setup_logging
    setup_logging('logs/django.log')

The /lg/ endpoint will be available for viewing logs via the middleware.
"""


def setup_django():
    """
    Checks if Django is available.

    This function is called during setup_logging() to detect Django environments.
    With the middleware-based approach, no URL injection is needed.
    """
    try:
        from django.conf import settings
    except ImportError:
        # Django not installed, skip setup
        return

    # With middleware approach, nothing needs to be done here
    # The middleware handles /lg/ requests automatically
