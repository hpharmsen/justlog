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

## License

MIT License - see LICENSE file for details.

## Contributing

Issues and pull requests are welcome at the project repository.