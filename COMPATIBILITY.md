# Compatibility

This matrix records evidence, not aspirations. A combination is marked `VERIFIED` once validated on live NetBox installations or CI pipeline execution with the plugin installed.

| Plugin | NetBox | Python | Django (via NetBox) | Status | Evidence |
| --- | --- | --- | --- | --- | --- |
| 0.3.x | 4.4.x (v4.4.10) | 3.11 | as pinned by NetBox 4.4.10 | VERIFIED | `.github/workflows/netbox-matrix.yml` CI pipeline passes (real Django ORM/migrations, not source-only) |
| 0.3.x | 4.5.x (v4.5.10) | 3.12 | as pinned by NetBox 4.5.10 | VERIFIED | `.github/workflows/netbox-matrix.yml` CI pipeline passes |
| 0.3.x | 4.6.x (v4.6.8) | 3.12 | as pinned by NetBox 4.6.8 | VERIFIED | `.github/workflows/netbox-matrix.yml` CI pipeline passes |
| 0.3.x | **4.6.x (v4.6.8)** | **3.14** | **6.0.8** | **VERIFIED (priority)** | Tested and verified against a real NetBox Community v4.6.8 instance; this is the priority lane in CI |

The plugin has no pinned Django/DRF dependency (see `pyproject.toml`) — it rides on whatever Django version the host NetBox install provides. "Django (via NetBox)" above records what each NetBox version actually installs, not a plugin requirement. Do not pin a Django version independently of NetBox.

NetBox 4.6.8 / Python 3.14 / Django 6.0.8 is treated as the priority lane and must stay green above all others. NetBox's own `min_version`/`max_version` bounds (see `netbox_ip_history/__init__.py`) are `4.0.0`–`4.99.99`; only the four rows above have actual evidence behind them — the rest of that range is unverified, not unsupported.

No NetBox release numbered `6.0.8` exists upstream — `6.0.8` is always the Django version production runs, under NetBox `4.6.8`. Keep the two numbers paired and labeled (as in the table above) wherever this combination is written elsewhere; never write "NetBox 6.0.8".

The plugin is not NetBox Labs certified. Certification is release-specific and requires external review.
