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
| `backup_days` | `int` | `30` | Days to keep logs, file and database (0 = infinite) |
| `logger_name` | `str` | `"app"` | Internal logger name |
| `use_database` | `bool` | `False` | Enable database logging (requires Django) |
| `db_level` | `int` | `logging.INFO` | Minimum level for database logging |

## Features

- **Singleton pattern**: Use `lg` anywhere after initial setup
- **File rotation**: Automatic rotation when size limit is reached
- **Dual output**: Log to file and stderr with separate levels
- **Database storage**: Optional database logging via Django ORM
- **Auto-cleanup**: Time-based cleanup of old entries
- **Exception handling**: Uncaught exceptions are automatically logged
- **Multi-argument support**: Pass any printable arguments
- **Structured logging**: Preserves extra arguments as JSON in database

## Django Integration

JustLog integrates seamlessly with Django to provide a web-based log viewer at `/lg/`.

### Setup

**Step 1:** Add `justlog.apps.JustLogConfig` to your `INSTALLED_APPS` in `settings.py`:

```python
# settings.py
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    # ... other apps ...
    'justlog.apps.JustLogConfig',  # Add this
]
```

**Step 2:** Add `justlog.middleware.JustLogMiddleware` to your `MIDDLEWARE` in `settings.py`:

```python
# settings.py
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    # ... other middleware ...
    'justlog.middleware.JustLogMiddleware',  # Add this
]
```

**Step 3:** Configure logging in `settings.py`:

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

**Step 4 (Optional):** Enable database logging and run migrations:

```python
# settings.py - Update setup_logging call to enable database logging
setup_logging(
    log_file_path=BASE_DIR / 'logs' / 'django.log',
    level=logging.DEBUG,
    to_stderr_level=logging.ERROR,
    use_database=True,      # Enable database logging
    db_level=logging.INFO   # Store INFO and above in database
)
```

Then run migrations to create the database table:

```bash
python manage.py migrate
```

That's it! The `/lg/` endpoint will be available via the middleware.

### Using JustLog in Your Django Code

```python
# views.py
from justlog import lg

def my_view(request):
    lg.info('Processing request', path=request.path, user=request.user.username)
    # ... your code ...
    return response
```

### Viewing Logs

Visit `http://localhost:8000/lg/` in your browser to view logs with:
- Real-time log viewing with syntax highlighting
- Filtering by log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
- Pagination for large log files
- Dark mode UI optimized for readability
- **Source selector**: Toggle between file-based and database logs (when `use_database=True`)

The `/lg/` endpoint is handled by middleware - no manual URL configuration needed.

### Database Logging Benefits

When `use_database=True`, logs are stored in both the file and database:

- **Queryable logs**: Use Django ORM to query logs programmatically
- **Structured data**: Extra arguments preserved as JSON fields
- **Better filtering**: Fast indexed queries by timestamp and level
- **Any database**: Works with PostgreSQL, MySQL, SQLite, etc.
- **Dual storage**: File logs remain available for backup/debugging

```python
# Query logs programmatically
from justlog.models import LogEntry

# Get recent errors
recent_errors = LogEntry.objects.filter(level__gte=40).order_by('-timestamp')[:10]

# Search by message content
payment_logs = LogEntry.objects.filter(message__icontains='payment')

# Get logs from specific time range
from datetime import datetime, timedelta
yesterday = datetime.now() - timedelta(days=1)
recent_logs = LogEntry.objects.filter(timestamp__gte=yesterday)
```

## License

MIT License