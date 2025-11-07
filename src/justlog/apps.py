# apps.py
from django.apps import AppConfig


class JustLogConfig(AppConfig):
    """Django app configuration for JustLog."""

    name = 'justlog'
    verbose_name = 'JustLog'
    default_auto_field = 'django.db.models.BigAutoField'

    def ready(self):
        """
        Called when Django app is ready and URLconf is loaded.
        This is the proper place to inject URLs into the Django project.
        """
        from .django_integration import inject_urls
        inject_urls()
