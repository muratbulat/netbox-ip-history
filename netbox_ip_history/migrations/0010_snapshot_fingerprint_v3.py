from django.db import migrations, models

from netbox_ip_history.migrations._fingerprints import NATIVE_PREFIX, fingerprint_v3, recompute

# Column names any importer has read a change time from, as of this migration (frozen).
TIMESTAMP_COLUMNS = frozenset({
    "timestamp", "time", "date", "datetime", "last_updated", "modified", "created", "cdate", "editdate",
})


def _clean(key):
    return str(key).strip().lower().replace(" ", "_").replace("-", "_")


def _had_timestamp(event):
    raw = event.raw_data if isinstance(event.raw_data, dict) else {}
    columns = set(TIMESTAMP_COLUMNS)
    mapped = (event.source.field_mapping or {}).get("timestamp") if isinstance(event.source.field_mapping, dict) else None
    if mapped:
        columns.add(_clean(mapped))
    return any(_clean(k) in columns and str(v or "").strip() for k, v in raw.items())


def forwards(apps, schema_editor):
    HistoricalIPEvent = apps.get_model("netbox_ip_history", "HistoricalIPEvent")
    imported = (
        HistoricalIPEvent.objects.exclude(source__source_type="netbox")
        .exclude(fingerprint__startswith=NATIVE_PREFIX)
        .select_related("source")
    )
    snapshots, infoblox = [], []
    for event in imported.iterator(chunk_size=2000):
        if event.source.source_type == "infoblox":
            kind = (event.raw_data or {}).get("object") or event.source_event_type
            event.source_record_id = f"{kind}:{event.ip_address}:{event.hostname}"
            infoblox.append(event)
            snapshots.append(event.pk)
        elif not _had_timestamp(event):
            snapshots.append(event.pk)
    HistoricalIPEvent.objects.bulk_update(infoblox, ["source_record_id"], batch_size=2000)
    for start in range(0, len(snapshots), 2000):
        HistoricalIPEvent.objects.filter(pk__in=snapshots[start:start + 2000]).update(snapshot=True)
    recompute(apps, fingerprint_v3)


class Migration(migrations.Migration):
    """
    Undated rows (snapshots) are identified without their import-time timestamp, and Infoblox
    record IDs no longer include CSV line numbers, so re-importing a snapshot is idempotent.
    """

    dependencies = [("netbox_ip_history", "0009_fingerprint_v2")]

    operations = [
        migrations.AddField(
            model_name="historicalipevent",
            name="snapshot",
            field=models.BooleanField(default=False),
        ),
        migrations.RunPython(forwards, migrations.RunPython.noop),
    ]
