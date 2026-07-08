from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from patchharbor.patch_lint import PatchLintFinding, PatchLintResult, PatchLintError
from patchharbor.patch_lint_api import (
    DEFAULT_PATCH_LINT_RULES,
    default_patch_lint_rules,
    lint_patch_file,
    lint_patch_files,
    lint_patch_text,
    patch_lint_rule_names,
    render_patch_lint_result,
)
from patchharbor.patch_lint_rules import RULE_FOOTER, RULE_GIT_NO_PAGER, lint_git_pager_commands


class PatchHarborPatchLintApiTests(unittest.TestCase):
    def test_default_patch_lint_rules_are_stable(self) -> None:
        self.assertEqual(default_patch_lint_rules(), DEFAULT_PATCH_LINT_RULES)
        self.assertIn("lint_git_pager_commands", patch_lint_rule_names())
        self.assertIn("lint_missing_footer", patch_lint_rule_names())

    def test_lint_patch_text_runs_default_rules(self) -> None:
        result = lint_patch_text("git diff\n")
        rule_ids = {finding.rule_id for finding in result.findings}
        self.assertIn(RULE_GIT_NO_PAGER, rule_ids)
        self.assertIn(RULE_FOOTER, rule_ids)

    def test_lint_patch_text_accepts_selected_rules(self) -> None:
        result = lint_patch_text("git diff\n", rules=(lint_git_pager_commands,))
        self.assertEqual([finding.rule_id for finding in result.findings], [RULE_GIT_NO_PAGER])

    def test_lint_patch_text_allows_empty_rule_set(self) -> None:
        result = lint_patch_text("git diff\n", rules=())
        self.assertTrue(result.ok)
        self.assertEqual(result.findings, ())

    def test_lint_patch_text_sorts_findings_by_default(self) -> None:
        text = "git diff\n"
        result = lint_patch_text(text)
        self.assertEqual(result.findings[0].rule_id, RULE_GIT_NO_PAGER)

    def test_lint_patch_text_can_preserve_rule_order(self) -> None:
        def late_rule(_: str) -> PatchLintResult:
            return PatchLintResult((PatchLintFinding("late", "late", line_number=10),))

        def early_rule(_: str) -> PatchLintResult:
            return PatchLintResult((PatchLintFinding("early", "early", line_number=1),))

        result = lint_patch_text("echo ok\n", rules=(late_rule, early_rule), sort=False)
        self.assertEqual([finding.rule_id for finding in result.findings], ["late", "early"])

    def test_lint_patch_text_rejects_invalid_inputs(self) -> None:
        with self.assertRaises(PatchLintError):
            lint_patch_text(5)  # type: ignore[arg-type]
        with self.assertRaises(PatchLintError):
            lint_patch_text("echo ok\n", rules=("not-callable",))  # type: ignore[arg-type]

    def test_lint_patch_text_rejects_rules_returning_wrong_type(self) -> None:
        def bad_rule(_: str) -> object:
            return object()

        with self.assertRaises(PatchLintError):
            lint_patch_text("echo ok\n", rules=(bad_rule,))  # type: ignore[arg-type]

    def test_lint_patch_file_reads_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "patch.sh"
            path.write_text("git log\n", encoding="utf-8")
            result = lint_patch_file(path, rules=(lint_git_pager_commands,))
        self.assertEqual([finding.rule_id for finding in result.findings], [RULE_GIT_NO_PAGER])

    def test_lint_patch_file_wraps_read_errors(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            missing = Path(tmp) / "missing.sh"
            with self.assertRaises(PatchLintError):
                lint_patch_file(missing)

    def test_lint_patch_files_returns_result_per_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            first = Path(tmp) / "one.sh"
            second = Path(tmp) / "two.sh"
            first.write_text("git diff\n", encoding="utf-8")
            second.write_text("git --no-pager diff\n", encoding="utf-8")
            results = lint_patch_files((first, second), rules=(lint_git_pager_commands,))

        self.assertEqual(set(results), {first, second})
        self.assertEqual(len(results[first].findings), 1)
        self.assertEqual(results[second].findings, ())

    def test_lint_patch_files_rejects_single_path_as_collection(self) -> None:
        with self.assertRaises(PatchLintError):
            lint_patch_files("patch.sh")  # type: ignore[arg-type]

    def test_render_patch_lint_result_reports_ok_warning_info_and_error(self) -> None:
        self.assertEqual(render_patch_lint_result(PatchLintResult()), ("status: ok",))

        warning = PatchLintResult((PatchLintFinding("warning", "warning"),))
        self.assertEqual(render_patch_lint_result(warning)[0], "status: warning")

        info = PatchLintResult((PatchLintFinding("info", "info", severity="info"),))
        self.assertEqual(render_patch_lint_result(info)[0], "status: info")

        error = PatchLintResult((PatchLintFinding("error", "error", severity="error"),))
        self.assertEqual(render_patch_lint_result(error)[0], "status: error")

    def test_render_patch_lint_result_rejects_wrong_type(self) -> None:
        with self.assertRaises(PatchLintError):
            render_patch_lint_result("not-a-result")  # type: ignore[arg-type]

    def test_patch_lint_api_files_do_not_store_local_private_values(self) -> None:
        root = Path(__file__).resolve().parents[1]
        checked = [
            root / "src/patchharbor/patch_lint_api.py",
            root / "tests/test_patch_lint_api.py",
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
