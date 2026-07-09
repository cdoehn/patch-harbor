from __future__ import annotations

from pathlib import Path
import unittest


class PatchHarborSourceWrapperCompatibilityInventoryTests(unittest.TestCase):
    def test_source_wrapper_inventory_document_exists(self) -> None:
        root = Path(__file__).resolve().parents[1]
        path = root / "docs/source-wrapper-compatibility-migration.md"
        self.assertTrue(path.exists())
        self.assertIn("PatchHarbor source-wrapper compatibility migration inventory", path.read_text(encoding="utf-8"))

    def test_inventory_lists_core_source_side_candidates(self) -> None:
        root = Path(__file__).resolve().parents[1]
        text = (root / "docs/source-wrapper-compatibility-migration.md").read_text(encoding="utf-8")
        candidates = [
            "scripts/dev/run_latest_download_patch.sh",
            "scripts/dev/install_aliases.sh",
            "scripts/dev/r.sh",
            "scripts/dev/run_repodossier_exports.sh",
            "scripts/dev/repo_patch_helper.py",
            "scripts/dev/show_progress_context.py",
            "scripts/dev/validate_patch_metadata.py",
            "scripts/dev/lint_patch_script.py",
            "scripts/dev/patch-rules.md",
        ]
        for candidate in candidates:
            with self.subTest(candidate=candidate):
                self.assertIn(candidate, text)

    def test_inventory_defines_wrapper_boundaries(self) -> None:
        root = Path(__file__).resolve().parents[1]
        text = (root / "docs/source-wrapper-compatibility-migration.md").read_text(encoding="utf-8")
        required = [
            "Generic PatchHarbor APIs and CLI commands",
            "Source-repository wrapper scripts",
            "Local alias or shell integration",
            "Source-specific defaults and safety rules",
            "should not assume a contributor home directory",
            "should not copy generic runner, lint, lifecycle, or display logic",
        ]
        for phrase in required:
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, text)

    def test_inventory_defines_target_side_phases(self) -> None:
        root = Path(__file__).resolve().parents[1]
        text = (root / "docs/source-wrapper-compatibility-migration.md").read_text(encoding="utf-8")
        required = [
            "Source-wrapper compatibility inventory",
            "Compatibility configuration model",
            "Wrapper planning API",
            "Wrapper rendering API",
            "Acceptance documentation",
        ]
        for phrase in required:
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, text)

    def test_inventory_keeps_current_step_inventory_only(self) -> None:
        root = Path(__file__).resolve().parents[1]
        text = (root / "docs/source-wrapper-compatibility-migration.md").read_text(encoding="utf-8")
        non_goals = [
            "no wrapper code generation",
            "no wrapper file writes",
            "no alias installation",
            "no shell rc-file changes",
            "no replacement of current source runner",
            "no download-folder mutation",
            "no export runner migration",
            "no source repository changes",
            "no compatibility command adoption",
            "no source-repository commits",
        ]
        for phrase in non_goals:
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, text)

    def test_inventory_preserves_behavior_to_plan_later(self) -> None:
        root = Path(__file__).resolve().parents[1]
        text = (root / "docs/source-wrapper-compatibility-migration.md").read_text(encoding="utf-8")
        required = [
            "repeat detection",
            "freshness and metadata checks",
            "repair the current patch before continuing",
            "done, current, next, and problem sections",
            "alias installation must write only to local shell configuration",
        ]
        for phrase in required:
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, text)

    def test_inventory_does_not_store_local_private_values(self) -> None:
        root = Path(__file__).resolve().parents[1]
        checked = [
            root / "docs/source-wrapper-compatibility-migration.md",
            root / "tests/test_source_wrapper_compatibility_inventory.py",
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
