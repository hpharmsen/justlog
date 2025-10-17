# JustLog

A simple, flexible logging utility for Python applications that provides an easy-to-use singleton logger with file rotation, configurable output levels, and automatic log cleanup.

## Features

- **Singleton pattern**: Import and use the same logger instance across your entire application
- **File rotation**: Automatic log file rotation based on size with configurable backup count
- **Dual output**: Log to both file and stderr with separate log levels
- **Auto-cleanup**: Optional time-based cleanup of old log entries
- **Exception handling**: Automatically logs uncaught exceptions
- **Zero configuration**: Works out of the box with sensible defaults

## Installation

```bash
pip install justlog
```

## Quick Start

```python
from justlog import lg, setup_logging

# Configure logging once at application startup
setup_logging("logs/app.log")

# Use throughout your application
lg.info("Application started")
lg.warning("This is a warning")
lg.error("Something went wrong")
```

## Usage

### Basic Setup

```python
from justlog import setup_logging, lg

# Minimal setup - creates logs/app.log with INFO level
setup_logging("logs/app.log")

# Now use lg anywhere in your application
lg.debug("Debug message")  # Won't be logged (below INFO level)
lg.info("Info message")    # Will be logged
lg.error("Error message")  # Will be logged
```

### Advanced Configuration

```python
import logging
from justlog import setup_logging, lg

setup_logging(
    log_file_path="logs/myapp.log",
    level=logging.DEBUG,           # File logging level
    to_stderr_level=logging.ERROR, # Also log ERROR+ to stderr
    max_bytes=5_000_000,          # 5MB file size limit
    backup_count=10,              # Keep 10 backup files
    backup_days=30,               # Delete log entries older than 30 days
    logger_name="myapp",
    datefmt="%Y-%m-%d %H:%M:%S",
    fmt="%(asctime)s [%(levelname)s] %(message)s"
)

lg.debug("This will be in the file")
lg.error("This will be in both file and stderr")
```

### Structured Logging with Extra Fields

Pass additional data using the `extra` parameter. Extra fields are formatted as JSON:

```python
lg.info("User logged in", extra={'user_id': 123, 'ip': '192.168.1.1'})
lg.error("Payment failed", extra={'amount': 50.0, 'currency': 'USD'})
```

Output:
```
2025-10-16 22:30:15 INFO User logged in
{
    "user_id": 123,
    "ip": "192.168.1.1"
}
```

### Import Patterns

```python
# Pattern 1: Import the configured logger
from justlog import lg
lg.info("Message")

# Pattern 2: Import setup function and logger
from justlog import setup_logging, lg
setup_logging("app.log")
lg.info("Message")

# Pattern 3: Use the logger like any other logger
import justlog
justlog.setup_logging("app.log")
justlog.lg.info("Message")
```

## Configuration Options

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `log_file_path` | `str \| Path` | Required | Path to the log file |
| `level` | `int` | `logging.INFO` | Minimum level for file logging |
| `to_stderr_level` | `int` | `logging.NOTSET` | Minimum level for stderr output (0 = disabled) |
| `max_bytes` | `int` | `1_000_000` | Max file size before rotation |
| `backup_count` | `int` | `5` | Number of backup files to keep |
| `backup_days` | `int` | `0` | Days of log history to keep (0 = infinite) |
| `logger_name` | `str` | `"app"` | Internal logger name |
| `datefmt` | `str` | `"%Y-%m-%d %H:%M:%S"` | Date format string |
| `fmt` | `str` | `"%(asctime)s %(levelname)s %(message)s"` | Log message format |

## File Structure

After rotation, your logs directory will look like:
```
logs/
├── app.log      # Current log file
├── app.log.1    # Most recent backup
├── app.log.2    # Older backup
└── app.log.3    # Oldest backup
```

## Exception Handling

JustLog automatically captures uncaught exceptions:

```python
from justlog import setup_logging, lg

setup_logging("logs/app.log")

# This exception will be logged before the program terminates
raise ValueError("Something went wrong!")
```

# Setting Up Justlog in Django Projects

This guide explains how to properly integrate justlog with Django to ensure logging is configured after Django settings are fully loaded.

## Why Special Setup is Needed

Django has a specific initialization order. If you call `setup_logging()` too early (e.g., in a module's `__init__.py`), Django's settings won't be fully configured yet, preventing justlog from properly integrating with Django.

The solution is to use Django's `AppConfig.ready()` method, which runs **after** Django is fully initialized.

## Setup Instructions

### 1. Create or Update Your App's `apps.py`

In your Django app directory (e.g., `myapp/apps.py`), create or update the AppConfig class:

```python
import logging
from pathlib import Path
from django.apps import AppConfig


class MyAppConfig(AppConfig):
    """App configuration for myapp."""
    default_auto_field = 'django.db.models.AutoField'
    name = 'myapp'  # Replace with your app name

    def ready(self):
        """Initialize logging after Django is fully configured."""
        from justlog import setup_logging

        # Configure justlog
        log_dir = Path(__file__).parent.parent / 'logs'
        log_dir.mkdir(exist_ok=True)

        setup_logging(
            log_file_path=str(log_dir / 'myapp.log'),
            level=logging.DEBUG,
            to_stderr_level=logging.ERROR,
            max_bytes=5_000_000,
            backup_count=10,
            backup_days=30,
            logger_name='myapp',
            datefmt='%Y-%m-%d %H:%M:%S',
            fmt='%(asctime)s [%(levelname)s] %(message)s'
        )
```

### 2. Update INSTALLED_APPS in settings.py

Modify your `settings.py` to use the AppConfig instead of just the app name:

```python
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    # ... other Django apps ...
    'myapp.apps.MyAppConfig',  # Use AppConfig instead of just 'myapp'
    # ... other apps ...
]
```

### 3. Use Justlog Throughout Your Project

Now you can use justlog anywhere in your Django project:

```python
from justlog import lg

def my_view(request):
    lg.info('Processing request', details={'user': request.user.username})
    # ... your code ...
    return response
```

## Django Integration Features

When properly configured, justlog automatically:
- Adds a `/lg/` URL endpoint to view your logs in a web browser
- Integrates seamlessly with Django's settings system
- Works with Django's development and production environments

## Troubleshooting

**Problem**: You see 'NO DJANGO SETTINGS' in console output

**Solution**: Make sure you're calling `setup_logging()` in the `ready()` method of an AppConfig, not in a module's `__init__.py` or at the top level of a file.

**Problem**: Logs aren't being created

**Solution**: Ensure the log directory exists and has write permissions. The `ready()` method above creates the directory automatically with `log_dir.mkdir(exist_ok=True)`.

## Example Project Structure

```
myproject/
├── manage.py
├── myproject/
│   ├── __init__.py
│   ├── settings.py
│   └── urls.py
├── myapp/
│   ├── __init__.py
│   ├── apps.py          # AppConfig with setup_logging() in ready()
│   ├── models.py
│   └── views.py
└── logs/
    └── myapp.log        # Created automatically
```

## Notes

- The `ready()` method may be called multiple times in some scenarios (e.g., when running tests). Justlog handles this gracefully.
- Make sure to add `logs/` to your `.gitignore` to avoid committing log files to version control.
- The log viewer at `/lg/` is automatically registered when using AppConfig setup.


## License

MIT License - see LICENSE file for details.

## Contributing

Issues and pull requests are welcome at the project repository.