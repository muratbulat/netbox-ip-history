from netbox.jobs import JobRunner

from .choices import ImportStatusChoices
from .models import ImportJob
from .services.import_service import build_importer, run_import

__all__ = ("ImportHistoryJobRunner",)


class ImportHistoryJobRunner(JobRunner):
    """Runs a queued file import for a pending ImportJob on NetBox's RQ workers."""

    class Meta:
        name = "IP history import"

    def run(self, data: bytes, format: str = "csv", delimiter: str = ",", **kwargs):
        import_job = ImportJob.objects.select_related("source").get(pk=self.job.object_id)
        if import_job.status != ImportStatusChoices.PENDING:
            self.logger.warning("Import job %s is %s, not pending; skipping", import_job.pk, import_job.status)
            return
        try:
            importer = build_importer(import_job.source, data, format=format, delimiter=delimiter)
        except Exception as exc:
            # run_import() never started: record the failure on the import job, not only on the NetBox job.
            import_job.status = ImportStatusChoices.FAILED
            import_job.error_details = [{"row": None, "error": str(exc)}]
            import_job.save(update_fields=["status", "error_details"])
            raise
        result, _ = run_import(import_job.source, importer, job=import_job, data=data, user=import_job.user)
        for warning in result.warnings:
            self.logger.warning(warning)
        self.logger.info(
            "Imported %s of %s records (%s duplicates, %s errors)",
            result.created,
            result.total,
            result.duplicates,
            result.error_count,
        )
        self.job.data = result.as_summary()
