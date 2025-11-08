#!/usr/bin/env python
"""Check if justlog integration is working."""

import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'testsite.settings')
sys.path.insert(0, '/Users/hp/proj/justlog/test_django_project')
django.setup()

from django.conf import settings
from django.urls import get_resolver

print('=== Checking Django Integration ===')
print(f'\nINSTALLED_APPS:')
for app in settings.INSTALLED_APPS:
    print(f'  - {app}')

print(f'\nROOT_URLCONF: {settings.ROOT_URLCONF}')

# Check URL patterns
urlconf = __import__(settings.ROOT_URLCONF, {}, {}, [''])
print(f'\nURL patterns:')
if hasattr(urlconf, 'urlpatterns'):
    for pattern in urlconf.urlpatterns:
        print(f'  - {pattern.pattern}')
else:
    print('  No urlpatterns found!')

# Check if justlog was properly setup
from justlog import lg
print(f'\nJustlog log_file_path: {lg.log_file_path}')
