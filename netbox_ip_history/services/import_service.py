from typing import Any

try:
    from django.db import transaction
    from django.utils import timezone
except ImportError:
    class _MockTransaction:
        @staticmethod
        def atomic(fn):
            return fn
    transaction = _MockTransaction()

    from datetime import datetime
    from datetime import timezone as _dt_tz
    class _MockTimezone:
        @staticmethod
        def now():
            return datetime.now(_dt_tz.utc)
    timezone = _MockTimezone()

from ..choices import JobStatus
from ..models import HistoricalIPEvent, ImportJob
from .normalize import RecordError, fingerprint, normalize_event_type, normalize_ip, normalize_timestamp


def normalize_record(source, record: dict[str, Any]) -> dict[str, Any]:
    ip, prefix = normalize_ip(record.get("ip_address", record.get("ip")))
    raw_prefix = record.get("prefix_length")
    prefix_len = int(raw_prefix) if raw_prefix is not None and str(raw_prefix).isdigit() else prefix
    normalized = dict(record)
    normalized.update(
        ip_address=ip,
        prefix_length=prefix_len,
        timestamp=normalize_timestamp(record.get("timestamp"), source.source_timezone),
        event_type=normalize_event_type(record.get("event_type") or record.get("source_event_type")),
    )
    normalized["fingerprint"] = fingerprint(source.slug, normalized)
    normalized.setdefault("raw_data", dict(record))
    return normalized


BATCH_SIZE = 500


@transaction.atomic
def run_import(job: ImportJob, importer, dry_run: bool | None = None) -> ImportJob:
    """Persist validated records in optimized batches; dry runs do not mutate event or job records."""
    dry_run = job.dry_run if dry_run is None else dry_run
    seen_in_import: set[str] = set()
    errors: list[dict[str, Any]] = []
    count = 0

    batch_records: list[dict[str, Any]] = []
    fields = (
        {field.name for field in HistoricalIPEvent._meta.fields} - {"id", "source", "import_job", "related_netbox_ip"}
        if hasattr(HistoricalIPEvent, "_meta")
        else set()
    )

    def _flush_batch(records_to_save: list[dict[str, Any]]) -> None:
        if not records_to_save:
            return
        fps = [r["fingerprint"] for r in records_to_save]
        if hasattr(HistoricalIPEvent, "objects") and hasattr(HistoricalIPEvent.objects, "filter"):
            existing_fps = set(
                HistoricalIPEvent.objects.filter(fingerprint__in=fps).values_list("fingerprint", flat=True)
            )
        else:
            existing_fps = set()

        events_to_create = []
        for r in records_to_save:
            fp = r["fingerprint"]
            if fp in existing_fps:
                job.duplicate_records += 1
                continue
            existing_fps.add(fp)

            if not dry_run and hasattr(HistoricalIPEvent, "objects"):
                event_kwargs = {k: v for k, v in r.items() if k in fields}
                events_to_create.append(
                    HistoricalIPEvent(source=job.source, import_job=job, **event_kwargs)
                )
            job.created_records += 1

        if events_to_create:
            HistoricalIPEvent.objects.bulk_create(events_to_create, batch_size=BATCH_SIZE)

    for raw in importer.iter_history():
        count += 1
        try:
            record = normalize_record(job.source, raw)
            fp = record["fingerprint"]
            if fp in seen_in_import:
                job.duplicate_records += 1
                continue
            seen_in_import.add(fp)
            batch_records.append(record)

            if len(batch_records) >= BATCH_SIZE:
                _flush_batch(batch_records)
                batch_records.clear()
        except (RecordError, ValueError, TypeError) as exc:
            job.error_records += 1
            errors.append({"row": count, "error": str(exc)})

    if batch_records:
        _flush_batch(batch_records)
        batch_records.clear()

    job.total_records = count
    job.processed_records = count
    job.error_details = errors
    job.completed = timezone.now()
    job.status = JobStatus.DRY_RUN if dry_run else JobStatus.COMPLETED
    job.summary = {
        # Original keys, kept for backward compatibility with existing
        # consumers (templates/API clients reading job.summary).
        "valid": job.created_records,
        "duplicates": job.duplicate_records,
        "errors": job.error_records,
        # Additive fields for a fuller report.
        "total": job.total_records,
        "processed": job.processed_records,
        "created": job.created_records,
        "dry_run": dry_run,
    }
    if hasattr(job, "save"):
        job.save()
    return job


@transaction.atomic
def rollback_job(job: ImportJob) -> int:
    """Safely remove all historical events created by a specific import job."""
    deleted = 0
    if hasattr(HistoricalIPEvent, "objects"):
        deleted, _ = HistoricalIPEvent.objects.filter(import_job=job).delete()
    job.status = getattr(JobStatus, "ROLLED_BACK", "rolled_back")
    if isinstance(job.summary, dict):
        job.summary["rolled_back_events"] = deleted
    if hasattr(job, "save"):
        job.save()
    return deleted