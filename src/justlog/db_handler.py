# db_handler.py
import logging
from datetime import datetime
from zoneinfo import ZoneInfo


class DatabaseHandler(logging.Handler):
    """Custom logging handler that writes logs to Django database."""

    def __init__(self):
        super().__init__()
        self._model = None

    def _get_model(self):
        """Lazy load the Django model to avoid circular imports."""
        if self._model is None:
            from .models import LogEntry
            self._model = LogEntry
        return self._model

    def emit(self, record: logging.LogRecord):
        """Write a log record to the database."""
        try:
            LogEntry = self._get_model()

            # Convert timestamp to CET timezone (naive datetime for USE_TZ=False)
            utc_dt = datetime.fromtimestamp(record.created, tz=ZoneInfo('UTC'))
            cet_dt = utc_dt.astimezone(ZoneInfo('Europe/Amsterdam'))
            timestamp = cet_dt.replace(tzinfo=None)  # Store as naive datetime

            # Extract extra args and kwargs if present
            extra_args = getattr(record, '_extra_args', None)
            extra_kwargs = getattr(record, '_extra_kwargs', None)

            # Create the log entry
            LogEntry.objects.create(
                timestamp=timestamp,
                level=record.levelno,
                message=record.getMessage(),
                extra_args=extra_args if extra_args else None,
                extra_kwargs=extra_kwargs if extra_kwargs else None,
            )

        except Exception:
            # Don't let logging errors crash the application
            self.handleError(record)
