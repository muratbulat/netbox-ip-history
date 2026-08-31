# Security Review

## Scope

This review covers source imports, provenance storage, permissions, external credentials, SQL adapter boundaries, upload handling, and native NetBox audit isolation.

## Controls

- All UI views (`history`, `event_detail`, `compare`, `import_view`, `import_jobs`, `import_job`, `source_support`, `rollback_import`) enforce strict Django model permissions with `@permission_required(..., raise_exception=True)`. Unauthenticated and unauthorized requests are rejected immediately.
- REST API viewsets inherit NetBox permission and authentication enforcement.
- IP Address detail page template extensions (`template_content.py`) check permissions before rendering action buttons or panels.
- Imported history is stored in plugin-owned models and never inserted into `core.ObjectChange`.
- Import and rollback views require explicit Django permissions and state-changing actions are CSRF-protected.
- External secrets are configuration references; tokens and passwords are not model fields or logs.
- Generic SQL is an administrator-only read-only contract and currently refuses execution without a configured connector.
- Source record data is retained for audit, so operators must treat `raw_data` as potentially sensitive.
- File hashes and size are recorded; uploaded contents are not retained by the plugin.
- IPs are parsed with Python's `ipaddress` library and timestamps require an explicit timezone when naive.

## Residual risks

The upload UI reads a file into memory and lacks a configurable upload-size limit. Pagination, streaming/bulk persistence, and full external API clients remain planned. Apply upstream request limits and use controlled files until those features are implemented.