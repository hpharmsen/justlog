# log.py
import json
import logging
from datetime import datetime, timedelta
from logging.handlers import RotatingFileHandler
import sys
import traceback
from pathlib import Path
from types import TracebackType
from typing import Optional, Type, Any
from zoneinfo import ZoneInfo

# Default format constants
DEFAULT_DATEFMT = '%Y-%m-%d %H:%M:%S'
DEFAULT_FMT = '%(asctime)s %(levelname)s %(message)s'


class StructuredFormatter(logging.Formatter):
    """Custom formatter that handles multiple arguments and keyword arguments."""

    # Standard LogRecord attributes that should not be treated as 'extra'
    RESERVED_ATTRS = {
        'name', 'msg', 'args', 'created', 'filename', 'funcName', 'levelname',
        'levelno', 'lineno', 'module', 'msecs', 'message', 'pathname', 'process',
        'processName', 'relativeCreated', 'thread', 'threadName', 'exc_info',
        'exc_text', 'stack_info', 'taskName', 'asctime', '_extra_args', '_extra_kwargs',
    }

    def formatTime(self, record: logging.LogRecord, datefmt: Optional[str] = None) -> str:
        """Convert timestamp to CET timezone."""
        # Convert the record's timestamp (in UTC) to CET
        ct = datetime.fromtimestamp(record.created, tz=ZoneInfo('Europe/Amsterdam'))
        if datefmt:
            return ct.strftime(datefmt)
        return ct.strftime(DEFAULT_DATEFMT)

    def format(self, record: logging.LogRecord) -> str:
        """Format log record with additional arguments shown below the main message."""
        # Get the base formatted message (timestamp + level + first message)
        base_message = super().format(record)

        lines = [base_message]

        # Handle extra positional arguments (after the first message)
        if hasattr(record, '_extra_args') and record._extra_args:
            for arg in record._extra_args:
                formatted = self._format_value(arg)
                lines.append(formatted)

        # Handle keyword arguments with their names
        if hasattr(record, '_extra_kwargs') and record._extra_kwargs:
            for key, value in record._extra_kwargs.items():
                # Check if value is a JSON dict/list
                is_json = ((value.startswith('{') and value.endswith('}')) or
                          (value.startswith('[') and value.endswith(']')))

                if is_json:
                    # Multi-line formatting for dicts/lists
                    formatted = self._format_value(value, indent=2)
                    lines.append(f'  {key}:')
                    lines.append(formatted)
                else:
                    # Single-line formatting for simple values
                    lines.append(f'  {key}: {value}')

        return '\n'.join(lines)

    def _format_value(self, value: str, indent: int = 2) -> str:
        """Format a value, pretty-printing dicts and lists as JSON."""
        # Try to parse as JSON and pretty-print
        try:
            if (value.startswith('{') and value.endswith('}')) or \
               (value.startswith('[') and value.endswith(']')):
                # Parse JSON and pretty-print
                parsed = json.loads(value)
                if isinstance(parsed, (dict, list)):
                    # Pretty-print with indentation
                    json_str = json.dumps(parsed, indent=2, default=str)
                    # Add indentation to each line
                    indented = '\n'.join(' ' * indent + line for line in json_str.split('\n'))
                    return indented
        except (json.JSONDecodeError, ValueError):
            pass

        # Default: just indent the string
        return ' ' * indent + value


class _LoggerProxy:
    """
    Class-based, importable singleton-like logger facade.

    Usage:
        from log import lg

        lg.setup_logging("logs/app.log")      # once at startup
        lg.info("message goes here")          # thereafter, just use lg like a logger
    """

    def __init__(self) -> None:
        self._logger: Optional[logging.Logger] = None
        self.log_file_path: Optional[Path] = None
        self.use_database: bool = False

    # ---- Public API -----------------------------------------------------

    def setup_logging(
        self,
        log_file_path: str | Path,  # Obligatory, where the log file is stored
        level: int = logging.INFO,  # Level from which logging to the file occurs
        to_stderr_level: int = logging.NOTSET,  # Level from which logging to stderr occurs
        max_bytes: int = 1_000_000, # Max size of a log file, above this size it is rotated with a .1 suffix
        backup_count: int = 5,      # Max number of old log files to keep .1 .2 .3 etc.
        backup_days: int = 30,      # Max number of days to keep logs (file and database). 0 is infinite
        logger_name: str = "app",
        use_database: bool = False, # Enable database logging (requires Django)
        db_level: int = logging.INFO,  # Minimum level for database logging
    ) -> logging.Logger:
        """
        Configure logging and bind the underlying logger to this proxy.
        Safe to call more than once; it replaces previous handlers.

        Args:
            log_file_path: Path to the log file (required)
            level: Minimum log level for file logging (default: logging.INFO)
            to_stderr_level: Minimum level for stderr output (default: logging.NOTSET, 0 = disabled)
            max_bytes: Maximum file size before rotation (default: 1,000,000 bytes)
            backup_count: Number of rotated backup files to keep (default: 5)
            backup_days: Delete log entries older than this many days (default: 30, 0 = infinite)
            logger_name: Name of the internal logger instance (default: 'app')
            use_database: Enable database logging via Django ORM (default: False)
            db_level: Minimum log level for database storage (default: logging.INFO)

        Returns:
            logging.Logger: The configured logger instance

        Note:
            Database logging requires Django and that you've run migrations after
            adding 'justlog.apps.JustLogConfig' to INSTALLED_APPS.
        """
        # Ensure file/dirs exist
        log_path = Path(log_file_path)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_path.touch(exist_ok=True)

        # Store for later access (e.g., Django view)
        self.log_file_path = log_path

        logger = logging.getLogger(logger_name)
        logger.setLevel(level)
        logger.propagate = False  # do not duplicate to root

        # Replace handlers idempotently
        logger.handlers.clear()

        formatter = StructuredFormatter(fmt=DEFAULT_FMT, datefmt=DEFAULT_DATEFMT)

        file_handler = RotatingFileHandler(log_path, maxBytes=max_bytes, backupCount=backup_count)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

        if to_stderr_level:
            stream_handler = logging.StreamHandler(sys.stderr)
            stream_handler.setLevel(to_stderr_level)
            stream_handler.setFormatter(formatter)
            logger.addHandler(stream_handler)

        # Add database handler if requested
        if use_database:
            try:
                from .db_handler import DatabaseHandler
                db_handler = DatabaseHandler()
                db_handler.setLevel(db_level)
                logger.addHandler(db_handler)
                self.use_database = True
            except ImportError:
                logger.warning('Database logging requested but Django is not available')

        self._logger = logger

        # Make sure uncaught exceptions are logged
        sys.excepthook = self._handle_uncaught_exception

        self.backup_days = backup_days
        if self.backup_days:
            self.cleanup_old_logs()
            if self.use_database:
                self._cleanup_old_db_logs()

        try:
            from .django_integration import setup_django

            setup_django()
        except ImportError:
            pass  # django_integration module not available

        return logger

    # ---- Logger-like delegation ----------------------------------------

    def _log(self, log_level: int, *args: Any, **kwargs: Any) -> None:
        """Internal method to log with multiple arguments."""
        logger = self._ensure_logger()
        if not args:
            return

        # First argument is the main message
        message = str(args[0])

        # Create the log record
        record = logger.makeRecord(
            logger.name,
            log_level,
            '(unknown file)',
            0,
            message,
            (),
            None,
        )

        # Attach extra args and kwargs to the record, preserving dicts/lists
        if len(args) > 1:
            record._extra_args = []
            for arg in args[1:]:
                if isinstance(arg, (dict, list)):
                    record._extra_args.append(json.dumps(arg, default=str))
                else:
                    record._extra_args.append(str(arg))
        if kwargs:
            record._extra_kwargs = {}
            for k, v in kwargs.items():
                if k == 'exc_info' and v:
                    record._extra_kwargs[k] = traceback.format_exc()
                elif isinstance(v, (dict, list)):
                    record._extra_kwargs[k] = json.dumps(v, default=str)
                else:
                    record._extra_kwargs[k] = str(v)

        logger.handle(record)

    def debug(self, *args: Any, **kwargs: Any) -> None:
        """Log a debug message with optional additional arguments."""
        self._log(logging.DEBUG, *args, **kwargs)

    def info(self, *args: Any, **kwargs: Any) -> None:
        """Log an info message with optional additional arguments."""
        self._log(logging.INFO, *args, **kwargs)

    def warning(self, *args: Any, **kwargs: Any) -> None:
        """Log a warning message with optional additional arguments."""
        self._log(logging.WARNING, *args, **kwargs)

    def error(self, *args: Any, **kwargs: Any) -> None:
        """Log an error message with optional additional arguments."""
        self._log(logging.ERROR, *args, **kwargs)

    def critical(self, *args: Any, **kwargs: Any) -> None:
        """Log a critical message with optional additional arguments."""
        self._log(logging.CRITICAL, *args, **kwargs)

    def __getattr__(self, name: str):
        """
        Delegate attribute access for other logger methods (like exception, etc.)
        to the underlying logging.Logger. If not configured yet, bootstrap a
        minimal stderr logger so calls won't crash.
        """
        logger = self._ensure_logger()
        return getattr(logger, name)

    # ---- Internals ------------------------------------------------------

    def _ensure_logger(self) -> logging.Logger:
        """
        Return the configured logger; if setup_logging hasn't been called yet,
        bootstrap a minimal stderr-only logger at WARNING level.
        """
        if self._logger is not None:
            return self._logger

        # Check if there's already a configured 'app' logger (e.g., from Django app ready())
        # This handles the case where setup_logging was called but lg._logger was reset
        # (e.g., in multiprocessing child processes after Django re-initializes)
        existing_logger = logging.getLogger("app")
        if existing_logger.handlers:
            # Logger was already configured, reuse it
            self._logger = existing_logger
            return self._logger

        # Minimal bootstrap to avoid AttributeError before setup
        logger = existing_logger
        logger.setLevel(logging.WARNING)
        logger.propagate = False
        formatter = StructuredFormatter(fmt=DEFAULT_FMT, datefmt=DEFAULT_DATEFMT)
        sh = logging.StreamHandler(sys.stderr)
        sh.setFormatter(formatter)
        logger.addHandler(sh)
        self._logger = logger
        return logger

    def _handle_uncaught_exception(
        self,
        exc_type: Type[BaseException],
        exc_value: BaseException,
        exc_traceback: Optional[TracebackType],
    ) -> None:
        self._ensure_logger().critical(
            "uncaught exception, application will terminate.",
            exc_info=(exc_type, exc_value, exc_traceback),
        )

    def cleanup_old_logs(self):
        """Remove old entries from the log file."""
        cutoff = datetime.now() - timedelta(days=self.backup_days)
        lines_to_keep = []

        with open(self.log_file_path, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    timestamp_str = line.split(" ")[0] + " " + line.split(" ")[1]
                    timestamp = datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S")
                    if timestamp >= cutoff:
                        lines_to_keep.append(line)
                except Exception:
                    lines_to_keep.append(line)

        with open(self.log_file_path, "w", encoding="utf-8") as f:
            f.writelines(lines_to_keep)

    def _cleanup_old_db_logs(self):
        """Remove old entries from the database."""
        try:
            from .models import LogEntry
            cutoff = datetime.now() - timedelta(days=self.backup_days)
            deleted, _ = LogEntry.objects.filter(timestamp__lt=cutoff).delete()
            if deleted:
                self.info(f'Cleaned up {deleted} old log entries from database')
        except Exception:
            pass  # Don't crash if cleanup fails


# Importable singleton
lg = _LoggerProxy()
