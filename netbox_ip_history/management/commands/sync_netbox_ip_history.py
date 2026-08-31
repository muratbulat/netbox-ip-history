from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Synchronize historical native NetBox IP changes from core.ObjectChange into HistoricalIPEvent."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Scan ObjectChange records without saving changes to the database.",
        )
        parser.add_argument(
            "--flush",
            action="store_true",
            help="Delete all previously synchronized native NetBox HistoricalIPEvent records before re-syncing.",
        )

    def handle(self, *args, **options):
        dry_run = options.get("dry_run", False)
        flush = options.get("flush", False)

        try:
            from core.models import ObjectChange
        except ImportError:
            self.stderr.write(self.style.ERROR("core.ObjectChange model is not available."))
            return

        if flush and not dry_run:
            try:
                from netbox_ip_history.models import HistoricalIPEvent
                deleted_count, _ = HistoricalIPEvent.objects.filter(source__slug="netbox").delete()
                self.stdout.write(self.style.WARNING(f"Flushed {deleted_count} existing native NetBox history record(s)."))
            except Exception as e:
                self.stderr.write(f"Error flushing native events: {e}")

        from netbox_ip_history.signals import record_object_change_as_event

        self.stdout.write("Scanning native NetBox ObjectChange IP records...")
        changes = ObjectChange.objects.filter(changed_object_type__model="ipaddress").order_by("time")
        total = changes.count()

        if total == 0:
            self.stdout.write(self.style.WARNING("No native IP ObjectChange records found in NetBox."))
            return

        self.stdout.write(f"Found {total} native IP change record(s). Synchronizing...")

        synced_count = 0
        error_count = 0

        for change in changes.iterator(chunk_size=1000):
            try:
                if not dry_run:
                    event = record_object_change_as_event(change)
                    if event:
                        synced_count += 1
                else:
                    synced_count += 1
            except Exception as e:
                error_count += 1
                self.stderr.write(f"Error processing ObjectChange pk={change.pk}: {e}")

        prefix = "[DRY RUN] " if dry_run else ""
        self.stdout.write(
            self.style.SUCCESS(
                f"{prefix}Successfully synchronized {synced_count} native NetBox IP history event(s) (Errors: {error_count})."
            )
        )
        if not dry_run:
            self.stdout.write(
                self.style.NOTICE(
                    "To update the NetBox global search index, run:\n"
                    "  python manage.py reindex netbox_ip_history"
                )
            )
