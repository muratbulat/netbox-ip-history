# repo-ai-init:managed

# Show repository status
status:
    git status --short --branch

# Show current changes
diff:
    git diff

# Check patch formatting and whitespace (staged and unstaged, vs HEAD)
diff-check:
    git diff HEAD --check

# Compile-check the package and test suite (mirrors ci.yml)
compile:
    python3 -m compileall -q netbox_ip_history tests

# Run the unit test suite (no Django required; uses coverage if installed, else plain unittest)
test:
    #!/usr/bin/env bash
    set -euo pipefail
    if python3 -c "import coverage" 2>/dev/null; then
        python3 -m coverage run --source=netbox_ip_history -m unittest discover -s tests -v
        python3 -m coverage report -m
    else
        echo "note: 'coverage' not installed, running plain unittest (see ci.yml for the coverage-instrumented run)" >&2
        python3 -m unittest discover -s tests -v
    fi

# Normal development verification: fast, no Django/NetBox/network required
check: diff-check compile test
    @echo "Development checks passed."

# Release-gate: pyproject.toml / __init__.py / CHANGELOG.md versions agree
version-check:
    python3 tools/verify_release.py versions

# Build sdist + wheel (requires: pip install build twine)
build:
    rm -rf dist
    python3 -m build
    python3 -m twine check dist/*

# Verify built artifacts contain required runtime files (migrations, templates, locale, LICENSE)
package-check: build
    python3 tools/verify_release.py package dist/*.whl dist/*.tar.gz

# Install the built wheel into a clean venv and test it, not the source tree (mirrors ci.yml)
wheel-test: build
    #!/usr/bin/env bash
    set -euo pipefail
    rm -rf /tmp/nih-wheel-env /tmp/nih-installed-wheel-tests
    python3 -m venv /tmp/nih-wheel-env
    /tmp/nih-wheel-env/bin/pip install --upgrade pip -q
    /tmp/nih-wheel-env/bin/pip install dist/*.whl -q
    cp -r tests /tmp/nih-installed-wheel-tests
    cd /tmp/nih-installed-wheel-tests
    /tmp/nih-wheel-env/bin/python -c "import netbox_ip_history; assert 'site-packages' in netbox_ip_history.__file__, netbox_ip_history.__file__"
    /tmp/nih-wheel-env/bin/python -m unittest discover -s . -v
    rm -rf /tmp/nih-wheel-env /tmp/nih-installed-wheel-tests

# Dependency vulnerability scan (requires: pip install pip-audit)
audit:
    python3 -m pip_audit --strict .

# Broader release verification: check + version/package/wheel/dependency checks (no local NetBox stack; see netbox-matrix.yml for that)
verify: check version-check package-check wheel-test audit
    @echo "Full verification passed."

default:
    @just --list
