from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from patchharbor.workflow_rules import WorkflowRulesError
from patchharbor.workflow_validation import (
    WorkflowRuleIssue,
    WorkflowRulesValidationResult,
    issues_with_severity,
    summarize_validation_result,
    validate_workflow_rules_file,
    validate_workflow_rules_mapping,
    validate_workflow_rules_text,
)


VALID_RULES = {
    "version": "1",
    "rules": [
        {
            "id": "patch.metadata",
            "description": "Require metadata",
            "category": "metadata",
            "severity": "warning",
            "enabled": True,
            "marker": "patchharbor-meta",
        }
    ],
}


class PatchHarborWorkflowValidationTests(unittest.TestCase):
    def test_validate_workflow_rules_text_accepts_valid_rules(self) -> None:
        result = validate_workflow_rules_text(json.dumps(VALID_RULES), source="memory")
        self.assertTrue(result.ok)
        self.assertEqual(result.issues, ())
        self.assertIsNotNone(result.ruleset)
        assert result.ruleset is not None
        self.assertEqual(result.ruleset.source, "memory")
        self.assertEqual(result.ruleset.rule_ids(), ("patch.metadata",))

    def test_validate_workflow_rules_text_returns_issue_for_invalid_json(self) -> None:
        result = validate_workflow_rules_text('{"version":')
        self.assertFalse(result.ok)
        self.assertIsNone(result.ruleset)
        self.assertEqual(len(result.errors), 1)
        self.assertIn("invalid", result.errors[0].message)

    def test_validate_workflow_rules_mapping_accepts_plain_mapping(self) -> None:
        result = validate_workflow_rules_mapping(VALID_RULES, source="mapping")
        self.assertTrue(result.ok)
        self.assertIsNotNone(result.ruleset)
        assert result.ruleset is not None
        self.assertEqual(result.ruleset.source, "mapping")

    def test_validate_workflow_rules_mapping_reports_model_errors(self) -> None:
        result = validate_workflow_rules_mapping(
            {
                "version": "1",
                "rules": [
                    {"id": "duplicate", "description": "first"},
                    {"id": "duplicate", "description": "second"},
                ],
            }
        )
        self.assertFalse(result.ok)
        self.assertIn("duplicate", result.errors[0].message)

    def test_validate_workflow_rules_file_reads_valid_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "rules.json"
            path.write_text(json.dumps(VALID_RULES), encoding="utf-8")
            result = validate_workflow_rules_file(path)
        self.assertTrue(result.ok)
        self.assertIsNotNone(result.ruleset)

    def test_validate_workflow_rules_file_reports_missing_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = validate_workflow_rules_file(Path(tmp) / "missing-rules.json")
        self.assertFalse(result.ok)
        self.assertIsNone(result.ruleset)
        self.assertEqual(result.errors[0].path_label(), "file")

    def test_issue_rendering_and_path_label_are_stable(self) -> None:
        issue = WorkflowRuleIssue("Something happened", severity="warning", path=("rules", "0"))
        self.assertEqual(issue.path_label(), "rules.0")
        self.assertEqual(issue.render(), "warning: rules.0: Something happened")

    def test_issue_rejects_invalid_message_or_severity(self) -> None:
        with self.assertRaises(WorkflowRulesError):
            WorkflowRuleIssue("")
        with self.assertRaises(WorkflowRulesError):
            WorkflowRuleIssue("message", severity="fatal")

    def test_validation_result_ok_allows_warnings(self) -> None:
        result = WorkflowRulesValidationResult(
            ruleset=None,
            issues=(WorkflowRuleIssue("Only a warning", severity="warning"),),
        )
        self.assertTrue(result.ok)
        self.assertEqual(result.errors, ())

    def test_validation_result_rejects_non_issue_items(self) -> None:
        with self.assertRaises(WorkflowRulesError):
            WorkflowRulesValidationResult(ruleset=None, issues=("not-an-issue",))  # type: ignore[arg-type]

    def test_validation_result_raise_for_errors_raises_combined_error(self) -> None:
        result = WorkflowRulesValidationResult(
            ruleset=None,
            issues=(WorkflowRuleIssue("Broken", path=("document",)),),
        )
        with self.assertRaises(WorkflowRulesError):
            result.raise_for_errors()

    def test_summarize_validation_result_reports_ok_count(self) -> None:
        result = validate_workflow_rules_mapping(VALID_RULES)
        self.assertEqual(summarize_validation_result(result), ("status: ok", "rules: 1"))

    def test_summarize_validation_result_reports_errors(self) -> None:
        result = validate_workflow_rules_text("[]")
        summary = summarize_validation_result(result)
        self.assertEqual(summary[0], "status: error")
        self.assertIn("workflow rules JSON must contain an object", summary[1])

    def test_issues_with_severity_filters_and_validates_severity(self) -> None:
        error = WorkflowRuleIssue("Error")
        warning = WorkflowRuleIssue("Warning", severity="warning")
        self.assertEqual(issues_with_severity((error, warning), "warning"), (warning,))
        with self.assertRaises(WorkflowRulesError):
            issues_with_severity((error, warning), "fatal")

    def test_validation_files_do_not_store_local_private_values(self) -> None:
        root = Path(__file__).resolve().parents[1]
        checked = [
            root / "src/patchharbor/workflow_validation.py",
            root / "tests/test_workflow_validation.py",
        ]
        text = "\n".join(path.read_text(encoding="utf-8") for path in checked)
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
