"""JustLog - A simple, flexible logging utility for Python applications."""

from importlib.metadata import version, PackageNotFoundError

from .log import lg, _LoggerProxy

# Export the main interface
__all__ = ['lg', 'setup_logging']

# Convenience function that delegates to lg.setup_logging and sets up Django integration
def setup_logging(*args, **kwargs):
    """
    Configure logging with automatic Django integration.

    For Django projects:
    1. Add 'justlog.apps.JustLogConfig' to INSTALLED_APPS in settings.py
    2. Call setup_logging() after INSTALLED_APPS is defined
    3. The /lg/ URL endpoint will be automatically injected for viewing logs

    Example (Django settings.py):
        INSTALLED_APPS = [
            'django.contrib.admin',
            ...
            'justlog.apps.JustLogConfig',
        ]

        from justlog import setup_logging
        setup_logging('logs/django.log')

    See lg.setup_logging for full parameter documentation.
    """
    result = lg.setup_logging(*args, **kwargs)
    return result

try:
    __version__ = version('justlog')
except PackageNotFoundError:
    # Package not installed yet (development mode)
    __version__ = '0.0.0-dev'