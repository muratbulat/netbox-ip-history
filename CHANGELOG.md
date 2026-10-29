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
- Re-importing a file with undated rows (e.g. any Infoblox export) no longer creates new
  events each time. Such rows are flagged as *undated* events and identified without their
  import-time timestamp, and Infoblox record IDs no longer contain CSV line numbers.
  Migration `0010` flags existing undated events and recomputes their fingerprints (v3).
- Importing a file that was already imported into the same source (same SHA-256) now warns,
  in the UI and in the job summary.
- The *IP History* tab of an IP address only shows events of that address in its own VRF
  (exact match), not the same address in the global table or other VRFs; the header button
  and the tab's filter link carry the VRF to the full timeline.
- Import sources reject unknown timezones (previously a typo silently shifted every imported
  timestamp to the server timezone) and field mappings that aren't an object of known field
  names to column names, in the UI and the API. A source saved with an invalid mapping by an
  earlier version now fails its import with an error instead of a server error, and a failed
  background import no longer leaves its import job pending.
- Background imports record the uploaded file's SHA-256 on the import job (it was left empty).
- Import sources left by pre-1.0 versions are migrated (`0011`): `generic_sql` becomes
  `other`, and `netbox`-typed sources other than the native one become *NetBox changelog
  export* (they were hidden from the import form and treated as native history). The `netbox`
  source type and slug are now reserved for NetBox's own history, and the native source is
  looked up by both.
- Object-level permissions are enforced for imports and rollbacks: an import is rolled back
  if any created event falls outside the user's *add* constraints (also for background
  imports), and a rollback is refused if any event of the job falls outside the user's
  *delete* constraints. Previously both acted on every event regardless of constraints.
- The REST timeline endpoint accepts the same filters as the UI: `date_from`, `date_to`
  (YYYY-MM-DD; invalid dates return 400), `owner` and `username`, all documented in the OpenAPI
  schema. Each entry has a `kind` (`event` or `objectchange`) telling which object its `id`
  refers to.
- Imported prefix lengths are validated per address family (a `64` on an IPv4 address is no
  longer stored) and IPv4 dotted netmasks such as `255.255.255.0` are accepted.
- New per-source *date order* setting (`date_order`: `dmy`, the default and previous
  behaviour, or `mdy`) for slash-separated dates, so US-style exports (`03/04/2025` = March 4)
  are no longer silently read day-first. Migration `0012` adds it.
- The import form and `import_ip_history --delimiter` accept `tab` (or `\t`) for
  tab-separated files; the single-character field previously couldn't express a TAB.

### Security
- Timeline CSV exports prefix values starting with `=`, `+`, `-`, `@`, tab or carriage return
  with `'`, so imported data cannot inject spreadsheet formulas. JSON exports are unchanged.

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
