from __future__ import annotations

from pathlib import Path
import tempfile
import unittest
import zipfile

from patchharbor.download_plan import (
    DEFAULT_PHASE_ORDER,
    DEFAULT_ZIP_EXTRACT_PREFIX,
    DownloadLifecyclePlan,
    create_lifecycle_plan,
)
from patchharbor.download_selection import DownloadArtifactSelection, select_download_artifact


ROOT = Path(__file__).resolve().parents[1]
ACCEPTANCE = ROOT / "docs/download-runner-lifecycle-plan-acceptance.md"


class DownloadRunnerLifecyclePlanAcceptanceTests(unittest.TestCase):
    def read_acceptance(self) -> str:
        return ACCEPTANCE.read_text(encoding="utf-8")

    def test_acceptance_document_exists_and_references_10c_steps(self) -> None:
        text = self.read_acceptance()
        required = [
            "PATCHHARBOR.10c4",
            "Download Runner Lifecycle Plan Acceptance",
            "PATCHHARBOR.10c1",
            "PATCHHARBOR.10c2",
            "PATCHHARBOR.10c3",
            "src/patchharbor/download_selection.py",
            "src/patchharbor/download_plan.py",
            "tests/test_download_selection.py",
            "tests/test_download_plan.py",
            "tests/test_download_plan_acceptance.py",
        ]
        missing = [marker for marker in required if marker not in text]
        self.assertEqual(missing, [])

    def test_acceptance_records_non_executing_planning_contract(self) -> None:
        text = self.read_acceptance()
        required = [
            "selects a script or archive artifact without executing it",
            "builds a non-executing lifecycle plan from selection",
            "script plans execute the selected script directly",
            "archive plans execute the embedded script after extraction",
            "archive plans keep the original archive as the lifecycle input artifact",
            "success destinations point into `done`",
            "failure destinations point into `failed`",
            "log files stay in the download directory",
            "applied ledger path is `.applied_patch_hashes.tsv` inside `done`",
            "exposes the nested selection mapping from `DownloadArtifactSelection.to_mapping()`",
            "cleanup paths are planned, but cleanup is not executed",
        ]
        missing = [marker for marker in required if marker not in text]
        self.assertEqual(missing, [])

    def test_acceptance_records_10c_non_goals(self) -> None:
        text = self.read_acceptance()
        non_goals = [
            "execute patchscripts",
            "validate metadata",
            "perform repeat checks",
            "perform freshness checks",
            "run Bash syntax checks",
            "move files to `done` or `failed`",
            "write the applied ledger",
            "change aliases",
            "switch `c`",
            "replace the RepoDossier source runner",
            "mutate the RepoDossier source repository",
        ]
        missing = [marker for marker in non_goals if marker not in text]
        self.assertEqual(missing, [])

    def test_script_plan_acceptance_contract_matches_selection_api(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            downloads = Path(tmp) / "Downloads"
            downloads.mkdir()
            script = downloads / "acceptance_patch.sh"
            script.write_text("#!/usr/bin/env bash\necho acceptance\n", encoding="utf-8")

            selection = select_download_artifact(download_directory=downloads)
            plan = create_lifecycle_plan(download_directory=downloads, run_timestamp="20260710_010203")

            self.assertIsInstance(selection, DownloadArtifactSelection)
            self.assertIsInstance(plan, DownloadLifecyclePlan)
            self.assertTrue(plan.is_script)
            self.assertFalse(plan.is_archive)
            self.assertEqual(plan.artifact_path, script)
            self.assertEqual(plan.execution_script_path, script)
            self.assertEqual(plan.lifecycle_input_path, script)
            self.assertEqual(plan.success_destination, downloads / "done" / "acceptance_patch.sh")
            self.assertEqual(plan.failure_destination, downloads / "failed" / "acceptance_patch.sh")
            self.assertEqual(plan.log_file, downloads / "acceptance_patch_20260710_010203.log")
            self.assertEqual(plan.ledger_file, downloads / "done" / ".applied_patch_hashes.tsv")
            self.assertEqual(plan.phase_order, DEFAULT_PHASE_ORDER)
            self.assertEqual(plan.cleanup_paths, ())

    def test_archive_plan_acceptance_contract_keeps_original_archive_as_lifecycle_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            downloads = Path(tmp) / "Downloads"
            downloads.mkdir()
            archive = downloads / "acceptance_archive.zip"
            with zipfile.ZipFile(archive, "w") as zipped:
                zipped.writestr("nested/acceptance_patch.sh", "#!/usr/bin/env bash\necho acceptance\n")

            plan = create_lifecycle_plan(download_directory=downloads, run_timestamp="20260710_010204")

            self.assertTrue(plan.is_archive)
            self.assertFalse(plan.is_script)
            self.assertEqual(plan.artifact_path, archive)
            self.assertEqual(plan.lifecycle_input_path, archive)
            self.assertEqual(plan.extraction_directory, downloads / f"{DEFAULT_ZIP_EXTRACT_PREFIX}acceptance_archive")
            self.assertEqual(plan.execution_script_path, plan.extraction_directory / "nested/acceptance_patch.sh")
            self.assertEqual(plan.cleanup_paths, (plan.extraction_directory,))
            self.assertEqual(plan.success_destination, downloads / "done" / "acceptance_archive.zip")
            self.assertEqual(plan.failure_destination, downloads / "failed" / "acceptance_archive.zip")
            self.assertEqual(plan.log_file, downloads / "acceptance_archive_20260710_010204.log")

    def test_plan_to_mapping_exposes_compatibility_fields(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            downloads = Path(tmp) / "Downloads"
            downloads.mkdir()
            script = downloads / "mapping_patch.sh"
            script.write_text("#!/usr/bin/env bash\necho mapping\n", encoding="utf-8")

            plan = create_lifecycle_plan(download_directory=downloads, run_timestamp="20260710_010205")
            mapping = plan.to_mapping()

            expected_keys = {
                "selection",
                "download_directory",
                "done_directory",
                "failed_directory",
                "log_file",
                "ledger_file",
                "execution_script_path",
                "lifecycle_input_path",
                "success_destination",
                "failure_destination",
                "cleanup_paths",
                "phase_order",
            }
            self.assertEqual(set(mapping), expected_keys)
            self.assertEqual(mapping["phase_order"], list(DEFAULT_PHASE_ORDER))
            self.assertEqual(mapping["cleanup_paths"], [])
            self.assertEqual(mapping["selection"]["selection_source"], "latest")
            self.assertEqual(mapping["selection"]["download_directory"], str(downloads))
            self.assertEqual(mapping["selection"]["candidate"]["artifact_type"], "script")
            self.assertEqual(mapping["selection"]["candidate"]["path"], str(script))

    def test_acceptance_files_do_not_store_private_local_values(self) -> None:
        checked = [
            ACCEPTANCE,
            ROOT / "tests/test_download_plan_acceptance.py",
        ]
        text = "\n".join(path.read_text(encoding="utf-8") for path in checked)
        forbidden = [
            "/home/" + "christian",
            "christian" + "@",
            "christian.doehn" + "@" + "gmail.com",
            "Think" + "Pad",
            "~/" + "Projekte",
            chr(96) * 3,
        ]
        for value in forbidden:
            self.assertNotIn(value, text)


if __name__ == "__main__":
    unittest.main()
