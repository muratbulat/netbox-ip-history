# Release Checklist

This is the required sequence for cutting a new `netbox-ip-history` release.
Every step here is also enforced by CI (see the "CI enforcement" column) —
this checklist is for the human steps CI cannot perform (deciding the version
number, writing the CHANGELOG entry, and pushing the tag), plus a local
dry-run of the same gates so failures surface before a tag is pushed, not
after.

Do not skip a step because "it'll just run in CI anyway" — CI blocks the
**PyPI publish**, but a tag and a GitHub Release are themselves visible,
public, and hard to fully undo. Run the checks locally first.

| # | Step | Command | CI enforcement |
|---|------|---------|-----------------|
| 1 | Working tree is clean | `git status` | — (human step) |
| 2 | Bump the version | Edit `version` in `pyproject.toml` **and** the fallback `__version__` in `netbox_ip_history/__init__.py` — they must match exactly | `tools/verify_release.py versions`, all workflows |
| 3 | Add a CHANGELOG entry | New `## [X.Y.Z] - YYYY-MM-DD` section at the top of `CHANGELOG.md`, version matching step 2 | `publish-pypi.yml` `verify` job; `build.yml` on tag push |
| 4 | Full local test suite | `python -m unittest discover -s tests -v` | `ci.yml` |
| 5 | Migration drift check (fresh DB) | See "Migration drift check" below | `netbox-matrix.yml`, `publish-pypi.yml` `verify` job |
| 6 | Django system check | `python manage.py check` (inside a real NetBox checkout with the plugin installed) | `netbox-matrix.yml`, `publish-pypi.yml` `verify` job |
| 7 | Build wheel + sdist | `python -m build` | `ci.yml`, `build.yml`, `publish-pypi.yml` |
| 8 | Inspect package contents | `python tools/verify_release.py package dist/*.whl dist/*.tar.gz` | same as above |
| 9 | Install the built wheel in a clean environment and run tests against it (not the source checkout) | See "Installed-wheel test" below | `ci.yml` `package-verify` job, `publish-pypi.yml` `verify` job |
| 10 | Security scan | `python -m pip_audit --strict .` and gitleaks (`security.yml`) | `security.yml`, runs on every push including tags |
| 11 | Push commits | `git push origin main` | — (human step; never force-push) |
| 12 | Tag the release | `git tag vX.Y.Z && git push origin vX.Y.Z` | tag push triggers `build.yml` and `netbox-matrix.yml` |
| 13 | Wait for the tag's CI to pass | Check the Actions tab for the pushed tag | — (human step: do not proceed on red CI) |
| 14 | Create the GitHub Release | From the pushed tag, using the CHANGELOG entry as the release notes | `release: published` triggers `publish-pypi.yml`, whose `publish` job only runs if its own `verify` job (re-running steps 2–3, 5–9 against the release tag) passes — **a release cannot reach PyPI if this fails**, regardless of what earlier workflow runs showed |

## Migration drift check

NetBox wraps `manage.py makemigrations` and refuses to *write* a migration
outside its own dev workflow, but `--check --dry-run` still runs the real
Django autodetector and exits non-zero if the committed migrations disagree
with current model state — this is what all of `ci`, `netbox-matrix`, and
the release `verify` job run to catch missing migrations before they ship:

```bash
cd netbox/netbox   # inside a real NetBox checkout with the plugin installed
python manage.py migrate --noinput
python manage.py makemigrations netbox_ip_history --check --dry-run
```

A fresh (never-migrated) database is required — a database that has already
applied a stale migration set can mask drift that only appears on a true
from-scratch install.

## Installed-wheel test

Source-tree tests can pass while the wheel is missing files (templates,
locale, migrations, management commands) that aren't picked up by
`packages.find` or `package-data`. Always test the *installed artifact*:

```bash
python -m build
python -m venv /tmp/release-check-env
/tmp/release-check-env/bin/pip install dist/*.whl
cp -r tests /tmp/release-check-tests && cd /tmp/release-check-tests
/tmp/release-check-env/bin/python -c \
  "import netbox_ip_history as m; assert 'site-packages' in m.__file__, m.__file__"
/tmp/release-check-env/bin/python -m unittest discover -s . -v
```

Running from a directory that does **not** contain a `netbox_ip_history/`
source folder is essential — otherwise Python's `sys.path` resolves the
import to the local checkout instead of the installed wheel, and the test
silently proves nothing.

## What is never automated

Creating the Git tag and creating the GitHub Release are always manual, human
actions — see `.agents/rules/deployment.md`. No agent or workflow in this
repository creates a tag, a release, or publishes to PyPI on its own
initiative.
