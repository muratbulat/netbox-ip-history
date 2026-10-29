# NetBox IP History

[![PyPI](https://img.shields.io/pypi/v/netbox-ip-history.svg)](https://pypi.org/project/netbox-ip-history/)
[![CI](https://github.com/muratbulat/netbox-ip-history/actions/workflows/ci.yml/badge.svg)](https://github.com/muratbulat/netbox-ip-history/actions/workflows/ci.yml)
[![NetBox compatibility](https://github.com/muratbulat/netbox-ip-history/actions/workflows/netbox-matrix.yml/badge.svg)](https://github.com/muratbulat/netbox-ip-history/actions/workflows/netbox-matrix.yml)
[![License](https://img.shields.io/badge/license-Apache--2.0-blue.svg)](LICENSE)

<img src="docs/assets/icon.svg" alt="" width="96" align="right">

A NetBox plugin that answers *"who had this IP address, and when?"* It merges NetBox's own
IP address change log with history imported from other IPAM/DCIM systems into one
timeline per address, and keeps every imported record with its original source data.

- **Native capture** — every IP address create/update/delete in NetBox is recorded as a
  classified event: created, assigned, unassigned, reassigned, owner changed (device ↔ VM),
  interface/DNS/status changed, deleted.
- **Imports** — CSV, JSON / JSON Lines and flat XML, with dedicated parsers for GestióIP,
  phpIPAM, Infoblox NIOS and NetBox changelog exports. Dry-run previews, duplicate
  detection, per-row error reports, background jobs and one-click rollback.
- **Timeline & comparison** — filter by VRF (or `Global`), source, event type, owner, user
  and date; export CSV/JSON; compare the latest state of an address across sources.
- **Native NetBox integration** — models with tags, custom fields, change logging and
  journaling; standard list/detail/bulk views, global search, an *IP History* tab on every
  IP address, REST API, and object-level permissions everywhere.

## Compatibility

| Plugin | NetBox         | Python      |
|--------|----------------|-------------|
| 1.x    | 4.7.0 or later | 3.12 – 3.14 |

No maximum NetBox version is declared. Every change is tested against NetBox 4.7.0 and
4.7.3, plus an early-warning lane against NetBox's development branch
([workflow](.github/workflows/netbox-matrix.yml)). The plugin has no Python dependencies
of its own: it uses the Django, DRF and libraries that NetBox ships.

## Installation

```shell
source /opt/netbox/venv/bin/activate
pip install netbox-ip-history
echo netbox-ip-history >> /opt/netbox/local_requirements.txt
```

Enable it in `configuration.py`:

```python
PLUGINS = ["netbox_ip_history"]

PLUGINS_CONFIG = {
    "netbox_ip_history": {
        "enable_native_event_tracking": True,  # record NetBox IP changes as they happen
        "backfill_on_migrate": True,           # record existing NetBox IP history on every migrate
        "enable_global_search": True,          # index events and sources in global search
        "background_import_threshold": 5 * 1024 * 1024,  # queue uploads at/above this size
        "max_upload_size": 50 * 1024 * 1024,
    },
}
```

Then apply migrations and restart NetBox and its worker (background imports run on the
NetBox RQ worker):

```shell
cd /opt/netbox/netbox
python manage.py migrate
sudo systemctl restart netbox netbox-rq
```

`migrate` also records any IP address changes already in NetBox's change log that the plugin
hasn't seen yet (for example, history from before installation) and adds them to global
search, so no `reindex` is needed. On instances with a very large change log the first run
can take a while; set `backfill_on_migrate` to `False` and run
`python manage.py import_ip_history --native` at a convenient time instead.

## Usage

1. **IP History → Sources**: add an import source, choose its type, and set its timezone
   (applied to timestamps without an offset) and an optional field mapping such as
   `{"hostname": "Server Name"}`.
2. **IP History → Import History**: upload an export. Leave *Dry run* checked to preview
   what would be imported; uncheck it to import. Every import is an *Import Job* that can be
   rolled back.
3. **IP History → Timeline**, or the *IP History* tab on any IP address: the merged history.

The same import is available from the command line:

```shell
python manage.py import_ip_history --source lab-csv --file export.csv [--format json] [--dry-run]
```

### File format

Column names are matched case-insensitively against common aliases (`ip`, `address`,
`hostname`, `fqdn`, `mac`, `vrf`, `action`, `date`, `user`, ...). A minimal history file:

```csv
timestamp,ip,event_type,hostname,vrf,user
2026-01-05T09:00:00+00:00,192.0.2.10,created,device-01.example.com,,admin
2026-02-10T12:30:00+00:00,192.0.2.10,deleted,device-01.example.com,,admin
```

IPv4 and IPv6 addresses are canonicalized (`2001:0db8::0001` → `2001:db8::1`); rows that
can't be parsed are reported individually and never abort an import. *IP History →
Supported Formats* lists every source type and whether it has a dedicated parser.

### REST API

| Endpoint | Description |
|----------|-------------|
| `GET /api/plugins/ip-history/timeline/?ip=192.0.2.10[&vrf=Global&date_from=2026-01-01&owner=...]` | Merged timeline for one address; each entry's `kind` says whether `id` is an event or an ObjectChange |
| `GET /api/plugins/ip-history/compare/?ip=192.0.2.10` | Latest state per source |
| `/api/plugins/ip-history/events/` | Historical events (read, tag, delete) |
| `/api/plugins/ip-history/import-jobs/` | Import jobs (read, tag, delete) |
| `/api/plugins/ip-history/sources/` | Import sources (full CRUD) |

## Permissions

Nothing is visible without a permission. Viewing history requires
`netbox_ip_history.view_historicalipevent`; importing requires `add_historicalipevent` and
`add_importjob`; rolling back requires `delete_historicalipevent` and `change_importjob`.
Object-level permission constraints apply to the timeline, comparison and API. History
reconstructed live from NetBox's change log additionally requires `core.view_objectchange`.

Imports and rollbacks are all-or-nothing under object-level constraints: an import fails if
any record falls outside the user's `add_historicalipevent` constraints, and a rollback is
refused if any event of the job falls outside their `delete_historicalipevent` constraints.
Dry runs write nothing and therefore do not evaluate add constraints; the real import does.
Imports run from `manage.py import_ip_history` are not subject to object permissions.

## Security

- Report vulnerabilities privately through
  [GitHub Security Advisories](https://github.com/muratbulat/netbox-ip-history/security/advisories/new).
- Never attach real exports, database dumps, credentials or tokens to issues or pull
  requests. Use documentation addresses (`192.0.2.0/24`, `2001:db8::/32`) in examples.
- XML uploads containing DOCTYPE or ENTITY declarations are rejected.

## Development

```shell
git clone https://github.com/netbox-community/netbox.git ~/netbox   # pick a 4.7.x tag
pip install -r ~/netbox/requirements.txt -e .
export NETBOX_ROOT=~/netbox/netbox   # with configuration.py enabling the plugin
just check                           # ruff, tests (throwaway test database), migration drift
```

## License

Apache-2.0. The project icon (`docs/assets/icon.svg`) is licensed under CC BY 4.0; it is
not a NetBox or NetBox Labs logo and implies no endorsement.
