#!/usr/bin/env python3
"""
Run the plugin test suite inside a NetBox installation.

Usage (from NetBox's ``netbox/`` directory, with the plugin installed and enabled):

    DJANGO_SETTINGS_MODULE=netbox.settings PYTHONPATH=. python /path/to/tools/run_tests.py /path/to/tests

Uses Django's test runner, so a throwaway test database is created and destroyed: tests
never touch the configured NetBox database.
"""

import sys
from pathlib import Path

import django
from django.conf import settings
from django.test.utils import get_runner

if __name__ == "__main__":
    django.setup()
    tests = Path(sys.argv[1] if len(sys.argv) > 1 else Path(__file__).parent.parent / "tests").resolve()
    sys.path.insert(0, str(tests.parent))
    runner = get_runner(settings)(verbosity=2, interactive=False, keepdb="--keepdb" in sys.argv)
    failures = runner.run_tests([tests.name], top_level=str(tests.parent))
    sys.exit(bool(failures))
