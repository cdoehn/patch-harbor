from __future__ import annotations

import json
import unittest
from pathlib import Path

from patchharbor.workflow_rules import DEFAULT_RULESET_VERSION, VALID_SEVERITIES, load_rules_from_text

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / "schemas/workflow-rules.schema.json"


class PatchHarborWorkflowRulesSchemaTests(unittest.TestCase):
    def read_schema(self) -> dict:
        return json.loads(SCHEMA.read_text(encoding="utf-8"))

    def test_workflow_rules_schema_exists_and_is_valid_json(self) -> None:
        schema = self.read_schema()
        self.assertEqual(schema["title"], "PatchHarbor workflow rules")
        self.assertEqual(schema["type"], "object")
        self.assertIn("$defs", schema)

    def test_schema_requires_version_and_rules(self) -> None:
        schema = self.read_schema()
        self.assertEqual(schema["required"], ["version", "rules"])
        self.assertEqual(schema["properties"]["version"]["type"], "string")
        self.assertEqual(schema["properties"]["rules"]["type"], "array")

    def test_schema_rule_definition_matches_model_basics(self) -> None:
        rule = self.read_schema()["$defs"]["workflowRule"]
        self.assertEqual(rule["required"], ["id", "description"])
        self.assertEqual(rule["properties"]["category"]["default"], "general")
        self.assertEqual(rule["properties"]["severity"]["default"], "error")
        self.assertEqual(rule["properties"]["enabled"]["default"], True)
        self.assertEqual(set(rule["properties"]["severity"]["enum"]), set(VALID_SEVERITIES))

    def test_schema_allows_extra_rule_data_for_future_linter_contracts(self) -> None:
        rule = self.read_schema()["$defs"]["workflowRule"]
        self.assertTrue(rule["additionalProperties"])

    def test_schema_example_document_is_accepted_by_model(self) -> None:
        example = {
            "version": DEFAULT_RULESET_VERSION,
            "rules": [
                {
                    "id": "patch.no_pager",
                    "description": "Avoid commands that can hang in a pager",
                    "category": "git",
                    "severity": "warning",
                    "enabled": True,
                    "command": "git diff",
                }
            ],
        }
        ruleset = load_rules_from_text(json.dumps(example), source="schema-test")
        self.assertEqual(ruleset.version, DEFAULT_RULESET_VERSION)
        self.assertEqual(ruleset.source, "schema-test")
        self.assertEqual(ruleset.rule_ids(), ("patch.no_pager",))
        self.assertEqual(ruleset.enabled_rules()[0].data["command"], "git diff")

    def test_schema_files_do_not_store_local_private_values(self) -> None:
        checked = [
            SCHEMA,
            ROOT / "tests/test_workflow_rules_schema.py",
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
