from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INVENTORY = ROOT / "docs" / "public-docs-inventory.md"
MIGRATION_INVENTORY = ROOT / "docs" / "migration-artifact-inventory.md"


class PatchHarborPublicDocsInventoryTests(unittest.TestCase):
    def read_inventory(self) -> str:
        return INVENTORY.read_text(encoding="utf-8")

    def test_inventory_document_exists(self) -> None:
        self.assertTrue(INVENTORY.is_file())
        text = self.read_inventory()
        self.assertIn("PATCHHARBOR.15a2 – Public docs inventory", text)
        self.assertIn("target-only", text)

    def test_inventory_lists_public_document_classes(self) -> None:
        text = self.read_inventory()
        expected = [
            "public entry point",
            "public CLI contract",
            "public runner contract",
            "public lint contract",
            "public compatibility contract",
            "packaging contract",
            "historical migration document",
            "public-readiness inventory",
        ]
        for item in expected:
            with self.subTest(item=item):
                self.assertIn(item, text)

    def test_inventory_lists_public_docs(self) -> None:
        text = self.read_inventory()
        expected = [
            "README.md",
            "docs/bootstrap.md",
            "docs/cli-command-inventory.md",
            "docs/cli-exit-code-contract.md",
            "docs/patch-linting-acceptance.md",
            "docs/runner-compatibility-acceptance.md",
            "docs/source-wrapper-compatibility-acceptance.md",
            "docs/source-side-adoption-acceptance.md",
            "docs/workflow-rules-acceptance.md",
            "docs/packaging-acceptance.md",
            "docs/download-runner-api-inventory.md",
            "docs/download-runner-lifecycle-plan-acceptance.md",
        ]
        for item in expected:
            with self.subTest(item=item):
                self.assertIn(item, text)
                self.assertTrue((ROOT / item).is_file())

    def test_inventory_lists_historical_docs(self) -> None:
        text = self.read_inventory()
        expected = [
            "docs/migration.md",
            "docs/dev-script-inventory.md",
            "docs/workflow-rules-migration.md",
            "docs/patch-linting-migration.md",
            "docs/runner-compatibility-migration.md",
            "docs/source-wrapper-compatibility-migration.md",
            "docs/source-side-adoption-inventory.md",
            "docs/source-side-adoption-preflight-inventory.md",
            "docs/source-side-alias-compatibility-plan.md",
            "docs/source-side-runner-compatibility-tests.md",
            "docs/source-side-runner-wrapper-draft.md",
        ]
        for item in expected:
            with self.subTest(item=item):
                self.assertIn(item, text)
                self.assertTrue((ROOT / item).is_file())

    def test_inventory_records_15b_consolidation_order(self) -> None:
        text = self.read_inventory()
        expected = [
            "PATCHHARBOR.15b1 consolidates runner docs",
            "PATCHHARBOR.15b2 consolidates compatibility docs",
            "PATCHHARBOR.15b3 consolidates CLI docs",
            "PATCHHARBOR.15b4 marks migration docs historical",
        ]
        for item in expected:
            with self.subTest(item=item):
                self.assertIn(item, text)

        positions = [
            text.index("PATCHHARBOR.15b1"),
            text.index("PATCHHARBOR.15b2"),
            text.index("PATCHHARBOR.15b3"),
            text.index("PATCHHARBOR.15b4"),
        ]
        self.assertEqual(positions, sorted(positions))

    def test_inventory_defines_public_docs_acceptance_gates_and_non_goals(self) -> None:
        text = self.read_inventory()
        expected = [
            "Public docs acceptance gates",
            "README is the public entry point",
            "CLI command names and exit codes",
            "runner behavior",
            "compatibility behavior",
            "migration documents are clearly historical",
            "target-only docs patches leave the source repository unchanged",
            "PATCHHARBOR.15a2 does not",
            "delete migration docs",
            "change CLI behavior",
            "modify RepoDossier",
        ]
        for item in expected:
            with self.subTest(item=item):
                self.assertIn(item, text)

    def test_migration_artifact_inventory_links_to_public_docs_inventory(self) -> None:
        text = MIGRATION_INVENTORY.read_text(encoding="utf-8")
        self.assertIn("PATCHHARBOR.15a2 applied", text)
        self.assertIn("docs/public-docs-inventory.md", text)
        self.assertIn("No migration artifact is deleted by PATCHHARBOR.15a2", text)

    def test_public_docs_inventory_does_not_store_private_local_values_or_fences(self) -> None:
        text = "\n".join(
            path.read_text(encoding="utf-8")
            for path in [INVENTORY, MIGRATION_INVENTORY, Path(__file__).resolve()]
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
