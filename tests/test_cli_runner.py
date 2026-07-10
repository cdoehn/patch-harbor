from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from patchharbor.cli import build_parser, main
from patchharbor.patch_lint_rules import RULE_GIT_NO_PAGER


def run_patchharbor(args: list[str]) -> subprocess.CompletedProcess[str]:
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


def metadata_lines(patch_id: str = "PATCHHARBOR.CLI") -> str:
    return (
        f'# patchharbor-meta: {{"type":"patch","id":"{patch_id}","title":"CLI runner","commit":"Test CLI runner"}}\n'
        '# patchharbor-meta: {"type":"progress","panel":"roadmap","status":"active","file":"docs/example.md","label":"Roadmap"}\n'
        '# patchharbor-meta: {"type":"progress","panel":"milestone","status":"active","file":"docs/example.md","label":"Milestone"}\n'
        '# patchharbor-meta: {"type":"display","context":2,"layout":"side-by-side","frame":false}\n'
    )


def script_body(command: str = 'printf "ran" > "$PATCHHARBOR_SENTINEL"\n', *, patch_id: str = "PATCHHARBOR.CLI") -> str:
    return "#!/usr/bin/env bash\n" + metadata_lines(patch_id) + "set -euo pipefail\n" + command


def write_script(directory: Path, body: str, *, name: str = "patch.sh", mtime: float | None = None) -> Path:
    path = directory / name
    path.write_text(body, encoding="utf-8")
    if mtime is not None:
        os.utime(path, (mtime, mtime))
    return path


class PatchHarborRunnerCliTests(unittest.TestCase):
    def test_parser_exposes_run_script_subcommand(self) -> None:
        help_text = build_parser().format_help()
        self.assertIn("run-script", help_text)

    def test_main_without_command_prints_help(self) -> None:
        self.assertEqual(main([]), 0)

    def test_run_script_no_execute_exits_zero_without_running_script(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            sentinel = root / "sentinel.txt"
            script = write_script(root, script_body())
            result = run_patchharbor(
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

    def test_run_script_executes_explicit_script_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            sentinel = root / "sentinel.txt"
            script = write_script(root, script_body())
            result = run_patchharbor(
                [
                    "run-script",
                    str(script),
                    "--max-age-seconds",
                    "20",
                    "--env",
                    f"PATCHHARBOR_SENTINEL={sentinel}",
                ]
            )

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("runner status: passed", result.stdout)
            self.assertIn("phase execute: passed", result.stdout)
            self.assertEqual(sentinel.read_text(encoding="utf-8"), "ran")

    def test_run_script_can_run_lint_warning_path_without_blocking_execution(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            sentinel = root / "sentinel.txt"
            script = write_script(
                root,
                script_body(
                    "print_footer() { echo done; }\n"
                    "trap print_footer EXIT\n"
                    "python3 -m compileall src tests\n"
                    "if false; then git diff; fi\n"
                    'printf "ran" > "$PATCHHARBOR_SENTINEL"\n'
                ),
            )
            result = run_patchharbor(
                [
                    "run-script",
                    str(script),
                    "--lint",
                    "--max-age-seconds",
                    "20",
                    "--env",
                    f"PATCHHARBOR_SENTINEL={sentinel}",
                ]
            )

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("phase lint: passed", result.stdout)
            self.assertIn(RULE_GIT_NO_PAGER, result.stdout)
            self.assertIn("warning/lint/patch.git_no_pager", result.stdout)
            self.assertNotIn("PH-LINT-GIT-NO-PAGER", result.stdout)
            self.assertEqual(sentinel.read_text(encoding="utf-8"), "ran")

    def test_run_script_reports_repeated_patch_id_before_execution(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            sentinel = root / "sentinel.txt"
            script = write_script(root, script_body(patch_id="PATCHHARBOR.REPEAT"))
            result = run_patchharbor(
                [
                    "run-script",
                    str(script),
                    "--successful-patch-id",
                    "PATCHHARBOR.REPEAT",
                    "--env",
                    f"PATCHHARBOR_SENTINEL={sentinel}",
                ]
            )

            self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
            self.assertIn("runner status: failed", result.stdout)
            self.assertIn("repeat.already_applied", result.stdout)
            self.assertIn("phase execute: skipped", result.stdout)
            self.assertFalse(sentinel.exists())

    def test_run_script_reports_stale_script_when_max_age_is_exceeded(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            script = write_script(root, script_body(), mtime=100.0)
            result = run_patchharbor(["run-script", str(script), "--max-age-seconds", "20"])

            self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
            self.assertIn("runner status: failed", result.stdout)
            self.assertIn("freshness.too_old", result.stdout)
            self.assertIn("phase execute: skipped", result.stdout)

    def test_run_script_reports_invalid_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            script = write_script(root, "#!/usr/bin/env bash\n# patchharbor-meta: {\"type\":\n")
            result = run_patchharbor(["run-script", str(script)])

            self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
            self.assertIn("runner status: failed", result.stdout)
            self.assertIn("metadata invalid", result.stdout)
            self.assertIn("phase execute: skipped", result.stdout)

    def test_lint_script_missing_file_keeps_problem_output_contract(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            missing = Path(tmp) / "missing.sh"
            result = run_patchharbor(["lint-script", str(missing)])

        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertIn("status: error", result.stdout)
        self.assertIn("problem:", result.stdout)

    def test_run_script_rejects_bad_env_syntax(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            script = write_script(root, script_body())
            result = run_patchharbor(["run-script", str(script), "--env", "BROKEN"])

            self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
            self.assertIn("status: error", result.stdout)
            self.assertIn("KEY=VALUE", result.stdout)

    def test_main_run_script_accepts_file_directly(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            script = write_script(root, script_body())
            self.assertEqual(main(["run-script", str(script), "--no-execute"]), 0)

    def test_module_help_includes_run_script(self) -> None:
        result = run_patchharbor(["--help"])
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("run-script", result.stdout)

    def test_cli_runner_files_do_not_store_local_private_values(self) -> None:
        root = Path(__file__).resolve().parents[1]
        checked = [
            root / "src/patchharbor/cli.py",
            root / "tests/test_cli_runner.py",
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
