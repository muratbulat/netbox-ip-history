<!-- repo-ai-init:managed -->
# netbox-ip-history — Agent Instructions

NetBox plugin unifying native NetBox IP lifecycle events (`core.ObjectChange`)
with imported historical data from external IPAM/DCIM systems. Package:
`netbox_ip_history`; version lives in `pyproject.toml` /
`netbox_ip_history/__init__.py` (don't hardcode the version number here —
read those files).

## Stack
- Python `>=3.10` (classifiers cover 3.10-3.14). CI's priority lane is
  NetBox 4.6.8 / Python 3.14 / Django 6.0.8 — keep this lane green above
  all others; see `COMPATIBILITY.md` for the full verified matrix.
- NetBox plugin with **zero declared runtime dependencies** in
  `pyproject.toml` — it rides on the host NetBox's own Django/DRF version.
  Do not add a `dependencies` list pinning Django/DRF.
- Install: `pip install -e .` (editable) into a NetBox dev environment.
- No lint/format/type-check tooling configured (no ruff/black/isort/
  flake8/mypy/pre-commit/tox). Match existing style (4-space indent, see
  `.editorconfig`) rather than introducing one unasked; if you do add one,
  update `.github/workflows/ci.yml` in the same change so CI enforces it too.

## Critical gotchas
See `docs/ARCHITECTURE.md` for the full module map and importer-stub list;
this section is only the behavioral rules that follow from them.
- Most core modules (`models.py`, `signals.py`, `services/*.py`,
  `importers/base.py`) wrap Django imports in `try/except ImportError` with
  mock fallbacks, so they import with no Django installed. The local test
  suite (`tests/`) only exercises that fallback branch — real NetBox
  behavior is validated separately by `.github/workflows/netbox-matrix.yml`.
  A change inside a `try: from django...` block needs manual tracing or a
  NetBox-environment run; local tests will not catch regressions there.
- Among the vendor-labelled importers in `importers/`, only `gestioip.py`
  and `phpipam.py` have real vendor-specific parsing. Everything else
  (including RackTables, GLPI) is a stub delegating to the generic
  CSV/JSON importer — don't imply real vendor support without adding
  actual parsing. A new importer must follow `CONTRIBUTING.md`'s contract:
  subclass the common base, declare `capabilities`/`support_level`,
  preserve source-native fields in `raw_data`, emit normalized DTOs, never
  infer an assignment without source evidence, and add fixtures/tests
  (`gestioip.py` is the reference implementation).
- `services/timeline.py` is heuristic (device/VM disambiguation, IP
  extraction from `core.ObjectChange` JSON) and has shipped several
  point-fix regressions. Add a regression test in
  `tests/test_timeline_exact_ip_matching.py` for any fix here.

## Compatibility guardrails — explicit approval required to change
- `requires-python`, NetBox `min_version`/`max_version`
  (`netbox_ip_history/__init__.py`), and the plugin version in
  `pyproject.toml`/`__init__.py`.
- `COMPATIBILITY.md` is the source of truth for *verified* NetBox versions —
  update it alongside any compatibility claim, backed by evidence (a
  passing `netbox-matrix.yml` run, or your own documented testing against a
  real NetBox instance — see the "VERIFIED (priority)" row there).

## Migrations — never modify, always add
- Never modify an already-released migration (check `CHANGELOG.md`); add a
  new one instead. `0004`-`0006` are precedent for in-place data repairs
  (broad `try/except`, `apps.get_model`, not direct model imports).
- Local unit tests never load Django, so they cannot catch model/migration
  drift. Before calling a model change complete, run
  `manage.py makemigrations netbox_ip_history --check --dry-run` against a
  real NetBox checkout (see `netbox-matrix.yml`'s "no migration drift" step).
- Don't regenerate or squash existing migrations without being asked.

## Deployment / git approval
See `.agents/rules/deployment.md` — it is the single authority on this and
takes precedence over anything below. In short: any `git push`,
deploy/service restart, migration against a live host, tag/release (or
package publish), or destructive git op needs fresh, explicit approval in
the current request; no standing authorization carries forward. Deployment
target identity and access details are never documented in this repo — they
live in the operator's own local SSH config and environment variables.
There is no deploy script in this repo — deployment is a manual, ad hoc
operation.

## Verification
- `just check` — normal development verification (whitespace/diff check,
  compile-check, full unit test suite). No Django or network access needed.
- `just verify` — adds release-oriented checks on top of `check`: version
  consistency across `pyproject.toml`/`__init__.py`/`CHANGELOG.md`, package
  build + metadata validation, installing the built wheel into a clean venv
  and testing it (not the source tree), and a dependency vulnerability scan.
  Run before anything release-adjacent.
- There is no local NetBox/Postgres/Redis stack in this repo — full
  integration testing only runs in CI (`netbox-matrix.yml`).
- Always inspect `git status` and `git diff` (staged and unstaged) before
  finishing. Do not commit or push unless explicitly asked.

## Scope
- Make the smallest correct change; don't refactor unrelated code or add
  dependencies without justification.
- Never hard-code credentials, tokens, or secrets — `security.yml` greps
  tracked files for a short list of known token/key formats (GitHub tokens,
  AWS keys, PEM headers). That grep does **not** catch generic hardcoded
  passwords — `gitleaks` (same
  workflow) is the broader secret scan; don't treat the narrow grep as your
  only secret check when reviewing security-sensitive changes.
- Keep commits logically scoped (security fixes, importer fixes, feature
  work, etc. as separate commits) rather than bundling unrelated changes.
- Installing packages into a project-local virtualenv is fine; installing
  NetBox itself, Docker, or system-wide Python packages on the dev machine
  is not, without asking — and don't vendor a NetBox checkout into this
  repo. There is no local NetBox stack here by design (see
  `docs/ARCHITECTURE.md` and `netbox-matrix.yml` for how real-NetBox
  testing actually happens).
