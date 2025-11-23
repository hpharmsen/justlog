# models.py
from django.db import models
import json


class LogEntry(models.Model):
    """Model for storing log entries in the database."""

    LEVEL_CHOICES = [
        (10, 'DEBUG'),
        (20, 'INFO'),
        (30, 'WARNING'),
        (40, 'ERROR'),
        (50, 'CRITICAL'),
    ]

    timestamp = models.DateTimeField(db_index=True)
    level = models.IntegerField(choices=LEVEL_CHOICES, db_index=True)
    message = models.TextField()
    extra_args = models.JSONField(null=True, blank=True)
    extra_kwargs = models.JSONField(null=True, blank=True)

    class Meta:
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['-timestamp', 'level']),
        ]
        verbose_name = 'Log Entry'
        verbose_name_plural = 'Log Entries'

    def __str__(self):
        return f'{self.timestamp} {self.get_level_display()} {self.message[:50]}'

    def get_level_name(self):
        """Return the string name of the log level."""
        return self.get_level_display()

    def to_dict(self):
        """Convert log entry to dictionary."""
        return {
            'timestamp': self.timestamp.isoformat(),
            'level': self.level,
            'level_name': self.get_level_display(),
            'message': self.message,
            'extra_args': self.extra_args,
            'extra_kwargs': self.extra_kwargs,
        }
