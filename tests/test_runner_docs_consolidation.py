from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNNER_DOC = ROOT / "docs" / "runner.md"
PUBLIC_DOCS_INVENTORY = ROOT / "docs" / "public-docs-inventory.md"
MIGRATION_ARTIFACT_INVENTORY = ROOT / "docs" / "migration-artifact-inventory.md"


class PatchHarborRunnerDocsConsolidationTests(unittest.TestCase):
    def read_runner(self) -> str:
        return RUNNER_DOC.read_text(encoding="utf-8")

    def test_runner_doc_exists_and_is_marked_15b1(self) -> None:
        self.assertTrue(RUNNER_DOC.is_file())
        text = self.read_runner()
        self.assertIn("PatchHarbor runner documentation", text)
        self.assertIn("PATCHHARBOR.15b1", text)
        self.assertIn("consolidated public runner contract", text)

    def test_runner_doc_lists_public_commands_and_implementation_paths(self) -> None:
        text = self.read_runner()
        expected = [
            "patchharbor run-script",
            "patchharbor lint-script",
            "patchharbor doctor --repo",
            "src/patchharbor/runner_core.py",
            "src/patchharbor/cli.py",
            "src/patchharbor/patch_lint_api.py",
            "src/patchharbor/patch_lint.py",
            "src/patchharbor/console.py",
        ]
        for item in expected:
            with self.subTest(item=item):
                self.assertIn(item, text)

    def test_runner_doc_records_lifecycle_and_compatibility_boundary(self) -> None:
        text = self.read_runner()
        expected = [
            "Runner lifecycle",
            "resolve the script path",
            "run Bash syntax checks",
            "execute the patch script",
            "preserve and report the exit code",
            "Compatibility boundary",
            "target-only patches must not edit RepoDossier source files",
            "source-only patches must not edit PatchHarbor target files",
            "Source wrapper relationship",
            "RepoDossier-specific Download handling remains",
        ]
        for item in expected:
            with self.subTest(item=item):
                self.assertIn(item, text)

    def test_runner_doc_lists_related_historical_inputs_without_deleting_them(self) -> None:
        text = self.read_runner()
        related = [
            "docs/download-runner-api-inventory.md",
            "docs/download-runner-lifecycle-plan-acceptance.md",
            "docs/runner-compatibility-acceptance.md",
            "docs/runner-compatibility-migration.md",
        ]
        for relative in related:
            with self.subTest(relative=relative):
                self.assertIn(relative, text)
                self.assertTrue((ROOT / relative).is_file())
        self.assertIn("not deleted by PATCHHARBOR.15b1", text)

    def test_public_and_migration_inventories_link_to_runner_doc(self) -> None:
        public_text = PUBLIC_DOCS_INVENTORY.read_text(encoding="utf-8")
        migration_text = MIGRATION_ARTIFACT_INVENTORY.read_text(encoding="utf-8")

        self.assertIn("PATCHHARBOR.15b1 applied", public_text)
        self.assertIn("docs/runner.md", public_text)
        self.assertIn("No migration artifact is deleted by PATCHHARBOR.15b1", public_text)

        self.assertIn("PATCHHARBOR.15b1 applied", migration_text)
        self.assertIn("docs/runner.md", migration_text)
        self.assertIn("No migration artifact is deleted by PATCHHARBOR.15b1", migration_text)

    def test_runner_doc_points_to_next_consolidation_steps(self) -> None:
        text = self.read_runner()
        expected = [
            "PATCHHARBOR.15b2",
            "PATCHHARBOR.15b3",
            "PATCHHARBOR.15b4",
            "Compatibility docs are consolidated",
            "CLI docs are consolidated",
            "Historical migration docs are marked historical",
        ]
        for item in expected:
            with self.subTest(item=item):
                self.assertIn(item, text)

    def test_runner_doc_does_not_store_private_local_values_or_fences(self) -> None:
        text = "\n".join(
            path.read_text(encoding="utf-8")
            for path in [RUNNER_DOC, PUBLIC_DOCS_INVENTORY, MIGRATION_ARTIFACT_INVENTORY, Path(__file__).resolve()]
        )
        forbidden = [
            "/home/" + "christian",
            "christian" + "@",
            "christian.doehn" + "@" + "gmail.com",
            "Think" + "Pad",
            "Blade-" + "15",
            "~/" + "Projekte",
        ]
        for value in forbidden:
            with self.subTest(value=value):
                self.assertNotIn(value, text)
        self.assertNotIn(chr(96) * 3, text)


if __name__ == "__main__":
    unittest.main()
