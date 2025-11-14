# middleware.py
"""
Django middleware for JustLog log viewer.

This middleware intercepts requests to /lg/ and serves the log viewer
without requiring URL configuration. This approach avoids Django's
populate() re-entrancy issues and follows Django best practices.

To use:
    Add 'justlog.middleware.JustLogMiddleware' to your MIDDLEWARE setting:

    MIDDLEWARE = [
        'django.middleware.security.SecurityMiddleware',
        ...
        'justlog.middleware.JustLogMiddleware',  # Add this line
    ]
"""


class JustLogMiddleware:
    """Middleware to handle /lg/ requests for the log viewer."""

    def __init__(self, get_response):
        """Initialize middleware with the next middleware/view in the chain."""
        self.get_response = get_response

    def __call__(self, request):
        """Process the request, intercepting /lg/ paths for the log viewer."""
        # Check if this is a request to the log viewer
        if request.path == '/lg' or request.path == '/lg/':
            from .django_views import log_viewer_view
            return log_viewer_view(request)

        # Pass through to next middleware/view
        response = self.get_response(request)
        return response
