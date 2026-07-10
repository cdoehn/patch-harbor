from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from patchharbor.cli import build_parser
from patchharbor.runner_core import RunnerExecutionConfig, run_patch_script
from patchharbor.runner_display import render_runner_footer, render_runner_result
from patchharbor.runner_lifecycle import plan_download_lifecycle
from patchharbor.runner_preflight import run_preflight_checks
from patchharbor.runner_status import RunnerResult, failed_phase


def metadata_lines(patch_id: str = "PATCHHARBOR.ACCEPTANCE") -> str:
    return (
        f'# patchharbor-meta: {{"type":"patch","id":"{patch_id}","title":"Acceptance","commit":"Acceptance"}}\n'
        '# patchharbor-meta: {"type":"progress","panel":"roadmap","status":"active","file":"docs/example.md","label":"Roadmap"}\n'
        '# patchharbor-meta: {"type":"progress","panel":"milestone","status":"active","file":"docs/example.md","label":"Milestone"}\n'
        '# patchharbor-meta: {"type":"display","context":2,"layout":"side-by-side","frame":false}\n'
    )


def write_script(directory: Path, command: str = 'printf "ran" > "$PATCHHARBOR_SENTINEL"\n') -> Path:
    path = directory / "patch.sh"
    path.write_text("#!/usr/bin/env bash\n" + metadata_lines() + "set -euo pipefail\n" + command, encoding="utf-8")
    return path


def run_module(args: list[str]) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    src = str(Path(__file__).resolve().parents[1] / "src")
    env["PYTHONPATH"] = src + (os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")
    return subprocess.run(
        [sys.executable, "-m", "patchharbor", *args],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
        check=False,
    )


class PatchHarborRunnerCompatibilityAcceptanceTests(unittest.TestCase):
    def test_acceptance_document_exists_and_defines_scope(self) -> None:
        root = Path(__file__).resolve().parents[1]
        path = root / "docs/runner-compatibility-acceptance.md"
        text = path.read_text(encoding="utf-8")
        self.assertIn("PatchHarbor.06 runner and compatibility acceptance", text)
        self.assertIn("Accepted scope", text)
        self.assertIn("Explicit non-goals", text)
        self.assertIn("Compatibility boundary", text)

    def test_phase_components_are_present(self) -> None:
        root = Path(__file__).resolve().parents[1]
        required = [
            "docs/runner-compatibility-migration.md",
            "docs/runner-compatibility-acceptance.md",
            "src/patchharbor/runner_status.py",
            "src/patchharbor/runner_preflight.py",
            "src/patchharbor/runner_lifecycle.py",
            "src/patchharbor/runner_core.py",
            "src/patchharbor/runner_display.py",
            "src/patchharbor/cli.py",
            "tests/test_runner_status.py",
            "tests/test_runner_preflight.py",
            "tests/test_runner_lifecycle.py",
            "tests/test_runner_core.py",
            "tests/test_runner_display.py",
            "tests/test_cli_runner.py",
        ]
        for relative in required:
            with self.subTest(relative=relative):
                self.assertTrue((root / relative).exists(), relative)

    def test_acceptance_document_records_non_goals(self) -> None:
        root = Path(__file__).resolve().parents[1]
        text = (root / "docs/runner-compatibility-acceptance.md").read_text(encoding="utf-8")
        required = [
            "automatic newest-download script selection",
            "moving successful scripts into a done directory",
            "moving failed scripts into a failed directory",
            "alias installation",
            "shell rc-file edits",
            "source-repository wrapper changes",
        ]
        for phrase in required:
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, text)

    def test_cli_exposes_explicit_run_script_without_download_lifecycle_mutation(self) -> None:
        help_text = build_parser().format_help()
        self.assertIn("run-script", help_text)
        self.assertNotIn("latest-download", help_text)
        self.assertNotIn("done directory", help_text)

    def test_runner_components_work_together_for_no_execute_flow(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            sentinel = root / "sentinel.txt"
            script = write_script(root)

            preflight = run_preflight_checks(script, max_age_seconds=20)
            self.assertTrue(preflight.ok, preflight.render_summary())

            result = run_patch_script(
                script,
                RunnerExecutionConfig(
                    environment={"PATCHHARBOR_SENTINEL": str(sentinel)},
                    max_age_seconds=20,
                    execute=False,
                ),
            )

            self.assertTrue(result.ok, result.render_summary())
            self.assertEqual(result.by_phase()["execute"].status, "skipped")
            self.assertFalse(sentinel.exists())

    def test_lifecycle_planning_does_not_mutate_directories(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plan = plan_download_lifecycle(root, "patch.sh")
            self.assertEqual(plan.script_path, root / "patch.sh")
            self.assertEqual(plan.success_destination, root / "done" / "patch.sh")
            self.assertEqual(plan.failure_destination, root / "failed" / "patch.sh")
            self.assertFalse((root / "done").exists())
            self.assertFalse((root / "failed").exists())

    def test_display_renders_effective_failed_status_for_direct_result(self) -> None:
        result = RunnerResult(phases=(failed_phase("execute", "script failed", code="execute.failed"),))
        lines = render_runner_result(result)
        footer = render_runner_footer(result, next_step="repair current patch")
        self.assertEqual(lines[0], "runner status: failed")
        self.assertIn("Current: runner status failed", footer)
        self.assertIn("Problem: script failed", footer)

    def test_module_run_script_smoke_no_execute(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            sentinel = root / "sentinel.txt"
            script = write_script(root)
            result = run_module(
                [
                    "run-script",
                    str(script),
                    "--no-execute",
                    "--max-age-seconds",
                    "20",
                    "--env",
                    f"PATCHHARBOR_SENTINEL={sentinel}",
                ]
            )

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("PatchHarbor run-script", result.stdout)
            self.assertIn("runner status: passed", result.stdout)
            self.assertIn("phase execute: skipped", result.stdout)
            self.assertFalse(sentinel.exists())

    def test_lint_script_error_output_keeps_problem_contract(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            missing = Path(tmp) / "missing.sh"
            result = run_module(["lint-script", str(missing)])

        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertIn("status: error", result.stdout)
        self.assertIn("problem:", result.stdout)

    def test_acceptance_files_do_not_store_local_private_values(self) -> None:
        root = Path(__file__).resolve().parents[1]
        checked = [
            root / "docs/runner-compatibility-acceptance.md",
            root / "tests/test_runner_compatibility_acceptance.py",
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
