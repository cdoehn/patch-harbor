from __future__ import annotations

from pathlib import Path
import tempfile
import unittest
import zipfile

from patchharbor.download_plan import (
    DEFAULT_PHASE_ORDER,
    DEFAULT_ZIP_EXTRACT_PREFIX,
    DownloadLifecyclePlan,
    DownloadPlanError,
    create_lifecycle_plan,
    create_lifecycle_plan_for_selection,
)
from patchharbor.download_selection import select_download_artifact


class DownloadLifecyclePlanTests(unittest.TestCase):
    def test_script_selection_plan_uses_script_as_execution_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            downloads = Path(tmp) / "Downloads"
            downloads.mkdir()
            script = downloads / "example_patch.sh"
            script.write_text("#!/usr/bin/env bash\necho ok\n", encoding="utf-8")

            selection = select_download_artifact(download_directory=downloads)
            plan = create_lifecycle_plan_for_selection(selection, run_timestamp="20260710_010203")

            self.assertIsInstance(plan, DownloadLifecyclePlan)
            self.assertTrue(plan.is_script)
            self.assertFalse(plan.is_archive)
            self.assertEqual(plan.download_directory, downloads)
            self.assertEqual(plan.lifecycle_input_path, script)
            self.assertEqual(plan.execution_script_path, script)
            self.assertIsNone(plan.extraction_directory)
            self.assertEqual(plan.cleanup_paths, ())
            self.assertEqual(plan.done_directory, downloads / "done")
            self.assertEqual(plan.failed_directory, downloads / "failed")
            self.assertEqual(plan.success_destination, downloads / "done" / "example_patch.sh")
            self.assertEqual(plan.failure_destination, downloads / "failed" / "example_patch.sh")
            self.assertEqual(plan.ledger_file, downloads / "done" / ".applied_patch_hashes.tsv")
            self.assertEqual(plan.log_file, downloads / "example_patch_20260710_010203.log")
            self.assertEqual(plan.phase_order, DEFAULT_PHASE_ORDER)

    def test_archive_selection_plan_uses_extracted_script_but_moves_original_archive(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            downloads = Path(tmp) / "Downloads"
            downloads.mkdir()
            archive = downloads / "example_archive.zip"
            with zipfile.ZipFile(archive, "w") as zipped:
                zipped.writestr("nested/example_patch.sh", "#!/usr/bin/env bash\necho ok\n")

            plan = create_lifecycle_plan(download_directory=downloads, run_timestamp="20260710_010204")

            self.assertTrue(plan.is_archive)
            self.assertFalse(plan.is_script)
            self.assertEqual(plan.lifecycle_input_path, archive)
            self.assertEqual(plan.extraction_directory, downloads / f"{DEFAULT_ZIP_EXTRACT_PREFIX}example_archive")
            self.assertEqual(plan.execution_script_path, plan.extraction_directory / "nested/example_patch.sh")
            self.assertEqual(plan.cleanup_paths, (plan.extraction_directory,))
            self.assertEqual(plan.success_destination, downloads / "done" / "example_archive.zip")
            self.assertEqual(plan.failure_destination, downloads / "failed" / "example_archive.zip")
            self.assertEqual(plan.log_file, downloads / "example_archive_20260710_010204.log")

    def test_explicit_path_without_download_directory_uses_artifact_parent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            downloads = Path(tmp) / "Downloads"
            downloads.mkdir()
            script = downloads / "explicit_patch.sh"
            script.write_text("#!/usr/bin/env bash\necho explicit\n", encoding="utf-8")

            plan = create_lifecycle_plan(explicit_path=script, run_timestamp="20260710_010205")

            self.assertEqual(plan.download_directory, downloads)
            self.assertEqual(plan.selection.selection_source, "explicit")
            self.assertEqual(plan.execution_script_path, script)
            self.assertEqual(plan.success_destination, downloads / "done" / "explicit_patch.sh")

    def test_explicit_path_with_download_directory_uses_given_lifecycle_directory(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            downloads = root / "Downloads"
            other = root / "Other"
            downloads.mkdir()
            other.mkdir()
            script = other / "explicit_patch.sh"
            script.write_text("#!/usr/bin/env bash\necho explicit\n", encoding="utf-8")

            plan = create_lifecycle_plan(
                download_directory=downloads,
                explicit_path=script,
                run_timestamp="20260710_010206",
            )

            self.assertEqual(plan.download_directory, downloads)
            self.assertEqual(plan.lifecycle_input_path, script)
            self.assertEqual(plan.execution_script_path, script)
            self.assertEqual(plan.success_destination, downloads / "done" / "explicit_patch.sh")
            self.assertEqual(plan.failure_destination, downloads / "failed" / "explicit_patch.sh")

    def test_plan_to_mapping_is_serializable_contract(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            downloads = Path(tmp) / "Downloads"
            downloads.mkdir()
            script = downloads / "map_patch.sh"
            script.write_text("#!/usr/bin/env bash\necho map\n", encoding="utf-8")

            plan = create_lifecycle_plan(download_directory=downloads, run_timestamp="20260710_010207")
            mapping = plan.to_mapping()

            self.assertEqual(mapping["download_directory"], str(downloads))
            self.assertEqual(mapping["done_directory"], str(downloads / "done"))
            self.assertEqual(mapping["failed_directory"], str(downloads / "failed"))
            self.assertEqual(mapping["log_file"], str(downloads / "map_patch_20260710_010207.log"))
            self.assertEqual(mapping["ledger_file"], str(downloads / "done" / ".applied_patch_hashes.tsv"))
            self.assertEqual(mapping["execution_script_path"], str(script))
            self.assertEqual(mapping["lifecycle_input_path"], str(script))
            self.assertEqual(mapping["success_destination"], str(downloads / "done" / "map_patch.sh"))
            self.assertEqual(mapping["failure_destination"], str(downloads / "failed" / "map_patch.sh"))
            self.assertEqual(mapping["phase_order"], list(DEFAULT_PHASE_ORDER))
            self.assertEqual(mapping["selection"]["selection_source"], "latest")

    def test_create_lifecycle_plan_rejects_invalid_timestamp(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            downloads = Path(tmp) / "Downloads"
            downloads.mkdir()
            script = downloads / "bad_timestamp_patch.sh"
            script.write_text("#!/usr/bin/env bash\necho bad\n", encoding="utf-8")

            with self.assertRaisesRegex(DownloadPlanError, "YYYYMMDD_HHMMSS"):
                create_lifecycle_plan(download_directory=downloads, run_timestamp="2026-07-10")

    def test_plan_api_does_not_create_lifecycle_directories_or_logs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            downloads = Path(tmp) / "Downloads"
            downloads.mkdir()
            script = downloads / "dry_plan_patch.sh"
            script.write_text("#!/usr/bin/env bash\necho dry\n", encoding="utf-8")

            plan = create_lifecycle_plan(download_directory=downloads, run_timestamp="20260710_010208")

            self.assertFalse(plan.done_directory.exists())
            self.assertFalse(plan.failed_directory.exists())
            self.assertFalse(plan.log_file.exists())
            self.assertFalse(plan.ledger_file.exists())
            self.assertTrue(script.exists())

    def test_download_plan_tests_do_not_store_private_local_values(self) -> None:
        text = Path(__file__).read_text(encoding="utf-8")
        forbidden = [
            "/home/" + "exampleuser",
            "user" + "@",
            "example.user" + "@" + "example.invalid",
            "Example" + "Laptop",
            "~/" + "Projects",
            chr(96) * 3,
        ]
        for value in forbidden:
            self.assertNotIn(value, text)


if __name__ == "__main__":
    unittest.main()
