#!/usr/bin/env python
"""Debug script to test URL injection."""

import os
import sys
import django
import traceback

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'testsite.settings')
sys.path.insert(0, '/Users/hp/proj/justlog/test_django_project')

# Import before setup to see what happens
from django.conf import settings

print(f'Before django.setup()')
print(f'ROOT_URLCONF: {settings.ROOT_URLCONF}')

# Now setup Django
django.setup()

print(f'\nAfter django.setup()')

# Try to manually inject URLs
try:
    from django.urls import path, clear_url_caches
    from justlog.django_views import log_viewer_view

    # Get the root URLconf
    urlconf = __import__(settings.ROOT_URLCONF, {}, {}, [''])

    print(f'\nCurrent urlpatterns:')
    if hasattr(urlconf, 'urlpatterns'):
        for pattern in urlconf.urlpatterns:
            print(f'  - {pattern.pattern}')
    else:
        print('  No urlpatterns attribute!')

    # Try to inject
    print(f'\nAttempting to inject /lg/ URL...')
    if hasattr(urlconf, 'urlpatterns'):
        existing_patterns = [str(p.pattern) for p in urlconf.urlpatterns]
        if 'lg/' not in existing_patterns and 'lg' not in existing_patterns:
            new_pattern = path('lg/', log_viewer_view, name='justlog_viewer')
            urlconf.urlpatterns.append(new_pattern)
            clear_url_caches()
            print('  ✓ Successfully injected!')
        else:
            print('  - Already exists')

    print(f'\nURLpatterns after injection:')
    if hasattr(urlconf, 'urlpatterns'):
        for pattern in urlconf.urlpatterns:
            print(f'  - {pattern.pattern}')

except Exception as e:
    print(f'\nERROR: {e}')
    traceback.print_exc()
