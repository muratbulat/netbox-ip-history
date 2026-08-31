# NetBox IP History — Installation Guide

Package: `netbox-ip-history` (PyPI) · Plugin module: `netbox_ip_history` · Migration app label: `netbox_ip_history`

## 1. Requirements

- **NetBox versions:** the plugin declares `min_version = "4.0.0"`, `max_version = "4.99.99"` (`netbox_ip_history/__init__.py`), but only specific releases have actually been verified. See [`COMPATIBILITY.md`](../COMPATIBILITY.md) for the up-to-date evidence matrix — do not assume an unverified NetBox release will work correctly just because it falls inside the declared range.
- **Python versions:** 3.10, 3.11, or 3.12 (`pyproject.toml` classifiers; `requires-python >= 3.10`).
- **Virtual environment:** the plugin must be installed into NetBox's own Python virtual environment (typically `/opt/netbox/venv`), never into system Python.
- **PostgreSQL / Redis:** the plugin adds no new database or cache dependency — it uses whatever PostgreSQL and Redis instance your NetBox installation is already configured with. No additional services are required.
- **Permissions:** installing/upgrading requires shell access to the NetBox server with rights to write into the virtualenv and restart NetBox's systemd services (or Docker Compose stack). The plugin's own web-facing permissions (`view_historicalipevent`, `add_historicalipevent`, `delete_historicalipevent`, `view_importjob`, `view_importsource`) are ordinary Django model permissions, assigned to NetBox users/groups after installation like any other NetBox permission.
- **Backup recommendation:** back up your NetBox PostgreSQL database (e.g. `pg_dump`) before any plugin install, upgrade, or migration step, in addition to your normal NetBox backup routine. This plugin does not modify NetBox's own tables, but any Django migration is easier to recover from with a fresh backup on hand.

## 2. Installation via PyPI / pip

This is the recommended installation method for production.

### Activate NetBox virtual environment

```bash
source /opt/netbox/venv/bin/activate
```

### Install plugin

```bash
pip install netbox-ip-history
```

### Configure NetBox

Add the plugin to `PLUGINS` in NetBox's `configuration.py`:

```python
PLUGINS = [
    "netbox_ip_history",
]
```

Optionally, override its default settings via `PLUGINS_CONFIG` (both shown below default to `True`, so this block is only needed to change them):

```python
PLUGINS_CONFIG = {
    "netbox_ip_history": {
        "enable_global_search": True,          # index IP history in NetBox's global search
        "enable_native_event_tracking": True,   # auto-record native NetBox IP changes in real time
    }
}
```

### Run migrations

```bash
python /opt/netbox/netbox/manage.py migrate
```

### Collect static files

```bash
python /opt/netbox/netbox/manage.py collectstatic --no-input
```

### Restart NetBox services

```bash
systemctl restart netbox netbox-rq
```

Actual service names/units vary by installation (Docker Compose, a different init system, custom unit names) — restart whatever runs the NetBox WSGI process and its background worker.

### Verify

```bash
python /opt/netbox/netbox/manage.py check
python /opt/netbox/netbox/manage.py showmigrations netbox_ip_history
```

Then confirm the plugin loads in the browser at `/plugins/ip-history/`.

## 3. Installation from GitHub

Keep this separate from the PyPI flow above — do not mix `pip install netbox-ip-history` with a GitHub checkout of the same environment.

There are two distinct GitHub-based installs:

- **Production source installation** — install a specific tagged commit as a normal (non-editable) package. Use this when you want to run from source but do not intend to modify the code on this host.
- **Editable/development installation** — install with `pip install -e .`, so the running plugin is a live symlink to your working copy. Use this only for development; the checkout must stay in place for the plugin to keep working, and code changes take effect without reinstalling.

### Production source installation

```bash
source /opt/netbox/venv/bin/activate
pip install "netbox-ip-history @ git+https://github.com/muratbulat/netbox-ip-history.git@main"
```

Pin `@main` to a specific tag (e.g. `@v0.3.1`) for a reproducible production install.

### Editable/development installation

```bash
cd /opt
git clone https://github.com/muratbulat/netbox-ip-history.git
cd netbox-ip-history
source /opt/netbox/venv/bin/activate
pip install -e .
```

### Configure, migrate, and verify (both methods)

Same as the PyPI flow above:

```python
# configuration.py
PLUGINS = [
    "netbox_ip_history",
]
```

```bash
python /opt/netbox/netbox/manage.py migrate
python /opt/netbox/netbox/manage.py collectstatic --no-input
systemctl restart netbox netbox-rq
python /opt/netbox/netbox/manage.py check
python /opt/netbox/netbox/manage.py showmigrations netbox_ip_history
```

Verify at `/plugins/ip-history/`.

## 4. Upgrade — PyPI / pip

```bash
source /opt/netbox/venv/bin/activate
pip install --upgrade netbox-ip-history
```

Then, in order:

```bash
python /opt/netbox/netbox/manage.py migrate
python /opt/netbox/netbox/manage.py collectstatic --no-input
systemctl restart netbox netbox-rq
python /opt/netbox/netbox/manage.py showmigrations netbox_ip_history
```

Verify `/plugins/ip-history/` loads, then check NetBox and worker logs (`journalctl -u netbox -u netbox-rq`, or your platform's equivalent) if anything looks wrong.

`collectstatic` must be run after every upgrade — the plugin ships its own static assets, and skipping this step causes a NetBox "Static Media Failure" for any of them that changed.

## 5. Upgrade — GitHub

Handle GitHub/source upgrades separately from the PyPI flow.

Before updating, check for local modifications:

```bash
cd /opt/netbox-ip-history
git status
```

If local changes exist, review them first — do not discard them blindly. Never run `git reset --hard` as part of a normal upgrade; it silently destroys uncommitted work.

Normal upgrade workflow:

```bash
cd /opt/netbox-ip-history
git pull --ff-only
source /opt/netbox/venv/bin/activate
pip install -e .
```

`git pull --ff-only` refuses to proceed (rather than auto-merging or rebasing) if your local branch has diverged — investigate and reconcile manually if that happens.

If you installed via the non-editable production method (Section 3), reinstall from the updated checkout instead of `pip install -e .`:

```bash
pip install --force-reinstall --no-deps .
```

Then, as with any upgrade:

```bash
python /opt/netbox/netbox/manage.py migrate
python /opt/netbox/netbox/manage.py collectstatic --no-input
systemctl restart netbox netbox-rq
python /opt/netbox/netbox/manage.py showmigrations netbox_ip_history
```

Verify `/plugins/ip-history/` loads.

A GitHub source install has two parts that must be kept in sync: the Git checkout (source code) and the Python package registration in the venv (`pip`'s record of what's installed). Pulling new commits alone is not enough for a non-editable install — you must also reinstall the package so `pip`/Python picks up the change; an editable install (`-e .`) picks up source changes automatically but still needs `migrate`/`collectstatic`/restart for anything beyond pure Python logic.

## 6. Disable Plugin

The non-destructive way to turn the plugin off:

1. Remove or comment out `"netbox_ip_history"` in `PLUGINS` in `configuration.py`.
2. Restart NetBox services:
   ```bash
   systemctl restart netbox netbox-rq
   ```

This disables the plugin's UI, API, and background tracking, but preserves:

- the installed Python package,
- the plugin's database tables,
- all historical IP records already recorded.

Re-enabling later (adding the line back and restarting) restores full functionality with no data loss.

## 7. Uninstall — PyPI / pip

1. Remove `"netbox_ip_history"` from `PLUGINS` in `configuration.py`.
2. Restart NetBox:
   ```bash
   systemctl restart netbox netbox-rq
   ```
3. Activate the NetBox virtual environment:
   ```bash
   source /opt/netbox/venv/bin/activate
   ```
4. Uninstall the package:
   ```bash
   pip uninstall netbox-ip-history
   ```

Uninstalling the Python package does **not** delete the plugin's database tables or historical records — see Section 9 if you specifically need to remove that data too.

## 8. Uninstall — GitHub

1. Remove `"netbox_ip_history"` from `PLUGINS` in `configuration.py`.
2. If installed editable or from source, uninstall the Python package registration:
   ```bash
   source /opt/netbox/venv/bin/activate
   pip uninstall netbox-ip-history
   ```
3. Restart NetBox:
   ```bash
   systemctl restart netbox netbox-rq
   ```
4. Only after confirming the checkout is no longer needed (no other process references `/opt/netbox-ip-history`), remove the source directory:
   ```bash
   rm -rf /opt/netbox-ip-history
   ```

Do not delete the repository directory before uninstalling the Python package — for an editable install, doing so breaks the venv's package registration and can leave `pip` in an inconsistent state. This does not delete any user data; see Section 9 for that.

## 9. Complete Database Removal

**⚠️ DANGER / DESTRUCTIVE — this permanently deletes all historical IP records the plugin has stored.**

Normal uninstall (Sections 7–8) does **not** require deleting the plugin's database data, and doing so is rarely necessary — the tables are inert once the plugin is disabled/removed.

If you specifically need to remove the plugin's tables, the only safe, supported method is to reverse its own migrations, which is exactly what they're designed for:

```bash
source /opt/netbox/venv/bin/activate
python /opt/netbox/netbox/manage.py migrate netbox_ip_history zero
```

This runs the plugin's 6 migrations (`0001`–`0006`) in reverse and drops its tables (`ImportSource`, `ImportJob`, `HistoricalIPEvent`). It does not touch any native NetBox table.

Do this **only** after the plugin package itself is already uninstalled or `PLUGINS` no longer references it, and only after confirming — with your team, and against a fresh database backup — that the historical IP records are no longer needed. There is no undo once this runs. Do not attempt to hand-write a different rollback path; the migrations already provide one.

## 10. Verification

Run after any install or upgrade:

```bash
python /opt/netbox/netbox/manage.py check
python /opt/netbox/netbox/manage.py showmigrations netbox_ip_history
```

Also check:

- NetBox service status: `systemctl status netbox`
- Worker status: `systemctl status netbox-rq`
- The plugin loads without errors: visit `/plugins/ip-history/`
- The **IP History** button/tab appears on a NetBox IP Address detail page (`/ipam/ip-addresses/<id>/`)
- Static assets load (browser console / Network tab clean, no broken CSS or JS)
- NetBox and worker logs for warnings: `journalctl -u netbox -u netbox-rq` (or your platform's equivalent)

A **"Static Media Failure"** banner almost always means `collectstatic` was not run after install/upgrade, or the web server's static file path/permissions are misconfigured — it is not usually a sign the plugin itself is broken.

## 11. Troubleshooting

### Plugin does not appear

Check, in order:

1. `PLUGINS` in `configuration.py` actually lists `"netbox_ip_history"`.
2. You installed into NetBox's own virtual environment, not system Python.
3. The package is actually installed: `pip show netbox-ip-history`.
4. NetBox startup logs for an import error: `journalctl -u netbox -n 100`.

### Migration errors

```bash
python /opt/netbox/netbox/manage.py showmigrations netbox_ip_history
```

Any migration shown as not applied (`[ ]`) that should be applied indicates `migrate` did not complete — re-run it and read the error output; do not skip or fake-apply migrations.

### Static Media Failure

```bash
python /opt/netbox/netbox/manage.py collectstatic --no-input
```

If the failure persists after that, verify your web server's static file mapping (e.g. nginx `location /static/`) points at NetBox's `STATIC_ROOT`, and that the web server process can actually read the files (ownership/permissions, including the traversal permission on parent directories).

### Import/module error

```bash
pip show netbox-ip-history
which python
```

Confirm `pip`/`python` here resolve inside the **NetBox virtual environment** (`/opt/netbox/venv/...`), not a system or unrelated Python install — this is the most common cause of "plugin installed but NetBox can't find it."

### Service errors

```bash
systemctl status netbox
systemctl status netbox-rq
journalctl -u netbox -n 100 --no-pager
```

Service unit names vary by installation; use whatever your platform actually defines.

## 12. Offline / Air-Gapped Installation

If the NetBox server has no internet access, do not attempt `pip install netbox-ip-history` or `pip install -e .` from a git clone directly on it — both need to reach PyPI/GitHub. Instead, build the package once on a connected machine and transfer only the resulting wheel file.

### On a connected development/build machine

```bash
git clone https://github.com/muratbulat/netbox-ip-history.git
cd netbox-ip-history
python -m pip install --upgrade build
python -m build
```

This produces `dist/netbox_ip_history-<version>-py3-none-any.whl` (and a `.tar.gz` sdist) using the standard Python build toolchain declared in `pyproject.toml` — no custom packaging step is required or supported.

### Transfer

Copy just the wheel file to the air-gapped server by whatever transfer method your environment allows (`scp` over a jump host, removable media, an internal artifact mirror, etc.):

```bash
scp dist/netbox_ip_history-<version>-py3-none-any.whl user@netbox-host:/tmp/
```

### On the air-gapped NetBox server

```bash
source /opt/netbox/venv/bin/activate
pip install --no-index /tmp/netbox_ip_history-<version>-py3-none-any.whl
```

`--no-index` makes pip install only from the local file, never attempting to reach PyPI. Since this plugin has zero required runtime dependencies beyond what NetBox itself already provides (see Requirements above), no dependency-bundling step is needed for a normal install.

Then continue exactly as any other install/upgrade: `PLUGINS` configuration, `migrate`, `collectstatic --no-input`, service restart, and verification (Sections 2 and 10 above apply unchanged — only the installation command differs).

To upgrade an existing offline install, repeat this process with the new version's wheel and `pip install --no-index --upgrade /tmp/netbox_ip_history-<new-version>-py3-none-any.whl`.

## 13. Quick Command Reference

```bash
# PyPI install
source /opt/netbox/venv/bin/activate
pip install netbox-ip-history
python /opt/netbox/netbox/manage.py migrate
python /opt/netbox/netbox/manage.py collectstatic --no-input
systemctl restart netbox netbox-rq

# GitHub install (editable/dev)
cd /opt && git clone https://github.com/muratbulat/netbox-ip-history.git
cd netbox-ip-history
source /opt/netbox/venv/bin/activate
pip install -e .
python /opt/netbox/netbox/manage.py migrate
python /opt/netbox/netbox/manage.py collectstatic --no-input
systemctl restart netbox netbox-rq

# PyPI upgrade
source /opt/netbox/venv/bin/activate
pip install --upgrade netbox-ip-history
python /opt/netbox/netbox/manage.py migrate
python /opt/netbox/netbox/manage.py collectstatic --no-input
systemctl restart netbox netbox-rq

# GitHub upgrade
cd /opt/netbox-ip-history && git status
git pull --ff-only
source /opt/netbox/venv/bin/activate
pip install -e .
python /opt/netbox/netbox/manage.py migrate
python /opt/netbox/netbox/manage.py collectstatic --no-input
systemctl restart netbox netbox-rq

# Disable (non-destructive)
# remove "netbox_ip_history" from PLUGINS, then:
systemctl restart netbox netbox-rq

# Uninstall
source /opt/netbox/venv/bin/activate
pip uninstall netbox-ip-history
systemctl restart netbox netbox-rq

# Verification
python /opt/netbox/netbox/manage.py check
python /opt/netbox/netbox/manage.py showmigrations netbox_ip_history
```
