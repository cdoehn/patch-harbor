from __future__ import annotations

import unittest
from pathlib import Path

from patchharbor.runner_status import (
    VALID_RUN_PHASES,
    VALID_RUN_SEVERITIES,
    VALID_RUN_STATUSES,
    RunnerIssue,
    RunnerPhaseResult,
    RunnerResult,
    RunnerStatusError,
    derive_runner_status,
    failed_phase,
    passed_phase,
)


class PatchHarborRunnerStatusTests(unittest.TestCase):
    def test_runner_issue_defaults_to_error(self) -> None:
        issue = RunnerIssue("Metadata missing", phase="metadata", code="metadata.missing")
        self.assertTrue(issue.is_error)
        self.assertEqual(issue.render(), "error:metadata:metadata.missing: Metadata missing")

    def test_runner_issue_supports_mapping_roundtrip_with_extra_data(self) -> None:
        issue = RunnerIssue.from_mapping(
            {
                "message": "Freshness check skipped",
                "severity": "warning",
                "phase": "freshness",
                "code": "freshness.skipped",
                "age_seconds": 12,
            }
        )
        self.assertEqual(issue.data["age_seconds"], 12)
        self.assertEqual(issue.to_mapping()["age_seconds"], 12)

    def test_runner_issue_rejects_invalid_values(self) -> None:
        with self.assertRaises(RunnerStatusError):
            RunnerIssue("")
        with self.assertRaises(RunnerStatusError):
            RunnerIssue("message", severity="fatal")
        with self.assertRaises(RunnerStatusError):
            RunnerIssue("message", phase="unknown")
        with self.assertRaises(RunnerStatusError):
            RunnerIssue("message", code="")
        with self.assertRaises(RunnerStatusError):
            RunnerIssue("message", data=["bad"])  # type: ignore[arg-type]

    def test_runner_phase_result_defaults_to_pending(self) -> None:
        phase = RunnerPhaseResult("metadata")
        self.assertEqual(phase.status, "pending")
        self.assertFalse(phase.ok)
        self.assertEqual(phase.errors, ())

    def test_runner_phase_result_ok_for_passed_and_skipped_without_errors(self) -> None:
        self.assertTrue(RunnerPhaseResult("metadata", status="passed").ok)
        self.assertTrue(RunnerPhaseResult("lint", status="skipped").ok)

    def test_runner_phase_with_issue_fails_on_error_issue(self) -> None:
        phase = RunnerPhaseResult("syntax", status="passed")
        failed = phase.with_issue(RunnerIssue("bash syntax failed", phase="syntax"))
        self.assertEqual(failed.status, "failed")
        self.assertFalse(failed.ok)
        self.assertEqual(len(failed.errors), 1)

    def test_runner_phase_with_warning_keeps_status(self) -> None:
        phase = RunnerPhaseResult("lint", status="passed")
        warned = phase.with_issue(RunnerIssue("warning", severity="warning", phase="lint"))
        self.assertEqual(warned.status, "passed")
        self.assertTrue(warned.ok)

    def test_runner_phase_mapping_roundtrip(self) -> None:
        phase = RunnerPhaseResult.from_mapping(
            {
                "phase": "execute",
                "status": "failed",
                "message": "script failed",
                "exit_code": 1,
                "duration_seconds": 0.5,
                "issues": [{"message": "exit code 1", "phase": "execute"}],
            }
        )
        mapping = phase.to_mapping()
        self.assertEqual(mapping["phase"], "execute")
        self.assertEqual(mapping["status"], "failed")
        self.assertEqual(mapping["exit_code"], 1)
        self.assertEqual(mapping["duration_seconds"], 0.5)
        self.assertEqual(mapping["issues"][0]["message"], "exit code 1")

    def test_runner_phase_rejects_invalid_values(self) -> None:
        cases = [
            lambda: RunnerPhaseResult("unknown"),
            lambda: RunnerPhaseResult("metadata", status="bad"),
            lambda: RunnerPhaseResult("metadata", message=""),
            lambda: RunnerPhaseResult("metadata", exit_code="1"),  # type: ignore[arg-type]
            lambda: RunnerPhaseResult("metadata", duration_seconds=-1),
            lambda: RunnerPhaseResult("metadata", issues=("bad",)),  # type: ignore[arg-type]
        ]
        for case in cases:
            with self.subTest(case=case):
                with self.assertRaises(RunnerStatusError):
                    case()

    def test_runner_result_defaults_to_pending(self) -> None:
        result = RunnerResult()
        self.assertEqual(result.status, "pending")
        self.assertFalse(result.ok)
        self.assertEqual(result.phase_names(), ())
        self.assertEqual(result.errors, ())

    def test_runner_result_ok_when_passed_without_errors(self) -> None:
        result = RunnerResult(status="passed", phases=(passed_phase("metadata"), passed_phase("syntax")))
        self.assertTrue(result.ok)
        self.assertEqual(result.phase_names(), ("metadata", "syntax"))

    def test_runner_result_with_phase_derives_status(self) -> None:
        result = RunnerResult().with_phase(passed_phase("metadata")).with_phase(passed_phase("syntax"))
        self.assertEqual(result.status, "passed")
        self.assertTrue(result.ok)

    def test_runner_result_with_failed_phase_derives_failed_status(self) -> None:
        result = RunnerResult().with_phase(passed_phase("metadata")).with_phase(failed_phase("syntax", "failed"))
        self.assertEqual(result.status, "failed")
        self.assertFalse(result.ok)
        self.assertEqual(len(result.errors), 1)

    def test_runner_result_with_issue_sets_failed_for_error_issue(self) -> None:
        result = RunnerResult(status="passed").with_issue(RunnerIssue("problem", phase="display"))
        self.assertEqual(result.status, "failed")
        self.assertFalse(result.ok)

    def test_runner_result_rejects_duplicate_phases(self) -> None:
        with self.assertRaises(RunnerStatusError):
            RunnerResult(phases=(passed_phase("metadata"), passed_phase("metadata")))

    def test_runner_result_mapping_roundtrip(self) -> None:
        result = RunnerResult.from_mapping(
            {
                "status": "failed",
                "script_path": "downloads/patch.sh",
                "log_path": "logs/patch.log",
                "exit_code": 1,
                "phases": [{"phase": "metadata", "status": "passed"}],
                "issues": [{"message": "runner failed", "phase": "execute"}],
            }
        )
        mapping = result.to_mapping()
        self.assertEqual(mapping["status"], "failed")
        self.assertEqual(mapping["script_path"], "downloads/patch.sh")
        self.assertEqual(mapping["log_path"], "logs/patch.log")
        self.assertEqual(mapping["exit_code"], 1)
        self.assertEqual(mapping["phases"][0]["phase"], "metadata")
        self.assertEqual(mapping["issues"][0]["message"], "runner failed")

    def test_runner_result_render_summary_is_stable(self) -> None:
        result = RunnerResult(
            status="failed",
            script_path="downloads/patch.sh",
            log_path="logs/patch.log",
            exit_code=1,
            phases=(failed_phase("execute", "script failed", code="exit.nonzero"),),
        )
        summary = result.render_summary()
        self.assertEqual(summary[0], "status: failed")
        self.assertIn("script: downloads/patch.sh", summary)
        self.assertIn("log: logs/patch.log", summary)
        self.assertIn("exit_code: 1", summary)
        self.assertTrue(any(line.startswith("phase: execute") for line in summary))
        self.assertTrue(any("exit.nonzero" in line for line in summary))

    def test_derive_runner_status_orders_failure_running_passed_pending(self) -> None:
        self.assertEqual(derive_runner_status((passed_phase("metadata"),)), "passed")
        self.assertEqual(derive_runner_status((RunnerPhaseResult("execute", status="running"),)), "running")
        self.assertEqual(derive_runner_status((failed_phase("execute", "failed"),)), "failed")
        self.assertEqual(derive_runner_status(()), "pending")
        self.assertEqual(derive_runner_status((), (RunnerIssue("problem"),)), "failed")

    def test_helper_constructors_return_expected_phases(self) -> None:
        self.assertEqual(passed_phase("metadata", "ok").status, "passed")
        failed = failed_phase("syntax", "bad syntax", code="syntax.failed")
        self.assertEqual(failed.status, "failed")
        self.assertEqual(failed.issues[0].code, "syntax.failed")

    def test_status_constants_include_runner_and_display_phases(self) -> None:
        self.assertEqual(VALID_RUN_STATUSES, frozenset({"pending", "running", "passed", "failed", "skipped"}))
        self.assertEqual(VALID_RUN_SEVERITIES, frozenset({"error", "warning", "info"}))
        self.assertIn("display", VALID_RUN_PHASES)
        self.assertIn("lifecycle", VALID_RUN_PHASES)

    def test_runner_status_files_do_not_store_local_private_values(self) -> None:
        root = Path(__file__).resolve().parents[1]
        checked = [
            root / "src/patchharbor/runner_status.py",
            root / "tests/test_runner_status.py",
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
