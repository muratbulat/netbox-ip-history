#!/usr/bin/env python3
"""
Test runner used only by .github/workflows/netbox-matrix.yml, where the
plugin's tests run against a REAL, installed Django/NetBox — not the
Django-less fallback path the local suite normally exercises.

Plain `python -m unittest discover` never calls django.setup(), so importing
any real Django model (e.g. via netbox_ip_history.models -> netbox.models ->
core.models.ContentType) fails with AppRegistryNotReady even when
DJANGO_SETTINGS_MODULE is set correctly — settings become readable, but the
app registry is never populated. manage.py-based commands don't hit this
because ManagementUtility.execute() calls django.setup() itself; a bare
unittest invocation has no equivalent. This is that equivalent: setup() then
discover-and-run, so this job actually exercises the real-Django code path
it exists to validate, wrapped in `coverage run` from the workflow.

Not shipped: excluded from the built package (see pyproject.toml
`tool.setuptools.packages.find` excludes `tools*`).
"""
from __future__ import annotations

import sys
import unittest

import django

django.setup()

if __name__ == "__main__":
    tests_dir = sys.argv[1] if len(sys.argv) > 1 else "../../tests"
    suite = unittest.TestLoader().discover(tests_dir)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)
