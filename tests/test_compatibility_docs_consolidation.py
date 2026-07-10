from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMPAT_DOC = ROOT / "docs" / "compatibility.md"
RUNNER_DOC = ROOT / "docs" / "runner.md"
PUBLIC_DOCS_INVENTORY = ROOT / "docs" / "public-docs-inventory.md"
MIGRATION_ARTIFACT_INVENTORY = ROOT / "docs" / "migration-artifact-inventory.md"


class PatchHarborCompatibilityDocsConsolidationTests(unittest.TestCase):
    def read_compat(self) -> str:
        return COMPAT_DOC.read_text(encoding="utf-8")

    def test_compatibility_doc_exists_and_is_marked_15b2(self) -> None:
        self.assertTrue(COMPAT_DOC.is_file())
        text = self.read_compat()
        self.assertIn("PatchHarbor compatibility documentation", text)
        self.assertIn("PATCHHARBOR.15b2", text)
        self.assertIn("consolidated public compatibility contract", text)

    def test_compatibility_doc_lists_current_surfaces(self) -> None:
        text = self.read_compat()
        expected = [
            "source wrapper compatibility",
            "source-side adoption compatibility",
            "workflow-rule compatibility",
            "alias compatibility",
            "runner compatibility",
            "CLI compatibility",
            "active compatibility contract",
        ]
        for item in expected:
            with self.subTest(item=item):
                self.assertIn(item, text)

    def test_compatibility_doc_records_source_wrapper_and_alias_boundaries(self) -> None:
        text = self.read_compat()
        expected = [
            "PatchHarbor owns generic patch infrastructure",
            "RepoDossier owns product-specific Download and export workflows",
            "Target-only patches must leave source wrappers unchanged",
            "Source-only patches must leave target package code unchanged",
            "PatchHarbor target patches must not edit shell rc files or source alias installers",
            "`c` is a RepoDossier source alias",
            "`r` is a RepoDossier source alias",
        ]
        for item in expected:
            with self.subTest(item=item):
                self.assertIn(item, text)

    def test_compatibility_doc_lists_related_inputs_without_deleting_them(self) -> None:
        text = self.read_compat()
        related = [
            "docs/source-wrapper-compatibility-acceptance.md",
            "docs/source-wrapper-compatibility-migration.md",
            "docs/source-side-adoption-acceptance.md",
            "docs/source-side-adoption-inventory.md",
            "docs/source-side-adoption-preflight-inventory.md",
            "docs/source-side-alias-compatibility-plan.md",
            "docs/workflow-rules-acceptance.md",
        ]
        for relative in related:
            with self.subTest(relative=relative):
                self.assertIn(relative, text)
                self.assertTrue((ROOT / relative).is_file())

    def test_compatibility_doc_links_runner_and_cli_consolidation_boundaries(self) -> None:
        text = self.read_compat()
        expected = [
            "docs/runner.md",
            "PATCHHARBOR.15b3",
            "CLI docs are consolidated by PATCHHARBOR.15b3",
            "Historical migration docs are marked historical by PATCHHARBOR.15b4",
        ]
        for item in expected:
            with self.subTest(item=item):
                self.assertIn(item, text)

    def test_public_migration_and_runner_docs_link_to_compatibility_doc(self) -> None:
        public_text = PUBLIC_DOCS_INVENTORY.read_text(encoding="utf-8")
        migration_text = MIGRATION_ARTIFACT_INVENTORY.read_text(encoding="utf-8")
        runner_text = RUNNER_DOC.read_text(encoding="utf-8")

        self.assertIn("PATCHHARBOR.15b2 applied", public_text)
        self.assertIn("docs/compatibility.md", public_text)
        self.assertIn("No migration artifact is deleted by PATCHHARBOR.15b2", public_text)

        self.assertIn("PATCHHARBOR.15b2 applied", migration_text)
        self.assertIn("docs/compatibility.md", migration_text)
        self.assertIn("No migration artifact is deleted by PATCHHARBOR.15b2", migration_text)

        self.assertIn("PATCHHARBOR.15b2 applied", runner_text)
        self.assertIn("docs/compatibility.md", runner_text)

    def test_compatibility_doc_does_not_store_private_local_values_or_fences(self) -> None:
        text = "\n".join(
            path.read_text(encoding="utf-8")
            for path in [COMPAT_DOC, PUBLIC_DOCS_INVENTORY, MIGRATION_ARTIFACT_INVENTORY, RUNNER_DOC, Path(__file__).resolve()]
        )
        forbidden = [
            "/home/" + "exampleuser",
            "user" + "@",
            "example.user" + "@" + "example.invalid",
            "Example" + "Laptop",
            "Example" + "Machine",
            "~/" + "Projects",
        ]
        for value in forbidden:
            with self.subTest(value=value):
                self.assertNotIn(value, text)
        self.assertNotIn(chr(96) * 3, text)


if __name__ == "__main__":
    unittest.main()
