# Development tasks. Tests need a NetBox checkout: set NETBOX_ROOT to its netbox/ directory
# (the one containing manage.py), with this plugin installed and enabled.

netbox_root := env_var_or_default("NETBOX_ROOT", "")

default:
    @just --list

# Lint and compile-check
lint:
    ruff check .
    python3 -m compileall -q netbox_ip_history tests tools

# Run the test suite inside NetBox (throwaway test database)
test:
    cd "{{netbox_root}}" && DJANGO_SETTINGS_MODULE=netbox.settings PYTHONPATH=. python "{{justfile_directory()}}/tools/run_tests.py" "{{justfile_directory()}}/tests"

# Fail if models and migrations disagree
migrations-check:
    cd "{{netbox_root}}" && python manage.py makemigrations netbox_ip_history --check --dry-run

check: lint test migrations-check

# Release gate: versions, build, package contents
verify: check
    python3 tools/verify_release.py versions
    rm -rf dist && python3 -m build && python3 -m twine check dist/*
    python3 tools/verify_release.py package dist/*.whl dist/*.tar.gz
