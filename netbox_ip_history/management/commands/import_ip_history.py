import hashlib
from io import BytesIO

from django.core.management.base import BaseCommand, CommandError

from ...importers import importer_for
from ...models import ImportJob, ImportSource
from ...services.import_service import run_import


class Command(BaseCommand):
    help = "Import external IP history using the same service as the web workflow."

    def add_arguments(self, parser):
        parser.add_argument("--source", required=True)
        parser.add_argument("--file", required=True)
        parser.add_argument("--history-only", action="store_true")
        parser.add_argument("--dry-run", action="store_true")
        parser.add_argument("--format", choices=("csv", "json"))

    def handle(self, *args, **options):
        source = ImportSource.objects.filter(slug=options["source"], enabled=True).first()
        if not source:
            raise CommandError("Enabled import source was not found")
        try:
            data = open(options["file"], "rb").read()
        except OSError as exc:
            raise CommandError(str(exc)) from exc
        fmt = options["format"] or ("json" if source.source_type in ("phpipam", "generic_json") else "csv")
        importer_class = importer_for(source.source_type)
        if not importer_class:
            raise CommandError("No adapter is registered for this source type")
        job = ImportJob.objects.create(source=source, filename=options["file"], file_hash=hashlib.sha256(data).hexdigest(), file_size=len(data), dry_run=options["dry_run"], import_mode="history_only")
        importer = importer_class(source, BytesIO(data), format=fmt) if source.source_type in ("gestioip", "phpipam") else importer_class(source, BytesIO(data))
        result = run_import(job, importer)
        self.stdout.write(self.style.SUCCESS(f"{result.status}: {result.total_records} records, {result.created_records} created, {result.error_records} errors"))