from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INVENTORY = ROOT / "docs/runner-compatibility-migration.md"


class PatchHarborRunnerCompatibilityInventoryTests(unittest.TestCase):
    def test_runner_compatibility_inventory_document_exists(self) -> None:
        self.assertTrue(INVENTORY.is_file())

    def test_inventory_lists_source_side_candidates(self) -> None:
        text = INVENTORY.read_text(encoding="utf-8")
        expected = [
            "scripts/dev/run_latest_download_patch.sh",
            "scripts/dev/repo_patch_helper.py",
            "scripts/dev/install_aliases.sh",
            "scripts/dev/show_progress_context.py",
            "scripts/dev/validate_patch_metadata.py",
            "scripts/dev/validate_patch_workflow_rules.py",
            "scripts/dev/lint_patch_script.py",
            "scripts/dev/patch-rules.md",
        ]
        for item in expected:
            with self.subTest(item=item):
                self.assertIn(item, text)

    def test_inventory_records_runner_responsibilities_to_split(self) -> None:
        text = INVENTORY.read_text(encoding="utf-8")
        expected = [
            "selecting the newest downloaded patch script",
            "validating patch metadata comments",
            "detecting repeated successful patch application",
            "checking script freshness",
            "running Bash syntax checks",
            "writing a persistent log",
            "moving successful scripts to a done folder",
            "moving failed scripts to a failed folder",
        ]
        for item in expected:
            with self.subTest(item=item):
                self.assertIn(item, text)

    def test_inventory_marks_context_and_milestone_display_as_patchharbor_scope(self) -> None:
        text = INVENTORY.read_text(encoding="utf-8")
        expected = [
            "Context and milestone display belongs to PatchHarbor",
            "patch footer status sections",
            "current and next-step display",
            "done/current/next/problem colors",
            "milestone and roadmap labels from patch metadata",
            "progress context used by the patch runner output",
        ]
        for item in expected:
            with self.subTest(item=item):
                self.assertIn(item, text)

    def test_inventory_defines_compatibility_boundary(self) -> None:
        text = INVENTORY.read_text(encoding="utf-8")
        expected = [
            "generic runner and display primitives",
            "thin wrappers or configuration",
            "local command aliases",
            "repository-specific paths",
            "compatibility command names",
        ]
        for item in expected:
            with self.subTest(item=item):
                self.assertIn(item, text)

    def test_inventory_defines_target_side_phases(self) -> None:
        text = INVENTORY.read_text(encoding="utf-8")
        expected = [
            "Generic runner result and status model",
            "Preflight APIs for metadata, freshness, and repeat checks",
            "Download-file discovery and lifecycle planning",
            "Runner core that can execute an explicit script path",
            "Context and milestone display renderer",
            "Optional CLI command for explicit runner use",
            "Acceptance documentation",
        ]
        for item in expected:
            with self.subTest(item=item):
                self.assertIn(item, text)

    def test_inventory_keeps_current_step_inventory_only(self) -> None:
        text = INVENTORY.read_text(encoding="utf-8")
        self.assertIn("This step is inventory-only", text)
        self.assertIn("no runner code copy", text)
        self.assertIn("no download-folder mutation", text)
        self.assertIn("no source-repository wrapper changes", text)

    def test_inventory_does_not_store_local_private_values(self) -> None:
        text = INVENTORY.read_text(encoding="utf-8")
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
