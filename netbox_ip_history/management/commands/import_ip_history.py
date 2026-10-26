from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from ...models import ImportSource
from ...services.import_service import build_importer, run_import

CHUNK = 1000


class Command(BaseCommand):
    help = (
        "Import IP history from an export file (--source/--file), or backfill native NetBox history from "
        "core.ObjectChange (--native). Runs synchronously; uses the same service as the web workflow."
    )

    def add_arguments(self, parser):
        parser.add_argument("--source", help="Slug of the ImportSource to import into")
        parser.add_argument("--file", type=Path, help="Path of the export file")
        parser.add_argument("--format", choices=("csv", "json", "xml"), default="csv")
        parser.add_argument("--delimiter", default=",")
        parser.add_argument("--dry-run", action="store_true", help="Validate and count without saving")
        parser.add_argument(
            "--native", action="store_true", help="Record existing ipaddress ObjectChanges as native events"
        )

    def handle(self, *args, **options):
        if options["native"]:
            return self.backfill_native(options["dry_run"])
        if not options["source"] or not options["file"]:
            raise CommandError("--source and --file are required (or use --native)")

        source = ImportSource.objects.filter(slug=options["source"], enabled=True).first()
        if source is None:
            raise CommandError(f"No enabled import source with slug '{options['source']}'")
        try:
            data = options["file"].read_bytes()
        except OSError as exc:
            raise CommandError(str(exc)) from exc

        importer = build_importer(source, data, format=options["format"], delimiter=options["delimiter"])
        result, job = run_import(
            source, importer, dry_run=options["dry_run"], filename=options["file"].name, data=data
        )
        label = "Dry run" if job is None else f"Import job #{job.pk}"
        self.stdout.write(
            self.style.SUCCESS(
                f"{label}: {result.total} records, {result.created} new, {result.duplicates} duplicates, "
                f"{result.error_count} errors"
            )
        )
        for error in result.errors[:20]:
            self.stderr.write(f"  row {error['row']}: {error['error']}")

    def backfill_native(self, dry_run):
        from core.models import ObjectChange

        from ...signals import get_native_source, record_object_changes

        changes = ObjectChange.objects.filter(changed_object_type__model="ipaddress").select_related(
            "changed_object_type"
        ).order_by("pk")
        total = changes.count()
        if dry_run:
            self.stdout.write(f"Dry run: {total} ipaddress ObjectChange records would be recorded")
            return
        source = get_native_source()
        recorded, batch = 0, []
        for change in changes.iterator(chunk_size=CHUNK):
            batch.append(change)
            if len(batch) >= CHUNK:
                recorded += len(record_object_changes(batch, source=source))
                batch = []
        if batch:
            recorded += len(record_object_changes(batch, source=source))
        self.stdout.write(self.style.SUCCESS(f"Recorded {recorded} of {total} native IP changes"))
