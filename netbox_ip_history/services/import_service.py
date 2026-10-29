import hashlib
import io
from dataclasses import dataclass, field
from typing import Any

from django.db import transaction
from django.utils import timezone

from ..choices import ImportStatusChoices
from ..importers import importer_for
from ..models import HistoricalIPEvent, ImportJob, ImportSource
from .normalize import RecordError, fingerprint, normalize_event_type, normalize_ip, normalize_timestamp, normalize_vrf

__all__ = (
    "BATCH_SIZE",
    "ImportResult",
    "build_importer",
    "normalize_record",
    "rollback_job",
    "run_import",
)

BATCH_SIZE = 1000
PREVIEW_ROWS = 25
MAX_REPORTED_ERRORS = 500

_EVENT_FIELDS = frozenset(
    f.name for f in HistoricalIPEvent._meta.concrete_fields
) - {"id", "source", "import_job", "related_netbox_ip", "created", "last_updated", "custom_field_data"}
_MAX_LENGTHS = {
    f.name: f.max_length for f in HistoricalIPEvent._meta.concrete_fields if getattr(f, "max_length", None)
}


@dataclass
class ImportResult:
    """Outcome of an import; persisted onto an ImportJob for live runs, in-memory only for dry runs."""

    dry_run: bool
    total: int = 0
    created: int = 0
    duplicates: int = 0
    errors: list[dict[str, Any]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    preview: list[dict[str, Any]] = field(default_factory=list)

    @property
    def error_count(self) -> int:
        return len(self.errors)

    def as_summary(self) -> dict[str, Any]:
        return {
            "total": self.total,
            "created": self.created,
            "duplicates": self.duplicates,
            "errors": self.error_count,
            "warnings": self.warnings,
            "dry_run": self.dry_run,
        }


def normalize_record(source: ImportSource, record: dict[str, Any], default_timestamp=None) -> dict[str, Any]:
    ip, prefix = normalize_ip(record.get("ip_address", record.get("ip")))
    raw_prefix = str(record.get("prefix_length") or "").strip()
    normalized = {k: v for k, v in record.items() if k in _EVENT_FIELDS}
    for key, value in normalized.items():
        if isinstance(value, str):
            normalized[key] = value.strip()[: _MAX_LENGTHS.get(key)]
    normalized.update(
        ip_address=ip,
        prefix_length=int(raw_prefix) if raw_prefix.isdigit() and int(raw_prefix) <= 128 else prefix,
        timestamp=normalize_timestamp(record.get("timestamp"), source.source_timezone, default_timestamp),
        snapshot=not str(record.get("timestamp") or "").strip(),
        event_type=normalize_event_type(record.get("event_type") or record.get("source_event_type")),
        vrf_name=normalize_vrf(record.get("vrf_name")),
        raw_data=record.get("raw_data") or {k: v for k, v in record.items() if k != "raw_data"},
    )
    normalized["fingerprint"] = fingerprint(source.slug, normalized)
    return normalized


def _previous_import_warning(source: ImportSource, file_hash: str, exclude_pk=None) -> str | None:
    """Warn when this exact file (by SHA-256) was already imported into the same source."""
    if not file_hash:
        return None
    previous = (
        ImportJob.objects.filter(source=source, file_hash=file_hash, status=ImportStatusChoices.COMPLETED)
        .exclude(pk=exclude_pk)
        .order_by("-started")
        .first()
    )
    if previous is None:
        return None
    return (
        f"This file was already imported into {source} as import job #{previous.pk} "
        f"on {previous.started:%Y-%m-%d %H:%M}; matching records are counted as duplicates."
    )


def build_importer(source: ImportSource, data: bytes, format: str = "csv", delimiter: str = ","):
    importer_class = importer_for(source.source_type)
    return importer_class(source, io.BytesIO(data), format=format, delimiter=delimiter or ",")


def _index_for_search(instances: list[HistoricalIPEvent]) -> None:
    """bulk_create() emits no post_save, so feed NetBox's search cache once the import commits."""
    if not instances:
        return

    def cache():
        from netbox.search.backends import search_backend

        search_backend.cache(instances, remove_existing=False)

    transaction.on_commit(cache)


def _process(source: ImportSource, importer, job: ImportJob | None, result: ImportResult) -> None:
    snapshot_time = timezone.now()
    seen: set[str] = set()
    batch: list[dict[str, Any]] = []

    def flush():
        existing = set(
            HistoricalIPEvent.objects.filter(fingerprint__in=[r["fingerprint"] for r in batch]).values_list(
                "fingerprint", flat=True
            )
        )
        new = [r for r in batch if r["fingerprint"] not in existing]
        result.duplicates += len(batch) - len(new)
        result.created += len(new)
        if job is not None and new:
            events = HistoricalIPEvent.objects.bulk_create(
                [HistoricalIPEvent(source=source, import_job=job, **record) for record in new],
                batch_size=BATCH_SIZE,
            )
            _index_for_search(events)
        batch.clear()

    for row_number, raw in enumerate(importer.iter_records(), start=1):
        result.total = row_number
        try:
            record = normalize_record(source, raw, default_timestamp=snapshot_time)
        except (RecordError, ValueError, TypeError) as exc:
            if len(result.errors) < MAX_REPORTED_ERRORS:
                result.errors.append({"row": row_number, "error": str(exc)})
            continue
        if record["fingerprint"] in seen:
            result.duplicates += 1
            continue
        seen.add(record["fingerprint"])
        if len(result.preview) < PREVIEW_ROWS:
            result.preview.append(record)
        batch.append(record)
        if len(batch) >= BATCH_SIZE:
            flush()
    if batch:
        flush()


def run_import(
    source: ImportSource,
    importer,
    *,
    dry_run: bool = False,
    job: ImportJob | None = None,
    user=None,
    filename: str = "",
    data: bytes = b"",
) -> tuple[ImportResult, ImportJob | None]:
    """
    Import every record ``importer`` yields for ``source``.

    Dry runs only read the database (for duplicate detection) and return an in-memory
    result; nothing is persisted. Live runs create (or complete the given pending) ImportJob
    and insert events in batches inside a single transaction, so a failure leaves no
    partial import behind.
    """
    result = ImportResult(dry_run=dry_run)
    file_hash = (job.file_hash if job is not None else "") or (hashlib.sha256(data).hexdigest() if data else "")
    if warning := _previous_import_warning(source, file_hash, exclude_pk=job.pk if job is not None else None):
        result.warnings.append(warning)
    if dry_run:
        _process(source, importer, None, result)
        return result, None

    if job is None:
        job = ImportJob(
            source=source,
            user=user,
            filename=filename[:255],
            file_hash=file_hash,
            file_size=len(data) if data else None,
        )
    try:
        with transaction.atomic():
            job.status = ImportStatusChoices.RUNNING
            job.save()
            _process(source, importer, job, result)
            job.status = ImportStatusChoices.COMPLETED
            _finalize(job, result)
    except Exception as exc:
        job.status = ImportStatusChoices.FAILED
        result.errors.append({"row": None, "error": str(exc)})
        _finalize(job, result)
        raise
    return result, job


def _finalize(job: ImportJob, result: ImportResult) -> None:
    job.completed = timezone.now()
    job.total_records = job.processed_records = result.total
    job.created_records = result.created
    job.duplicate_records = result.duplicates
    job.error_records = result.error_count
    job.error_details = result.errors
    job.summary = result.as_summary()
    if job.pk is None or not ImportJob.objects.filter(pk=job.pk).exists():
        job.pk = None
    job.save()


@transaction.atomic
def rollback_job(job: ImportJob) -> int:
    """Delete every event created by ``job`` and mark it rolled back."""
    deleted, _ = HistoricalIPEvent.objects.filter(import_job=job).delete()
    job.status = ImportStatusChoices.ROLLED_BACK
    job.summary = {**(job.summary or {}), "rolled_back_events": deleted}
    job.save()
    return deleted
