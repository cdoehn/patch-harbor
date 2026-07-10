from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INVENTORY = ROOT / "docs" / "migration-artifact-inventory.md"


class PatchHarborMigrationArtifactInventoryTests(unittest.TestCase):
    def read_inventory(self) -> str:
        return INVENTORY.read_text(encoding="utf-8")

    def test_inventory_document_exists(self) -> None:
        self.assertTrue(INVENTORY.is_file())
        text = self.read_inventory()
        self.assertIn("PATCHHARBOR.15a1 – Migration artifact inventory", text)
        self.assertIn("target-only", text)

    def test_inventory_lists_migration_documents(self) -> None:
        text = self.read_inventory()
        expected = [
            "docs/migration.md",
            "docs/dev-script-inventory.md",
            "docs/workflow-rules-migration.md",
            "docs/patch-linting-migration.md",
            "docs/runner-compatibility-migration.md",
            "docs/source-side-adoption-inventory.md",
            "docs/source-side-adoption-preflight-inventory.md",
            "docs/source-side-runner-wrapper-draft.md",
            "docs/source-wrapper-compatibility-migration.md",
        ]
        for item in expected:
            with self.subTest(item=item):
                self.assertIn(item, text)

    def test_inventory_lists_active_public_and_compatibility_contracts(self) -> None:
        text = self.read_inventory()
        expected = [
            "docs/cli-command-inventory.md",
            "docs/cli-exit-code-contract.md",
            "docs/patch-linting-acceptance.md",
            "docs/runner-compatibility-acceptance.md",
            "docs/source-wrapper-compatibility-acceptance.md",
            "docs/packaging-acceptance.md",
            "active public contract",
            "active compatibility contract",
            "acceptance guard",
        ]
        for item in expected:
            with self.subTest(item=item):
                self.assertIn(item, text)

    def test_inventory_lists_migration_and_acceptance_tests(self) -> None:
        text = self.read_inventory()
        expected = [
            "tests/test_dev_script_inventory.py",
            "tests/test_workflow_rules_inventory.py",
            "tests/test_patch_linting_inventory.py",
            "tests/test_runner_compatibility_inventory.py",
            "tests/test_source_side_adoption_inventory.py",
            "tests/test_source_side_runner_wrapper_draft.py",
            "tests/test_cli_help_snapshots.py",
            "tests/test_cli.py",
            "tests/test_packaging_acceptance.py",
        ]
        for item in expected:
            with self.subTest(item=item):
                self.assertIn(item, text)

    def test_inventory_defines_classification_and_deletion_gate(self) -> None:
        text = self.read_inventory()
        expected = [
            "Classification rules",
            "historical migration record",
            "bridge artifact",
            "removal candidate",
            "Deletion gate",
            "No migration artifact is deleted by PATCHHARBOR.15a1",
            "source repository state remains unchanged for target-only cleanup patches",
        ]
        for item in expected:
            with self.subTest(item=item):
                self.assertIn(item, text)

    def test_inventory_points_to_next_public_readiness_steps(self) -> None:
        text = self.read_inventory()
        expected = [
            "PATCHHARBOR.15a2 inventories public docs",
            "PATCHHARBOR.15b consolidates runner, compatibility, and CLI docs",
            "PATCHHARBOR.15c records public API and public-readiness acceptance",
        ]
        for item in expected:
            with self.subTest(item=item):
                self.assertIn(item, text)

    def test_inventory_referenced_paths_exist_for_current_docs_and_tests(self) -> None:
        text = self.read_inventory()
        required_existing_paths = [
            "docs/migration.md",
            "docs/dev-script-inventory.md",
            "docs/patch-linting-acceptance.md",
            "docs/runner-compatibility-acceptance.md",
            "docs/source-wrapper-compatibility-acceptance.md",
            "docs/packaging-acceptance.md",
            "tests/test_dev_script_inventory.py",
            "tests/test_patch_linting_acceptance.py",
            "tests/test_runner_compatibility_acceptance.py",
            "tests/test_source_wrapper_compatibility_acceptance.py",
            "tests/test_packaging_acceptance.py",
        ]
        for relative in required_existing_paths:
            with self.subTest(relative=relative):
                self.assertIn(relative, text)
                self.assertTrue((ROOT / relative).is_file())

    def test_inventory_does_not_store_private_local_values_or_fences(self) -> None:
        text = "\n".join(
            path.read_text(encoding="utf-8")
            for path in [INVENTORY, Path(__file__).resolve()]
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
