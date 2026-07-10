from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / "docs/workflow-rules-migration.md"


class PatchHarborWorkflowRulesInventoryTests(unittest.TestCase):
    def test_workflow_rules_inventory_document_exists(self) -> None:
        self.assertTrue(DOC.is_file())

    def test_inventory_lists_source_side_candidates(self) -> None:
        text = DOC.read_text(encoding="utf-8")
        expected = [
            "scripts/dev/patch-workflow-rules.json",
            "scripts/dev/patch-workflow-rules.schema.json",
            "scripts/dev/validate_patch_workflow_rules.py",
            "tests/test_patch_workflow_rules_schema.py",
            "scripts/dev/lint_patch_script.py",
            "scripts/dev/run_latest_download_patch.sh",
        ]
        for item in expected:
            with self.subTest(item=item):
                self.assertIn(item, text)

    def test_inventory_defines_target_side_phases(self) -> None:
        text = DOC.read_text(encoding="utf-8")
        expected = [
            "Generic workflow-rules data model",
            "Generic JSON schema",
            "Rule validator API",
            "Linter integration",
            "Runner integration",
        ]
        for item in expected:
            with self.subTest(item=item):
                self.assertIn(item, text)

    def test_inventory_keeps_current_step_inventory_only(self) -> None:
        text = DOC.read_text(encoding="utf-8")
        self.assertIn("This step is inventory-only", text)
        self.assertIn("no schema copy", text)
        self.assertIn("no JSON rules copy", text)
        self.assertIn("no source repository changes", text)

    def test_inventory_does_not_store_local_private_values(self) -> None:
        text = DOC.read_text(encoding="utf-8")
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
