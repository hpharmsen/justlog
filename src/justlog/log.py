# log.py
import json
import logging
from datetime import datetime, timedelta
from logging.handlers import RotatingFileHandler
import sys
from pathlib import Path
from types import TracebackType
from typing import Optional, Type


class StructuredFormatter(logging.Formatter):
    """Custom formatter that appends extra fields as formatted JSON."""

    # Standard LogRecord attributes that should not be treated as 'extra'
    RESERVED_ATTRS = {
        'name', 'msg', 'args', 'created', 'filename', 'funcName', 'levelname',
        'levelno', 'lineno', 'module', 'msecs', 'message', 'pathname', 'process',
        'processName', 'relativeCreated', 'thread', 'threadName', 'exc_info',
        'exc_text', 'stack_info', 'taskName', 'asctime',
    }

    def format(self, record: logging.LogRecord) -> str:
        """Format log record with extra fields appended as JSON."""
        # Get the base formatted message
        base_message = super().format(record)

        # Extract extra fields (anything not in RESERVED_ATTRS)
        extra_fields = {
            key: value
            for key, value in record.__dict__.items()
            if key not in self.RESERVED_ATTRS and not key.startswith('_')
        }

        # If there are extra fields, append them as formatted JSON
        if extra_fields:
            json_extra = json.dumps(extra_fields, indent=4, default=str)
            return f'{base_message}\n{json_extra}'

        return base_message


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

    # ---- Public API -----------------------------------------------------

    def setup_logging(
        self,
        log_file_path: str | Path,  # Obligatory, where the log file is stored
        level: int = logging.INFO,  # Level from which logging to the file occurs
        to_stderr_level: int = logging.NOTSET,  # Level from which logging to stderr occurs
        max_bytes: int = 1_000_000, # Max size of a log file, above this size it is rotated with a .1 suffix
        backup_count: int = 5,      # Max number of old log files to keep .1 .2 .3 etc.
        backup_days: int = 0,       # Max number of days of old log files to keep. 0 is infinite
        logger_name: str = "app",
        datefmt: str = "%Y-%m-%d %H:%M:%S",
        fmt: str = "%(asctime)s %(levelname)s %(message)s",
    ) -> logging.Logger:
        """
        Configure logging and bind the underlying logger to this proxy.
        Safe to call more than once; it replaces previous handlers.
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

        formatter = StructuredFormatter(fmt=fmt, datefmt=datefmt)

        file_handler = RotatingFileHandler(log_path, maxBytes=max_bytes, backupCount=backup_count)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

        if to_stderr_level:
            stream_handler = logging.StreamHandler(sys.stderr)
            stream_handler.setLevel(to_stderr_level)
            stream_handler.setFormatter(formatter)
            logger.addHandler(stream_handler)

        self._logger = logger

        # Make sure uncaught exceptions are logged
        sys.excepthook = self._handle_uncaught_exception

        self.backup_days = backup_days
        if self.backup_days:
            self.cleanup_old_logs()
        return logger

    # ---- Logger-like delegation ----------------------------------------

    def __getattr__(self, name: str):
        """
        Delegate attribute access (info, debug, warning, error, critical, etc.)
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

        # Minimal bootstrap to avoid AttributeError before setup
        logger = logging.getLogger("app")
        logger.setLevel(logging.WARNING)
        logger.propagate = False
        if not logger.handlers:
            formatter = StructuredFormatter(
                fmt="%(asctime)s %(levelname)s %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
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
        cutoff = datetime.now() - timedelta(days=self.backup_days)
        lines_to_keep = []

        with open(self.log_file_path, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    # Verwacht dat je log begint met iets als: "2025-10-05 15:23:45 ..."
                    timestamp_str = line.split(" ")[0] + " " + line.split(" ")[1]
                    timestamp = datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S")
                    if timestamp >= cutoff:
                        lines_to_keep.append(line)
                except Exception:
                    # Als een regel geen timestamp bevat, behouden we hem
                    lines_to_keep.append(line)

        with open(self.log_file_path, "w", encoding="utf-8") as f:
            f.writelines(lines_to_keep)


# Importable singleton
lg = _LoggerProxy()
