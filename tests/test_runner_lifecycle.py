from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from patchharbor.runner_lifecycle import (
    DEFAULT_DONE_DIRNAME,
    DEFAULT_FAILED_DIRNAME,
    DEFAULT_PATCH_SCRIPT_PATTERN,
    PatchScriptCandidate,
    RunnerLifecycleError,
    RunnerLifecyclePlan,
    destination_exists,
    discover_patch_scripts,
    lifecycle_directories,
    plan_download_lifecycle,
    plan_patch_script_lifecycle,
    select_latest_patch_script,
)


class PatchHarborRunnerLifecycleTests(unittest.TestCase):
    def test_patch_script_candidate_from_path_reads_file_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "patch.sh"
            path.write_text("echo ok\n", encoding="utf-8")
            os.utime(path, (100.0, 100.0))
            candidate = PatchScriptCandidate.from_path(path)

        self.assertEqual(candidate.path, path)
        self.assertEqual(candidate.name, "patch.sh")
        self.assertEqual(candidate.modified_time, 100.0)
        self.assertGreater(candidate.size_bytes, 0)
        self.assertEqual(candidate.age_seconds(now=105), 5.0)
        self.assertEqual(candidate.to_mapping()["path"], str(path))

    def test_patch_script_candidate_rejects_invalid_values(self) -> None:
        with self.assertRaises(RunnerLifecycleError):
            PatchScriptCandidate("", 1.0, 0)  # type: ignore[arg-type]
        with self.assertRaises(RunnerLifecycleError):
            PatchScriptCandidate(Path("patch.sh"), True, 0)  # type: ignore[arg-type]
        with self.assertRaises(RunnerLifecycleError):
            PatchScriptCandidate(Path("patch.sh"), 1.0, -1)

    def test_patch_script_candidate_from_path_rejects_missing_or_directory(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(RunnerLifecycleError):
                PatchScriptCandidate.from_path(Path(tmp) / "missing.sh")
            with self.assertRaises(RunnerLifecycleError):
                PatchScriptCandidate.from_path(Path(tmp))

    def test_discover_patch_scripts_sorts_newest_first(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            older = root / "older.sh"
            newer = root / "newer.sh"
            ignored = root / "notes.txt"
            older.write_text("old\n", encoding="utf-8")
            newer.write_text("new\n", encoding="utf-8")
            ignored.write_text("ignore\n", encoding="utf-8")
            os.utime(older, (100.0, 100.0))
            os.utime(newer, (200.0, 200.0))

            candidates = discover_patch_scripts(root)

        self.assertEqual([candidate.name for candidate in candidates], ["newer.sh", "older.sh"])

    def test_discover_patch_scripts_ignores_hidden_by_default(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            visible = root / "visible.sh"
            hidden = root / ".hidden.sh"
            visible.write_text("visible\n", encoding="utf-8")
            hidden.write_text("hidden\n", encoding="utf-8")

            default_candidates = discover_patch_scripts(root)
            all_candidates = discover_patch_scripts(root, include_hidden=True)

        self.assertEqual([candidate.name for candidate in default_candidates], ["visible.sh"])
        self.assertEqual({candidate.name for candidate in all_candidates}, {"visible.sh", ".hidden.sh"})

    def test_discover_patch_scripts_supports_recursive_search(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            nested_dir = root / "nested"
            nested_dir.mkdir()
            top = root / "top.sh"
            nested = nested_dir / "nested.sh"
            top.write_text("top\n", encoding="utf-8")
            nested.write_text("nested\n", encoding="utf-8")

            flat = discover_patch_scripts(root)
            recursive = discover_patch_scripts(root, recursive=True)

        self.assertEqual([candidate.name for candidate in flat], ["top.sh"])
        self.assertEqual({candidate.name for candidate in recursive}, {"top.sh", "nested.sh"})

    def test_discover_patch_scripts_validates_directory_and_options(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            file_path = root / "file.txt"
            file_path.write_text("x\n", encoding="utf-8")
            with self.assertRaises(RunnerLifecycleError):
                discover_patch_scripts(root / "missing")
            with self.assertRaises(RunnerLifecycleError):
                discover_patch_scripts(file_path)
            with self.assertRaises(RunnerLifecycleError):
                discover_patch_scripts(root, pattern="")
            with self.assertRaises(RunnerLifecycleError):
                discover_patch_scripts(root, recursive="yes")  # type: ignore[arg-type]
            with self.assertRaises(RunnerLifecycleError):
                discover_patch_scripts(root, include_hidden="yes")  # type: ignore[arg-type]

    def test_select_latest_patch_script_returns_newest_or_none(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.assertIsNone(select_latest_patch_script(root))
            older = root / "older.sh"
            newer = root / "newer.sh"
            older.write_text("old\n", encoding="utf-8")
            newer.write_text("new\n", encoding="utf-8")
            os.utime(older, (100.0, 100.0))
            os.utime(newer, (200.0, 200.0))
            latest = select_latest_patch_script(root)

        self.assertIsNotNone(latest)
        assert latest is not None
        self.assertEqual(latest.name, "newer.sh")

    def test_lifecycle_directories_uses_default_names_without_creating_directories(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            dirs = lifecycle_directories(root)

        self.assertEqual(dirs["downloads"], root)
        self.assertEqual(dirs["done"], root / DEFAULT_DONE_DIRNAME)
        self.assertEqual(dirs["failed"], root / DEFAULT_FAILED_DIRNAME)
        self.assertFalse((root / DEFAULT_DONE_DIRNAME).exists())
        self.assertFalse((root / DEFAULT_FAILED_DIRNAME).exists())

    def test_plan_patch_script_lifecycle_plans_success_and_failure_destinations(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            script = root / "patch.sh"
            done = root / "done"
            failed = root / "failed"
            log = root / "patch.log"
            plan = plan_patch_script_lifecycle(script, done_directory=done, failed_directory=failed, log_path=log)

        self.assertEqual(plan.script_path, script)
        self.assertEqual(plan.success_destination, done / "patch.sh")
        self.assertEqual(plan.failure_destination, failed / "patch.sh")
        self.assertEqual(plan.log_path, log)
        self.assertEqual(plan.destination_for_status("passed"), done / "patch.sh")
        self.assertEqual(plan.destination_for_status("failed"), failed / "patch.sh")

    def test_plan_download_lifecycle_uses_download_directory_names(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plan = plan_download_lifecycle(root, "patch.sh", log_path=root / "patch.log")

        self.assertEqual(plan.script_path, root / "patch.sh")
        self.assertEqual(plan.success_destination, root / "done" / "patch.sh")
        self.assertEqual(plan.failure_destination, root / "failed" / "patch.sh")
        self.assertEqual(plan.log_path, root / "patch.log")

    def test_runner_lifecycle_plan_render_and_mapping_are_stable(self) -> None:
        plan = RunnerLifecyclePlan(
            script_path=Path("downloads/patch.sh"),
            success_destination=Path("downloads/done/patch.sh"),
            failure_destination=Path("downloads/failed/patch.sh"),
            log_path=Path("downloads/patch.log"),
        )
        self.assertEqual(plan.to_mapping()["script_path"], "downloads/patch.sh")
        self.assertIn("success_destination: downloads/done/patch.sh", plan.render_summary())

    def test_runner_lifecycle_plan_rejects_invalid_destinations(self) -> None:
        with self.assertRaises(RunnerLifecycleError):
            RunnerLifecyclePlan("patch.sh", "done/patch.sh", "done/patch.sh")
        with self.assertRaises(RunnerLifecycleError):
            RunnerLifecyclePlan("patch.sh", "patch.sh", "failed/patch.sh")
        with self.assertRaises(RunnerLifecycleError):
            RunnerLifecyclePlan("patch.sh", "done/patch.sh", "patch.sh")
        with self.assertRaises(RunnerLifecycleError):
            RunnerLifecyclePlan("patch.sh", "done/patch.sh", "failed/patch.sh").destination_for_status("running")

    def test_destination_exists_reports_planned_destination_collisions_without_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            done = root / "done"
            failed = root / "failed"
            done.mkdir()
            failed.mkdir()
            script = root / "patch.sh"
            script.write_text("echo ok\n", encoding="utf-8")
            (done / "patch.sh").write_text("already done\n", encoding="utf-8")
            plan = plan_patch_script_lifecycle(script, done_directory=done, failed_directory=failed)

            status = destination_exists(plan)

        self.assertTrue(status["success_destination"])
        self.assertFalse(status["failure_destination"])
        self.assertFalse(status["log_path"])
        with self.assertRaises(RunnerLifecycleError):
            destination_exists("not-a-plan")  # type: ignore[arg-type]

    def test_public_constants_are_stable(self) -> None:
        self.assertEqual(DEFAULT_PATCH_SCRIPT_PATTERN, "*.sh")
        self.assertEqual(DEFAULT_DONE_DIRNAME, "done")
        self.assertEqual(DEFAULT_FAILED_DIRNAME, "failed")

    def test_runner_lifecycle_files_do_not_store_local_private_values(self) -> None:
        root = Path(__file__).resolve().parents[1]
        checked = [
            root / "src/patchharbor/runner_lifecycle.py",
            root / "tests/test_runner_lifecycle.py",
        ]
        text = "\n".join(path.read_text(encoding="utf-8") for path in checked)
        forbidden = [
            "/home/" + "exampleuser",
            "user" + "@",
            "example.user" + "@" + "example.invalid",
            "Example" + "Laptop",
            "~/" + "Projects",
            chr(96) * 3,
        ]
        for value in forbidden:
            with self.subTest(value=value):
                self.assertNotIn(value, text)
