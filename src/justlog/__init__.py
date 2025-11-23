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
    2. Add 'justlog.middleware.JustLogMiddleware' to MIDDLEWARE in settings.py
    3. Call setup_logging() after INSTALLED_APPS is defined
    4. (Optional) Run 'python manage.py migrate' if using database logging
    5. The /lg/ URL endpoint will be available for viewing logs via the middleware

    Example (Django settings.py):
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

        # Basic file logging
        setup_logging('logs/django.log')

        # With database logging (requires migration)
        setup_logging('logs/django.log', use_database=True, db_level=logging.INFO)

    Parameters:
        log_file_path: Path to log file (required)
        level: Minimum level for file logging (default: logging.INFO)
        to_stderr_level: Minimum level for stderr (default: logging.NOTSET)
        max_bytes: Max file size before rotation (default: 1_000_000)
        backup_count: Number of backup files to keep (default: 5)
        backup_days: Days to keep logs (0 = infinite, default: 0)
        logger_name: Internal logger name (default: 'app')
        use_database: Enable database logging (default: False, requires Django)
        db_level: Minimum level for database logging (default: logging.INFO)

    See lg.setup_logging for full parameter documentation.
    """
    result = lg.setup_logging(*args, **kwargs)
    return result

try:
    __version__ = version('justlog')
except PackageNotFoundError:
    # Package not installed yet (development mode)
    __version__ = '0.0.0-dev'