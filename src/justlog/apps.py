# apps.py
from django.apps import AppConfig


class JustLogConfig(AppConfig):
    """Django app configuration for JustLog."""

    name = 'justlog'
    verbose_name = 'JustLog'
    default_auto_field = 'django.db.models.BigAutoField'
