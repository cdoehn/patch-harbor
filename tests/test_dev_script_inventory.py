from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INVENTORY = ROOT / "docs/dev-script-inventory.md"


class PatchHarborDevScriptInventoryTests(unittest.TestCase):
    def test_inventory_document_exists(self) -> None:
        self.assertTrue(INVENTORY.is_file())

    def test_inventory_lists_core_source_candidates(self) -> None:
        text = INVENTORY.read_text(encoding="utf-8")
        expected = [
            "scripts/dev/run_latest_download_patch.sh",
            "scripts/dev/repo_patch_helper.py",
            "scripts/dev/validate_patch_metadata.py",
            "scripts/dev/lint_patch_script.py",
            "scripts/dev/show_progress_context.py",
            "scripts/dev/run_repodossier_exports.sh",
        ]
        for item in expected:
            with self.subTest(item=item):
                self.assertIn(item, text)

    def test_inventory_keeps_migration_boundary_clear(self) -> None:
        text = INVENTORY.read_text(encoding="utf-8")
        self.assertIn("source repository remains unchanged", text)
        self.assertIn("No source Dev-Script files are copied", text)
        self.assertIn("Suggested extraction order", text)

    def test_inventory_does_not_store_local_private_values(self) -> None:
        text = INVENTORY.read_text(encoding="utf-8")
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
