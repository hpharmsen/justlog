"""JustLog - A simple, flexible logging utility for Python applications."""

from .log import lg, _LoggerProxy

# Export the main interface
__all__ = ['lg', 'setup_logging']

# Convenience function that delegates to lg.setup_logging
def setup_logging(*args, **kwargs):
    """Configure logging. See lg.setup_logging for full documentation."""
    return lg.setup_logging(*args, **kwargs)

__version__ = '0.1.0'