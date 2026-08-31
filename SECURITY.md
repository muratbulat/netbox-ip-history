# Security policy

Use GitHub Security Advisories for vulnerability reports where available. Do not publish credentials, API tokens, authentication headers, private keys, production exports, or database dumps in issues or pull requests.

External database imports must use read-only accounts, administrator-defined mappings, and parameterized access. Secrets belong in environment variables or secure NetBox `PLUGINS_CONFIG` references and must never be copied to `ImportSource`, `HistoricalIPEvent`, `ImportJob`, browser responses, or logs.

The current development line is `0.3.x`. Security fixes should be tested in a NetBox 4.4+ environment before release; the priority-verified combination is NetBox 4.6.8 / Python 3.14 (see `COMPATIBILITY.md`).