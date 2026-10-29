# Changelog

All notable changes to this project are documented here.

## [Unreleased]

### Added
- `migrate` records ipaddress `ObjectChange` rows that aren't yet history events (e.g. history
  from before installation) and indexes them for global search, so no manual `reindex` is
  needed. Already-recorded changes are skipped; disable with `backfill_on_migrate: False`.

### Fixed
- Import duplicate detection now also compares VRF, route distinguisher, MAC address, status
  and DNS name, so the same row in two VRFs is no longer dropped as a duplicate. Migration
  `0009` recomputes the fingerprints of already-imported events (versioned algorithm v2), so
  re-importing an old file still matches what it imported; native events are untouched.

## [1.0.0] - 2026-10-26

Re-engineered on NetBox's native plugin APIs. **Requires NetBox 4.7.0+ and Python 3.12+.**

### Upgrading from 0.3.x
- Run `manage.py migrate`. Migrations `0001`–`0007` are squashed (existing installs skip
  them); `0008` adds the NetBox model features and repairs data: dry-run import jobs
  left behind by earlier versions are deleted, native events are detached from their
  synthetic import job, and the global VRF is stored as an empty name.
- Optionally run `manage.py import_ip_history --native` to re-record native events with
  the improved owner/interface resolution.
- `sync_netbox_ip_history` is replaced by `import_ip_history --native`;
  `generate_sample_data` was removed.
- URLs changed: the timeline lives at `/plugins/ip-history/`, events, sources and import
  jobs have standard NetBox list/detail pages, and the REST API exposes `sources/`,
  `import-jobs/`, `events/`, `timeline/` and `compare/`.
- `ImportSource.support_level/capabilities/inspection/authority` and `ImportJob.dry_run`
  were removed; support data comes from the importer registry.

### Added
- `ImportSource`, `ImportJob` and `HistoricalIPEvent` are `NetBoxModel`s: tags, custom
  fields, change logging, journaling, bookmarks, export templates and event rules.
- Standard list, detail, edit, delete, bulk edit/delete and changelog views with NetBox
  tables, filter forms and `q` search; global search indexes.
- REST API `timeline/` and `compare/` endpoints (`?ip=`), permission-checked and
  restricted to objects the caller may view.
- Background imports through NetBox's job system (`ImportHistoryJobRunner`); large
  uploads are queued automatically.
- Infoblox NIOS CSV and NetBox changelog (`/api/core/object-changes/`) importers; flat XML
  exports for generic sources.
- Composite indexes for timeline queries: `(ip_address, vrf_name, timestamp)` and
  `(source, timestamp)`.

### Changed
- All views and API endpoints are default-closed: every workflow page requires a model
  permission and querysets honour object-level permissions.
- Vendor sources without a format-specific parser share one data-driven profile table
  and are labelled "generic" in the support matrix.
- The Django-optional fallback code paths were removed; the plugin targets NetBox only.

### Fixed
- Timeline `vrf=Global` filter excluded native events (stored as `"Global"`).
- Dry runs persisted `ImportJob` rows on every preview.
- Non-canonical IPv6 queries missed stored events, and invalid IP input could raise a
  database error.
- Timeline rendering issued several queries per native event; lookups are now batched
  into a constant number of queries.
- A cached native `ImportSource` that was deleted broke every subsequent IP change.
- Recording a native event no longer creates a change-log entry of its own.
- Bulk-imported events were missing from NetBox global search.
- Over-long source values no longer abort an import.
- XML input with DOCTYPE/ENTITY declarations is rejected (XXE / entity expansion).

## 0.x

Pre-1.0 releases are no longer available on PyPI. Installations of 0.3.x upgrade to
1.0.0 directly; see *Upgrading from 0.3.x* above.
