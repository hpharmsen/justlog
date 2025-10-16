"""JustLog - A simple, flexible logging utility for Python applications."""

from .log import lg, _LoggerProxy
from .django_integration import setup_django

# Export the main interface
__all__ = ['lg', 'setup_logging']

# Convenience function that delegates to lg.setup_logging and sets up Django integration
def setup_logging(*args, **kwargs):
    """
    Configure logging and Django integration.
    See lg.setup_logging for full documentation.
    """
    result = lg.setup_logging(*args, **kwargs)
    setup_django()
    return result

__version__ = '0.1.0'