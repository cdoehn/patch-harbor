from __future__ import annotations

import unittest
from pathlib import Path

from patchharbor.patch_lint import (
    VALID_LINT_SEVERITIES,
    PatchLintError,
    PatchLintFinding,
    PatchLintResult,
    findings_with_severity,
    sort_findings,
)


class PatchHarborPatchLintModelTests(unittest.TestCase):
    def test_finding_defaults_are_generic_warning_without_location(self) -> None:
        finding = PatchLintFinding(rule_id="patch.footer", message="Footer is missing")
        self.assertEqual(finding.severity, "warning")
        self.assertIsNone(finding.line_number)
        self.assertIsNone(finding.column)
        self.assertIsNone(finding.hint)
        self.assertEqual(finding.data, {})
        self.assertEqual(finding.location_label(), ".")

    def test_finding_location_label_handles_line_and_column(self) -> None:
        line_only = PatchLintFinding(rule_id="rule", message="message", line_number=7)
        with_column = PatchLintFinding(rule_id="rule", message="message", line_number=7, column=3)
        self.assertEqual(line_only.location_label(), "line 7")
        self.assertEqual(with_column.location_label(), "line 7:3")

    def test_finding_render_includes_hint_when_available(self) -> None:
        finding = PatchLintFinding(
            rule_id="patch.no_pager",
            message="Avoid pager commands",
            severity="error",
            line_number=4,
            column=2,
            hint="Use git --no-pager diff",
        )
        self.assertEqual(
            finding.render(),
            "error: patch.no_pager: line 4:2: Avoid pager commands Hint: Use git --no-pager diff",
        )

    def test_finding_from_mapping_preserves_extra_data(self) -> None:
        finding = PatchLintFinding.from_mapping(
            {
                "rule_id": "patch.tests",
                "message": "Tests are missing",
                "severity": "info",
                "line_number": 12,
                "column": 5,
                "hint": "Run focused tests",
                "command": "python3 -m unittest",
            }
        )
        self.assertEqual(finding.rule_id, "patch.tests")
        self.assertEqual(finding.severity, "info")
        self.assertEqual(finding.data["command"], "python3 -m unittest")

    def test_finding_to_mapping_round_trips_known_and_extra_fields(self) -> None:
        finding = PatchLintFinding(
            rule_id="patch.syntax",
            message="Syntax check failed",
            severity="error",
            line_number=2,
            column=1,
            hint="Run bash -n",
            data={"tool": "bash"},
        )
        mapping = finding.to_mapping()
        self.assertEqual(mapping["rule_id"], "patch.syntax")
        self.assertEqual(mapping["severity"], "error")
        self.assertEqual(mapping["line_number"], 2)
        self.assertEqual(mapping["column"], 1)
        self.assertEqual(mapping["hint"], "Run bash -n")
        self.assertEqual(mapping["tool"], "bash")

    def test_finding_rejects_empty_required_strings(self) -> None:
        cases = (
            {"rule_id": "", "message": "message"},
            {"rule_id": "rule", "message": ""},
        )
        for kwargs in cases:
            with self.subTest(kwargs=kwargs):
                with self.assertRaises(PatchLintError):
                    PatchLintFinding(**kwargs)

    def test_finding_rejects_invalid_severity(self) -> None:
        with self.assertRaises(PatchLintError):
            PatchLintFinding(rule_id="rule", message="message", severity="fatal")

    def test_finding_rejects_invalid_line_or_column(self) -> None:
        cases = (
            {"line_number": 0},
            {"line_number": "1"},
            {"column": 0},
            {"column": "1"},
        )
        for kwargs in cases:
            with self.subTest(kwargs=kwargs):
                with self.assertRaises(PatchLintError):
                    PatchLintFinding(rule_id="rule", message="message", **kwargs)  # type: ignore[arg-type]

    def test_finding_rejects_invalid_hint_or_data(self) -> None:
        with self.assertRaises(PatchLintError):
            PatchLintFinding(rule_id="rule", message="message", hint="")
        with self.assertRaises(PatchLintError):
            PatchLintFinding(rule_id="rule", message="message", data=["bad"])  # type: ignore[arg-type]

    def test_finding_from_mapping_requires_mapping_and_required_fields(self) -> None:
        with self.assertRaises(PatchLintError):
            PatchLintFinding.from_mapping(["not", "mapping"])  # type: ignore[arg-type]
        with self.assertRaises(PatchLintError):
            PatchLintFinding.from_mapping({"rule_id": "rule"})

    def test_result_defaults_to_ok_without_findings(self) -> None:
        result = PatchLintResult()
        self.assertTrue(result.ok)
        self.assertFalse(result.has_findings)
        self.assertEqual(result.findings, ())
        self.assertEqual(result.errors, ())
        self.assertEqual(result.warnings, ())
        self.assertEqual(result.infos, ())

    def test_result_groups_findings_by_severity(self) -> None:
        error = PatchLintFinding(rule_id="error.rule", message="error", severity="error")
        warning = PatchLintFinding(rule_id="warning.rule", message="warning")
        info = PatchLintFinding(rule_id="info.rule", message="info", severity="info")
        result = PatchLintResult((error, warning, info))
        self.assertFalse(result.ok)
        self.assertTrue(result.has_findings)
        self.assertEqual(result.errors, (error,))
        self.assertEqual(result.warnings, (warning,))
        self.assertEqual(result.infos, (info,))

    def test_result_with_finding_and_extend_return_new_results(self) -> None:
        first = PatchLintFinding(rule_id="first", message="first")
        second = PatchLintFinding(rule_id="second", message="second")
        empty = PatchLintResult()
        one = empty.with_finding(first)
        two = one.extend([second])
        self.assertEqual(empty.findings, ())
        self.assertEqual(one.findings, (first,))
        self.assertEqual(two.findings, (first, second))

    def test_result_rejects_non_finding_items(self) -> None:
        with self.assertRaises(PatchLintError):
            PatchLintResult(("not-a-finding",))  # type: ignore[arg-type]
        with self.assertRaises(PatchLintError):
            PatchLintResult().with_finding("not-a-finding")  # type: ignore[arg-type]

    def test_result_render_and_mapping_are_plain_data(self) -> None:
        finding = PatchLintFinding(rule_id="patch.footer", message="Footer is missing", line_number=8)
        result = PatchLintResult((finding,))
        self.assertEqual(result.render_findings(), ("warning: patch.footer: line 8: Footer is missing",))
        self.assertEqual(result.to_mapping()["findings"][0]["line_number"], 8)

    def test_result_raise_for_errors_only_raises_for_error_findings(self) -> None:
        warning_result = PatchLintResult((PatchLintFinding(rule_id="warning", message="warning"),))
        warning_result.raise_for_errors()

        error_result = PatchLintResult(
            (PatchLintFinding(rule_id="error", message="error", severity="error"),)
        )
        with self.assertRaises(PatchLintError):
            error_result.raise_for_errors()

    def test_findings_with_severity_filters_and_validates_severity(self) -> None:
        error = PatchLintFinding(rule_id="error", message="error", severity="error")
        warning = PatchLintFinding(rule_id="warning", message="warning")
        self.assertEqual(findings_with_severity((error, warning), "error"), (error,))
        with self.assertRaises(PatchLintError):
            findings_with_severity((error, warning), "fatal")

    def test_sort_findings_orders_locations_before_unknown_locations(self) -> None:
        unknown = PatchLintFinding(rule_id="z", message="unknown")
        later = PatchLintFinding(rule_id="b", message="later", line_number=10)
        earlier = PatchLintFinding(rule_id="a", message="earlier", line_number=2)
        same_line_with_column = PatchLintFinding(rule_id="c", message="column", line_number=10, column=1)
        self.assertEqual(
            sort_findings((unknown, later, earlier, same_line_with_column)),
            (earlier, same_line_with_column, later, unknown),
        )

    def test_valid_lint_severities_are_stable(self) -> None:
        self.assertEqual(VALID_LINT_SEVERITIES, frozenset({"error", "warning", "info"}))

    def test_test_file_does_not_store_local_private_values(self) -> None:
        text = Path(__file__).read_text(encoding="utf-8")
        forbidden = [
            "/home/" + "exampleuser",
            "user" + "@",
            "example.user" + "@" + "example.invalid",
            "Example" + "Laptop",
            "~/" + "Projects",
        ]
        for value in forbidden:
            with self.subTest(value=value):
                self.assertNotIn(value, text)
