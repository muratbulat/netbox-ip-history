# Architecture

Reference documentation for how `netbox_ip_history` is actually built today.
This is descriptive, not a rulebook — for behavioral rules an AI coding agent
must follow, see `AGENTS.md`.

## What this plugin does

A NetBox plugin that unifies **native NetBox IP lifecycle events** (via
`core.ObjectChange`) with **imported historical data from external IPAM/DCIM
systems**, exposing both through a single per-IP timeline, a REST API, and
global search. The goal is to reliably answer "which device/VM/interface
owned this IP, when, and why did it change?" across both NetBox-native
history and imported history from GestióIP, phpIPAM, RackTables, GLPI, and
other IPAM/DCIM platforms (see "Importer status" below for how much of that
list is actually implemented today, as opposed to just registered).

## Module map

- `models.py` — `ImportSource`, `ImportJob`, `HistoricalIPEvent` (the core
  historical event log; unique `fingerprint` per event; indexed on
  IP/timestamp/source/event_type). Not strictly append-only — deleting an
  `ImportJob` via `rollback_job()` deletes its `HistoricalIPEvent` rows.
- `signals.py` — hooks `post_save` on `core.ObjectChange` to auto-convert
  native NetBox IP address changes into `HistoricalIPEvent` rows in real
  time (toggle:
  `PLUGINS_CONFIG["netbox_ip_history"]["enable_native_event_tracking"]`).
- `services/timeline.py` — the heavy lifting: `extract_ip_from_change`,
  `extract_netbox_change_details`, `resolve_assigned_object_type`,
  `native_events`, `get_timeline`. Heuristic code that reconstructs
  host/interface/VRF/status from `core.ObjectChange` JSON snapshots
  (`prechange_data`/`postchange_data`), including device-vs-VM
  disambiguation by inspecting ContentType, REST URLs, and DNS-name
  cross-checks. Prone to point-fix regressions — treat changes here with
  extra care and see the regression-test note below.
- `services/import_service.py` — `run_import()` / `rollback_job()`:
  batch-persists importer records into `HistoricalIPEvent`, with dedup via
  `fingerprint` and dry-run support.
- `services/normalize.py`, `services/owner_resolver.py` — field/IP/timestamp
  normalization and best-effort Device/VM/Interface resolution by name or
  MAC.
- `importers/` — pluggable adapter architecture: `base.py`
  (`BaseIPAMImporter` ABC), `registry.py` (`@register_importer` decorator +
  `IMPORTERS` dict + `support_matrix()`), `capabilities.py`
  (`ImportCapability`, `SupportLevel` enums), `dto.py` (`SourceInspection`).
- `api/`, `views.py`, `forms.py`, `filtersets.py`, `tables.py`,
  `navigation.py`, `template_content.py`, `search.py` — standard NetBox
  plugin UI/API surface.
- `migrations/` — Django migrations; `0004`–`0006` are **data migrations**
  (deduping GestióIP sources, seeding the source support matrix, repairing
  legacy `HistoricalIPEvent` rows against newer
  `extract_netbox_change_details` logic).

## The defensive `try/except ImportError` pattern

Nearly every core module (`models.py`, `choices.py`, `signals.py`,
`services/*.py`, `importers/base.py`) is written so it can be **imported
without Django or NetBox installed**, via
`try: from django... except ImportError: <mock fallback>`. This is
intentional: the fast CI job (`.github/workflows/ci.yml`) runs
`unittest discover` with **no Django installed at all**, so these fallbacks
are what make that job pass. Real NetBox/Django integration is validated
separately in `.github/workflows/netbox-matrix.yml`, which clones actual
NetBox against Postgres/Redis service containers.

Implication: **the mocked/fallback branch is what the local unit test suite
exercises, not the real Django branch.** As of the 2026-08 audit that
established this note, coverage showed `views.py` (4%), `signals.py` (9%),
`models.py` (17%), and `timeline.py` (41%) barely touched by `tests/` — a
snapshot, not a live number; re-run `just check` (or the coverage-instrumented
variant in `ci.yml`) for the current figures. When you change logic inside a
`try: from django...` block, the local test suite will not catch regressions
in the real-Django path; either add NetBox-environment coverage (see
`netbox-matrix.yml`) or manually trace the real-Django branch with extra care.

There is no local NetBox/Postgres/Redis stack in this repo, and none should
be vendored into it. To validate against real NetBox locally, mirror
`netbox-matrix.yml`'s recipe by hand in a directory *outside* this repo
(e.g. a sibling `netbox-dev/` checkout) — clone NetBox there, install this
plugin into it, and run against that.

## Importer status

The registry/capability architecture (`base.py` → `registry.py` →
`capabilities.py`) is clean and reusable, but of the source types registered
in `choices.SourceType` / `importers/registry.py`, only **two have real
vendor-specific parsing**:

- `gestioip.py` — real CSV + audit-log parser, GestióIP-specific event-string
  grammar. This is the reference implementation for what a real importer
  looks like.
- `phpipam.py` — thin field-alias mapping over the generic CSV/JSON importer.

Everything else — **including RackTables and GLPI**, both explicitly
in-scope for this project — is a thin stub (`bluecat.py`, `device42.py`,
`efficientip.py`, `glpi.py`, `infoblox.py`, `manageengine.py`, `micetro.py`,
`microsoft_ipam.py`, `nautobot.py`, `netbox.py`, `nipap.py`,
`racktables.py`, `ralph.py`, `solarwinds.py`, `teemip.py`) that registers a
display name/capabilities and delegates entirely to the generic CSV/JSON
importer (`vendor_file.py` → `generic_csv.py`/`generic_json.py`), with **no
vendor-specific field mapping or event-log parsing**. `support_level` on
these is honestly marked `EXPERIMENTAL`/`EXPORT`, so this isn't mis-sold to
users — but don't assume "RackTables support" or "GLPI support" means more
than "generic CSV import with that vendor's name attached."

See `CONTRIBUTING.md` for the contract a new importer must follow
(subclass, capabilities, `raw_data` preservation, fixtures/tests).

Note: `netbox_ping.py` is also registered in `importers/registry.py` but has
no corresponding `choices.SourceType` entry, so it isn't reachable through
the normal source-type selection UI/API today.
