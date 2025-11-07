# JustLog

A simple, flexible logging utility for Python with automatic file rotation and multi-argument support.

## Installation

```bash
pip install justlog
```

## Quick Start

```python
from justlog import lg, setup_logging

# Configure once at startup
setup_logging("logs/app.log")

# Use anywhere with any number of arguments
lg.info("Application started")
lg.info("User login", "user123", "192.168.1.1")
lg.error("Payment failed", amount=50.0, currency="USD")
```

## Usage

### Basic Logging

```python
from justlog import lg, setup_logging

setup_logging("logs/app.log")

lg.debug("Debug message")
lg.info("Info message")
lg.error("Error message")
```

### Multi-Argument Logging

Pass multiple arguments to log additional context:

```python
# Positional arguments appear below the main message
lg.info("Processing order", "order_123", "customer_456")

# Output:
# 2025-10-16 14:30:15 INFO Processing order
#   order_123
#   customer_456

# Named arguments show with their names
lg.error("Database error", table="users", operation="insert")

# Output:
# 2025-10-16 14:30:15 ERROR Database error
#   table: users
#   operation: insert

# Mix both types
lg.info("Payment received", "transaction_789", amount=100.50, currency="USD")

# Output:
# 2025-10-16 14:30:15 INFO Payment received
#   transaction_789
#   amount: 100.50
#   currency: USD
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
    backup_days=30,               # Delete entries older than 30 days
    logger_name="myapp"
)
```

## Configuration Options

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `log_file_path` | `str \| Path` | Required | Path to the log file |
| `level` | `int` | `logging.INFO` | Minimum level for file logging |
| `to_stderr_level` | `int` | `logging.NOTSET` | Minimum level for stderr (0 = disabled) |
| `max_bytes` | `int` | `1_000_000` | Max file size before rotation |
| `backup_count` | `int` | `5` | Number of backup files to keep |
| `backup_days` | `int` | `0` | Days to keep (0 = infinite) |
| `logger_name` | `str` | `"app"` | Internal logger name |

## Features

- **Singleton pattern**: Use `lg` anywhere after initial setup
- **File rotation**: Automatic rotation when size limit is reached
- **Dual output**: Log to file and stderr with separate levels
- **Auto-cleanup**: Time-based cleanup of old entries
- **Exception handling**: Uncaught exceptions are automatically logged
- **Multi-argument support**: Pass any printable arguments

## Django Integration

JustLog automatically integrates with Django when you call `setup_logging()`. The `/lg/` endpoint for viewing logs is automatically configured.

### Basic Setup

Simply call `setup_logging()` in your `settings.py` or in an app's `AppConfig.ready()` method:

```python
# settings.py
import logging
from pathlib import Path
from justlog import setup_logging

BASE_DIR = Path(__file__).resolve().parent.parent

setup_logging(
    log_file_path=BASE_DIR / 'logs' / 'django.log',
    level=logging.DEBUG,
    to_stderr_level=logging.ERROR
)
```

Or in an AppConfig for better organization:

```python
# myapp/apps.py
import logging
from pathlib import Path
from django.apps import AppConfig

class MyAppConfig(AppConfig):
    name = 'myapp'

    def ready(self):
        from justlog import setup_logging

        log_dir = Path(__file__).parent.parent / 'logs'
        log_dir.mkdir(exist_ok=True)

        setup_logging(
            log_file_path=str(log_dir / 'myapp.log'),
            level=logging.DEBUG,
            to_stderr_level=logging.ERROR
        )
```

### Viewing Logs

After setup, visit `http://localhost:8000/lg/` in your browser to view logs with:
- Real-time log viewing with syntax highlighting
- Filtering by log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
- Pagination for large log files
- Dark mode UI optimized for readability

The `/lg/` endpoint is automatically injected into your URLconf - no manual URL configuration needed.

## License

MIT License