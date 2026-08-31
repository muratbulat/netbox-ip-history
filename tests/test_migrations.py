"""
Regression tests for the migration chain's structural integrity.

Migration modules import `django.db.migrations` unconditionally (unlike the
rest of this Django-optional codebase) since they only ever run inside a
real NetBox/Django environment via manage.py — so these tests work purely
by reading migration file *source text*, not by importing them, to stay
runnable in this repo's Django-less local test suite. The real, authoritative
migration-vs-model consistency check is `manage.py makemigrations
netbox_ip_history --check --dry-run`, run in .github/workflows/netbox-matrix.yml
against a real NetBox/Postgres environment — these tests are a lightweight,
always-runnable defense-in-depth layer, not a replacement for it.
"""
import os
import re
from unittest import TestCase

import netbox_ip_history

# Resolved from the imported module's own __file__ so this test passes
# identically against the source checkout or an installed wheel (see
# .github/workflows/ci.yml's "installed-wheel-tests" job).
MIGRATIONS_DIR = os.path.join(os.path.dirname(os.path.abspath(netbox_ip_history.__file__)), "migrations")


def _migration_files():
    return sorted(
        f for f in os.listdir(MIGRATIONS_DIR)
        if re.match(r"^\d{4}_.*\.py$", f)
    )


def _read(filename):
    with open(os.path.join(MIGRATIONS_DIR, filename), encoding="utf-8") as f:
        return f.read()


class MigrationChainIntegrityTests(TestCase):
    def test_migrations_are_sequentially_numbered_with_no_gaps(self):
        files = _migration_files()
        numbers = [int(f[:4]) for f in files]
        self.assertEqual(numbers, list(range(1, len(numbers) + 1)), f"Migration files: {files}")

    def test_each_migration_depends_on_the_immediately_preceding_one(self):
        """Regression guard for model changes (Meta.ordering on all three
        models, plus the index-name drift that follows from a Django
        version's auto-generated hash changing) that were never captured in
        a migration, causing "have changes that are not yet reflected in a
        migration" on upgrade to a newer Django version. 0007 fixes this;
        this test ensures the chain stays linear and none of 0001-0006 (all
        already released) were touched to fix it."""
        files = _migration_files()
        for i in range(1, len(files)):
            content = _read(files[i])
            prev_name = files[i - 1][:-3]  # strip .py
            # Migration files mix single- and double-quote style depending
            # on whether they were auto-generated or hand-written, so match
            # either.
            pattern = r"""\(\s*['"]netbox_ip_history['"]\s*,\s*['"]""" + re.escape(prev_name) + r"""['"]\s*\)"""
            self.assertRegex(
                content, pattern,
                f"{files[i]} must declare a dependency on {prev_name}",
            )

    def test_0007_contains_only_the_expected_metadata_and_index_rename_operations(self):
        """0007_sync_model_metadata_indexes must consist of exactly 3
        AlterModelOptions + 5 RenameIndex operations and nothing else — no
        AddField/RemoveField/AlterField/CreateModel/DeleteModel/RunPython/
        RunSQL. This is a pure metadata/index-name synchronization fixing a
        release defect, not a schema or data change, and must stay that way:
        a stray AddField etc. here would mean a *different*, undocumented
        model change slipped in un-reviewed."""
        content = _read("0007_sync_model_metadata_indexes.py")

        self.assertEqual(content.count("migrations.AlterModelOptions("), 3)
        self.assertEqual(content.count("migrations.RenameIndex("), 5)

        forbidden_ops = (
            "AddField", "RemoveField", "AlterField",
            "CreateModel", "DeleteModel", "RunPython", "RunSQL",
        )
        for op in forbidden_ops:
            self.assertNotIn(
                f"migrations.{op}(", content,
                f"0007 must not contain a {op} operation",
            )

        self.assertIn("('netbox_ip_history', '0006_repair_native_events')", content)

    def test_already_released_migrations_0001_through_0006_are_unmodified(self):
        """0001-0006 were already released and must never be
        edited after the fact — only ever fixed forward with a new
        migration (0007 here). This pins their exact operation-type
        fingerprint so an accidental edit is caught even if the file's
        content otherwise still "looks right"."""
        expected_operation_counts = {
            "0001_initial.py": {"CreateModel": 3, "AddIndex": 1},
            "0002_source_profiles.py": {"AddField": 5},
            "0003_alter_historicalipevent_options_and_more.py": {"AlterField": 1, "AddIndex": 4},
            "0004_unify_gestioip_sources.py": {"RunPython": 1},
            "0005_seed_support_matrix_sources.py": {"RunPython": 1},
            "0006_repair_native_events.py": {"RunPython": 1},
        }
        for filename, expected_ops in expected_operation_counts.items():
            content = _read(filename)
            for op, count in expected_ops.items():
                self.assertEqual(
                    content.count(f"migrations.{op}("), count,
                    f"{filename} operation count for {op} changed — already-released migrations must not be edited",
                )
