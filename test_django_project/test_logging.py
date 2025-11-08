#!/usr/bin/env python
"""Test script to generate some log messages."""

import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'testsite.settings')
sys.path.insert(0, '/Users/hp/proj/justlog/test_django_project')
django.setup()

# Now we can import lg
from justlog import lg

# Generate some test log messages
lg.info('Test info message')
lg.warning('Test warning message')
lg.error('Test error message')
lg.debug('Test debug message - should not appear with default settings')
lg.info('Another info message with details', extra_data={'user': 'test', 'action': 'login'})

print('Log messages generated successfully!')
