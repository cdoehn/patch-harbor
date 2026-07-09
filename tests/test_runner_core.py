from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from patchharbor.runner_core import (
    RunnerCoreError,
    RunnerExecutionConfig,
    check_bash_syntax,
    execute_patch_script,
    lint_script_for_runner,
    run_patch_script,
)


def metadata_lines(patch_id: str = "PATCHHARBOR.TEST") -> str:
    return (
        f'# patchharbor-meta: {{"type":"patch","id":"{patch_id}","title":"Runner core","commit":"Test runner core"}}\n'
        '# patchharbor-meta: {"type":"progress","panel":"roadmap","status":"active","file":"docs/example.md","label":"Roadmap"}\n'
        '# patchharbor-meta: {"type":"progress","panel":"milestone","status":"active","file":"docs/example.md","label":"Milestone"}\n'
        '# patchharbor-meta: {"type":"display","context":2,"layout":"side-by-side","frame":false}\n'
    )


def write_script(directory: Path, body: str, *, name: str = "patch.sh", mtime: float = 100.0) -> Path:
    path = directory / name
    path.write_text(body, encoding="utf-8")
    os.utime(path, (mtime, mtime))
    return path


def clean_script_body(command: str = 'printf "ran" > "$PATCHHARBOR_SENTINEL"\n') -> str:
    return "#!/usr/bin/env bash\n" + metadata_lines() + "set -euo pipefail\n" + command


class PatchHarborRunnerCoreTests(unittest.TestCase):
    def test_runner_execution_config_defaults_are_safe(self) -> None:
        config = RunnerExecutionConfig()
        self.assertIsNone(config.working_directory)
        self.assertEqual(config.environment, {})
        self.assertEqual(config.successful_patch_ids, ())
        self.assertFalse(config.run_lint)
        self.assertTrue(config.execute)

    def test_runner_execution_config_validates_values(self) -> None:
        with self.assertRaises(RunnerCoreError):
            RunnerExecutionConfig(environment={"": "x"})
        with self.assertRaises(RunnerCoreError):
            RunnerExecutionConfig(environment={"KEY": 1})  # type: ignore[dict-item]
        with self.assertRaises(RunnerCoreError):
            RunnerExecutionConfig(successful_patch_ids="PATCHHARBOR.TEST")  # type: ignore[arg-type]
        with self.assertRaises(RunnerCoreError):
            RunnerExecutionConfig(successful_patch_ids=("",))
        with self.assertRaises(RunnerCoreError):
            RunnerExecutionConfig(max_age_seconds=-1)
        with self.assertRaises(RunnerCoreError):
            RunnerExecutionConfig(now="bad")  # type: ignore[arg-type]
        with self.assertRaises(RunnerCoreError):
            RunnerExecutionConfig(timeout_seconds=-1)
        with self.assertRaises(RunnerCoreError):
            RunnerExecutionConfig(run_lint="yes")  # type: ignore[arg-type]
        with self.assertRaises(RunnerCoreError):
            RunnerExecutionConfig(execute="yes")  # type: ignore[arg-type]

    def test_check_bash_syntax_passes_valid_script(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = write_script(Path(tmp), clean_script_body())
            phase = check_bash_syntax(path)

        self.assertEqual(phase.phase, "syntax")
        self.assertEqual(phase.status, "passed")
        self.assertEqual(phase.exit_code, 0)

    def test_check_bash_syntax_fails_invalid_script(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = write_script(Path(tmp), "if then\n")
            phase = check_bash_syntax(path)

        self.assertEqual(phase.status, "failed")
        self.assertEqual(phase.issues[0].code, "syntax.failed")

    def test_lint_script_for_runner_reports_ok_for_clean_script(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = write_script(
                Path(tmp),
                clean_script_body(
                    "print_footer() {\n"
                    "  echo done\n"
                    "}\n"
                    "trap print_footer EXIT\n"
                    "python3 -m compileall src tests\n"
                    "git --no-pager diff\n"
                ),
            )
            phase = lint_script_for_runner(path)

        self.assertEqual(phase.status, "passed")
        self.assertEqual(phase.issues, ())

    def test_lint_script_for_runner_reports_warnings_without_failure(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = write_script(
                Path(tmp),
                clean_script_body(
                    "print_footer() {\n"
                    "  echo done\n"
                    "}\n"
                    "trap print_footer EXIT\n"
                    "python3 -m compileall src tests\n"
                    "if false; then git diff; fi\n"
                ),
            )
            phase = lint_script_for_runner(path)

        self.assertEqual(phase.status, "passed")
        self.assertTrue(phase.issues)
        self.assertTrue(all(issue.severity == "warning" for issue in phase.issues))
        self.assertEqual(phase.issues[0].data["column"], 16)
        self.assertIn("line_number", phase.issues[0].data)

    def test_execute_patch_script_runs_explicit_script_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            sentinel = root / "sentinel.txt"
            path = write_script(root, clean_script_body())
            phase = execute_patch_script(path, RunnerExecutionConfig(environment={"PATCHHARBOR_SENTINEL": str(sentinel)}))

            self.assertEqual(phase.status, "passed")
            self.assertEqual(sentinel.read_text(encoding="utf-8"), "ran")

    def test_execute_patch_script_uses_working_directory(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            work = root / "work"
            work.mkdir()
            sentinel = root / "pwd.txt"
            path = write_script(root, clean_script_body('pwd > "$PATCHHARBOR_SENTINEL"\n'))
            phase = execute_patch_script(
                path,
                RunnerExecutionConfig(
                    working_directory=work,
                    environment={"PATCHHARBOR_SENTINEL": str(sentinel)},
                ),
            )

            self.assertEqual(phase.status, "passed")
            self.assertEqual(Path(sentinel.read_text(encoding="utf-8").strip()), work)

    def test_execute_patch_script_reports_nonzero_exit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = write_script(Path(tmp), clean_script_body('echo "boom" >&2\nexit 7\n'))
            phase = execute_patch_script(path)

        self.assertEqual(phase.status, "failed")
        self.assertEqual(phase.exit_code, 7)
        self.assertEqual(phase.issues[0].code, "execute.failed")
        self.assertIn("boom", phase.issues[0].data["stderr_tail"])

    def test_run_patch_script_executes_after_preflight_and_syntax(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            sentinel = root / "sentinel.txt"
            path = write_script(root, clean_script_body(), mtime=100.0)
            result = run_patch_script(
                path,
                RunnerExecutionConfig(
                    environment={"PATCHHARBOR_SENTINEL": str(sentinel)},
                    max_age_seconds=20,
                    now=105,
                ),
            )

            self.assertTrue(result.ok, result.render_summary())
            self.assertEqual(result.phase_names(), ("metadata", "repeat", "freshness", "syntax", "lint", "execute"))
            self.assertEqual(result.by_phase()["lint"].status, "skipped")
            self.assertEqual(sentinel.read_text(encoding="utf-8"), "ran")

    def test_run_patch_script_can_disable_execution(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            sentinel = root / "sentinel.txt"
            path = write_script(root, clean_script_body(), mtime=100.0)
            result = run_patch_script(
                path,
                RunnerExecutionConfig(
                    environment={"PATCHHARBOR_SENTINEL": str(sentinel)},
                    max_age_seconds=20,
                    now=105,
                    execute=False,
                ),
            )

            self.assertTrue(result.ok, result.render_summary())
            self.assertEqual(result.by_phase()["execute"].status, "skipped")
            self.assertFalse(sentinel.exists())

    def test_run_patch_script_stops_after_failed_preflight(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            sentinel = root / "sentinel.txt"
            path = write_script(
                root,
                "#!/usr/bin/env bash\n" + '# patchharbor-meta: {"type":\n' + 'printf "ran" > "$PATCHHARBOR_SENTINEL"\n',
            )
            result = run_patch_script(path, RunnerExecutionConfig(environment={"PATCHHARBOR_SENTINEL": str(sentinel)}))

            self.assertEqual(result.status, "failed")
            self.assertEqual(result.by_phase()["metadata"].status, "failed")
            self.assertEqual(result.by_phase()["syntax"].status, "skipped")
            self.assertEqual(result.by_phase()["execute"].status, "skipped")
            self.assertFalse(sentinel.exists())

    def test_run_patch_script_stops_after_syntax_failure(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = write_script(Path(tmp), "#!/usr/bin/env bash\n" + metadata_lines() + "if then\n", mtime=100.0)
            result = run_patch_script(path, RunnerExecutionConfig(max_age_seconds=20, now=105))

        self.assertEqual(result.status, "failed")
        self.assertEqual(result.by_phase()["syntax"].status, "failed")
        self.assertEqual(result.by_phase()["lint"].status, "skipped")
        self.assertEqual(result.by_phase()["execute"].status, "skipped")

    def test_run_patch_script_fails_repeated_patch_id_before_execution(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            sentinel = root / "sentinel.txt"
            path = write_script(root, clean_script_body(), mtime=100.0)
            result = run_patch_script(
                path,
                RunnerExecutionConfig(
                    environment={"PATCHHARBOR_SENTINEL": str(sentinel)},
                    successful_patch_ids=("PATCHHARBOR.TEST",),
                    max_age_seconds=20,
                    now=105,
                ),
            )

            self.assertEqual(result.status, "failed")
            self.assertEqual(result.by_phase()["repeat"].issues[0].code, "repeat.already_applied")
            self.assertEqual(result.by_phase()["execute"].status, "skipped")
            self.assertFalse(sentinel.exists())

    def test_run_patch_script_can_run_lint_without_blocking_warning_only_findings(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            sentinel = root / "sentinel.txt"
            body = clean_script_body(
                "print_footer() {\n"
                "  echo done\n"
                "}\n"
                "trap print_footer EXIT\n"
                "python3 -m compileall src tests\n"
                "if false; then git diff; fi\n"
                'printf "ran" > "$PATCHHARBOR_SENTINEL"\n'
            )
            path = write_script(root, body, mtime=100.0)
            result = run_patch_script(
                path,
                RunnerExecutionConfig(
                    environment={"PATCHHARBOR_SENTINEL": str(sentinel)},
                    max_age_seconds=20,
                    now=105,
                    run_lint=True,
                ),
            )

            self.assertTrue(result.ok, result.render_summary())
            self.assertEqual(result.by_phase()["lint"].status, "passed")
            self.assertTrue(result.by_phase()["lint"].issues)
            self.assertEqual(result.by_phase()["lint"].issues[0].data["column"], 16)
            self.assertEqual(sentinel.read_text(encoding="utf-8"), "ran")

    def test_run_patch_script_reports_execution_failure(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = write_script(Path(tmp), clean_script_body("exit 9\n"), mtime=100.0)
            result = run_patch_script(path, RunnerExecutionConfig(max_age_seconds=20, now=105))

        self.assertEqual(result.status, "failed")
        self.assertEqual(result.by_phase()["execute"].exit_code, 9)
        self.assertEqual(result.by_phase()["execute"].issues[0].code, "execute.failed")

    def test_runner_core_files_do_not_store_local_private_values(self) -> None:
        root = Path(__file__).resolve().parents[1]
        checked = [
            root / "src/patchharbor/runner_core.py",
            root / "tests/test_runner_core.py",
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
            with self.subTest(value=value):
                self.assertNotIn(value, text)
