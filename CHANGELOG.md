# Changelog

All notable changes to this project will be documented here.

## [Unreleased]

### Verified
- NetBox 4.7.0 compatibility: reviewed against NetBox 4.7's breaking changes (PostgreSQL `ltree` hierarchy migration, `Service.protocol`/`ports` → `port_mappings`, pre-rendered config context, deferred global search indexing, removed `querystring` tag, etc.) — none affect this plugin, as it uses only documented plugin APIs and touches none of the changed models. Verified live against a real NetBox Community v4.7.0 instance: `manage.py check`, `makemigrations --check` (no drift), and a full IP lifecycle (create/reassign/unassign/delete via both native signals and CSV import) with deleted-object history and global search all working correctly. See [COMPATIBILITY.md](COMPATIBILITY.md).

## [0.3.1]

Initial public baseline.
