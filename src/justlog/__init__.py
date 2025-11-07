"""JustLog - A simple, flexible logging utility for Python applications."""

from importlib.metadata import version, PackageNotFoundError

from .log import lg, _LoggerProxy

# Export the main interface
__all__ = ['lg', 'setup_logging']

# Convenience function that delegates to lg.setup_logging and sets up Django integration
def setup_logging(*args, **kwargs):
    """
    Configure logging with automatic Django integration.

    In Django projects, this automatically:
    - Sets up the logging system
    - Adds justlog to INSTALLED_APPS
    - Injects the /lg/ URL endpoint for viewing logs in the browser

    See lg.setup_logging for full parameter documentation.
    """
    result = lg.setup_logging(*args, **kwargs)
    return result

try:
    __version__ = version('justlog')
except PackageNotFoundError:
    # Package not installed yet (development mode)
    __version__ = '0.0.0-dev'