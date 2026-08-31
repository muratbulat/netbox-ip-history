# Contributing

## Development

Use a NetBox 4.4+ development installation and a Python 3.10+ virtual environment. Install the project with `pip install -e .`, run migrations, and keep credentials and source exports outside the repository.

## Tests and standards

Run `python -m compileall -q netbox_ip_history tests`, `python -m unittest discover -s tests -v`, and `python -m pip wheel . --no-deps --wheel-dir dist`. Keep changes typed where useful, focused, and compatible with current NetBox APIs.

## Adding an importer

Create one module under `netbox_ip_history/importers/`, subclass the common base, declare `capabilities` and `support_level`, implement `inspect_source`, emit normalized DTOs, preserve source-native fields in `raw_data`, and register with `@register_importer`. Do not add vendor branches to the import engine, invent API endpoints, or convert observations into assignments without source evidence. Add sanitized fixtures and tests.

Pull requests should explain source/version assumptions, permissions, migration behavior, tests, and any unsupported capabilities. Never include credentials, proprietary exports, or real user data.