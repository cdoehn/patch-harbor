from __future__ import annotations

from pathlib import Path
import unittest


class PatchHarborSourceSideAdoptionInventoryTests(unittest.TestCase):
    def test_source_side_adoption_inventory_document_exists(self) -> None:
        root = Path(__file__).resolve().parents[1]
        path = root / "docs/source-side-adoption-inventory.md"
        self.assertTrue(path.exists())
        text = path.read_text(encoding="utf-8")
        self.assertIn("PatchHarbor.08 source-side adoption inventory", text)
        self.assertIn("This step is inventory-only", text)

    def test_inventory_lists_adoption_candidates(self) -> None:
        root = Path(__file__).resolve().parents[1]
        text = (root / "docs/source-side-adoption-inventory.md").read_text(encoding="utf-8")
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

    def test_inventory_defines_readiness_and_deferred_work(self) -> None:
        root = Path(__file__).resolve().parents[1]
        text = (root / "docs/source-side-adoption-inventory.md").read_text(encoding="utf-8")
        required = [
            "Ready for dry-run planning",
            "Not ready for mutation yet",
            "Deferred",
            "export runner migration",
            "public audit helper migration",
            "development-environment helper migration",
        ]
        for phrase in required:
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, text)

    def test_inventory_defines_risk_checklist(self) -> None:
        root = Path(__file__).resolve().parents[1]
        text = (root / "docs/source-side-adoption-inventory.md").read_text(encoding="utf-8")
        required = [
            "Which source files are touched?",
            "Is the patch reversible?",
            "Does the old convenience workflow still work?",
            "Are download success and failure paths preserved?",
            "Does repeat detection still stop accidental re-runs?",
            "Does the patch run focused source-side tests before a full suite?",
        ]
        for phrase in required:
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, text)

    def test_inventory_defines_patchharbor_08_sequence(self) -> None:
        root = Path(__file__).resolve().parents[1]
        text = (root / "docs/source-side-adoption-inventory.md").read_text(encoding="utf-8")
        required = [
            "Source-side adoption inventory",
            "Source-side runner wrapper draft",
            "Source-side alias compatibility update plan",
            "Source-side runner compatibility tests",
            "Source-side adoption acceptance documentation",
        ]
        for phrase in required:
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, text)

    def test_inventory_keeps_current_step_non_mutating(self) -> None:
        root = Path(__file__).resolve().parents[1]
        text = (root / "docs/source-side-adoption-inventory.md").read_text(encoding="utf-8")
        non_goals = [
            "no RepoDossier file changes",
            "no source repository commits",
            "no wrapper file writes",
            "no alias installation",
            "no shell rc-file changes",
            "no download-folder mutation",
            "no export runner migration",
            "no deletion of old source scripts",
            "no compatibility command adoption",
            "no automatic replacement of local workflows",
        ]
        for phrase in non_goals:
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, text)

    def test_inventory_files_do_not_store_private_local_values(self) -> None:
        root = Path(__file__).resolve().parents[1]
        checked = [
            root / "docs/source-side-adoption-inventory.md",
            root / "tests/test_source_side_adoption_inventory.py",
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
