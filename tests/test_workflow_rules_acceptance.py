from __future__ import annotations

import json
import unittest
from pathlib import Path

from patchharbor.workflow_rules import VALID_SEVERITIES, WorkflowRuleSet, load_rules_from_text
from patchharbor.workflow_validation import summarize_validation_result, validate_workflow_rules_text

ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / "docs/workflow-rules-acceptance.md"
SCHEMA = ROOT / "schemas/workflow-rules.schema.json"


class PatchHarborWorkflowRulesAcceptanceTests(unittest.TestCase):
    def test_acceptance_document_exists_and_sets_boundaries(self) -> None:
        text = DOC.read_text(encoding="utf-8")
        self.assertIn("PatchHarbor.04 workflow rules acceptance", text)
        self.assertIn("Accepted scope", text)
        self.assertIn("Explicit non-goals", text)
        self.assertIn("RepoDossier remains unchanged", text)

    def test_phase_components_are_present(self) -> None:
        expected = [
            ROOT / "docs/workflow-rules-migration.md",
            ROOT / "src/patchharbor/workflow_rules.py",
            ROOT / "tests/test_workflow_rules.py",
            ROOT / "schemas/workflow-rules.schema.json",
            ROOT / "tests/test_workflow_rules_schema.py",
            ROOT / "src/patchharbor/workflow_validation.py",
            ROOT / "tests/test_workflow_validation.py",
        ]
        for path in expected:
            with self.subTest(path=path.relative_to(ROOT)):
                self.assertTrue(path.is_file())

    def test_phase_accepts_neutral_rules_document_end_to_end(self) -> None:
        document = {
            "version": "1",
            "rules": [
                {
                    "id": "patch.metadata",
                    "description": "Require patch metadata",
                    "category": "metadata",
                    "severity": "warning",
                    "enabled": True,
                    "marker": "patchharbor-meta",
                }
            ],
        }
        text = json.dumps(document)
        ruleset = load_rules_from_text(text, source="acceptance")
        result = validate_workflow_rules_text(text, source="acceptance")
        self.assertIsInstance(ruleset, WorkflowRuleSet)
        self.assertTrue(result.ok)
        self.assertEqual(summarize_validation_result(result), ("status: ok", "rules: 1"))
        self.assertEqual(ruleset.enabled_rules()[0].data["marker"], "patchharbor-meta")

    def test_schema_and_model_keep_severity_contract_aligned(self) -> None:
        schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
        severity_values = schema["$defs"]["workflowRule"]["properties"]["severity"]["enum"]
        self.assertEqual(set(severity_values), set(VALID_SEVERITIES))

    def test_acceptance_document_keeps_linter_and_runner_out_of_scope(self) -> None:
        text = DOC.read_text(encoding="utf-8")
        expected = [
            "patch-script linting rules",
            "download patch runner",
            "source-repository compatibility wrappers",
            "later phases",
        ]
        for item in expected:
            with self.subTest(item=item):
                self.assertIn(item, text)

    def test_acceptance_files_do_not_store_local_private_values(self) -> None:
        checked = [
            DOC,
            ROOT / "tests/test_workflow_rules_acceptance.py",
        ]
        text = "\n".join(path.read_text(encoding="utf-8") for path in checked)
        forbidden = [
            "/home/" + "christian",
            "christian" + "@",
            "christian.doehn" + "@" + "gmail.com",
            "Think" + "Pad",
            "~/" + "Projekte",
        ]
        for value in forbidden:
            with self.subTest(value=value):
                self.assertNotIn(value, text)
