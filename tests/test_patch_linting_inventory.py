from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INVENTORY = ROOT / "docs/patch-linting-migration.md"


class PatchHarborPatchLintingInventoryTests(unittest.TestCase):
    def test_patch_linting_inventory_document_exists(self) -> None:
        self.assertTrue(INVENTORY.is_file())

    def test_inventory_lists_source_side_candidates(self) -> None:
        text = INVENTORY.read_text(encoding="utf-8")
        expected = [
            "scripts/dev/lint_patch_script.py",
            "tests/test_lint_patch_script.py",
            "scripts/dev/patch-rules.md",
            "scripts/dev/run_latest_download_patch.sh",
            "scripts/dev/repo_patch_helper.py",
        ]
        for item in expected:
            with self.subTest(item=item):
                self.assertIn(item, text)

    def test_inventory_records_generic_behaviors_to_preserve(self) -> None:
        text = INVENTORY.read_text(encoding="utf-8")
        expected = [
            "plain `git diff` or `git log`",
            "explicit footer/status summary",
            "syntax or test execution",
            "Markdown fence sequences",
            "outside heredocs",
        ]
        for item in expected:
            with self.subTest(item=item):
                self.assertIn(item, text)

    def test_inventory_defines_target_side_phases(self) -> None:
        text = INVENTORY.read_text(encoding="utf-8")
        expected = [
            "Generic patch-lint finding model",
            "Heredoc-aware shell text scanner",
            "First generic lint rules",
            "Patch lint API",
            "Small CLI subcommand",
            "Acceptance documentation",
        ]
        for item in expected:
            with self.subTest(item=item):
                self.assertIn(item, text)

    def test_inventory_keeps_current_step_inventory_only(self) -> None:
        text = INVENTORY.read_text(encoding="utf-8")
        self.assertIn("This step is inventory-only", text)
        self.assertIn("no linter code copy", text)
        self.assertIn("no lint rule implementation", text)
        self.assertIn("no source repository changes", text)

    def test_inventory_does_not_store_local_private_values(self) -> None:
        text = INVENTORY.read_text(encoding="utf-8")
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
