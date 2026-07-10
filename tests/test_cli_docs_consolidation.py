from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CLI_DOC = ROOT / "docs" / "cli.md"
RUNNER_DOC = ROOT / "docs" / "runner.md"
COMPAT_DOC = ROOT / "docs" / "compatibility.md"
PUBLIC_DOCS_INVENTORY = ROOT / "docs" / "public-docs-inventory.md"
MIGRATION_ARTIFACT_INVENTORY = ROOT / "docs" / "migration-artifact-inventory.md"


class PatchHarborCliDocsConsolidationTests(unittest.TestCase):
    def read_cli(self) -> str:
        return CLI_DOC.read_text(encoding="utf-8")

    def test_cli_doc_exists_and_is_marked_15b3(self) -> None:
        self.assertTrue(CLI_DOC.is_file())
        text = self.read_cli()
        self.assertIn("PatchHarbor CLI documentation", text)
        self.assertIn("PATCHHARBOR.15b3", text)
        self.assertIn("consolidated public CLI contract", text)

    def test_cli_doc_lists_public_commands(self) -> None:
        text = self.read_cli()
        expected = [
            "patchharbor --help",
            "patchharbor --version",
            "patchharbor doctor --repo",
            "patchharbor lint-script",
            "patchharbor run-script",
            "patchharbor audit-public",
            "patchharbor check-env",
            "patchharbor rules",
        ]
        for item in expected:
            with self.subTest(item=item):
                self.assertIn(item, text)

    def test_cli_doc_records_examples_and_exit_codes(self) -> None:
        text = self.read_cli()
        expected = [
            "Command examples",
            "patchharbor doctor --repo .",
            "patchharbor lint-script ./example_patch.sh",
            "patchharbor run-script ./example_patch.sh",
            "patchharbor audit-public --repo .",
            "patchharbor check-env --repo .",
            "Exit-code contract",
            "| 0 | success |",
            "| 10 | metadata or validation failure |",
            "| 20 | patch lint or preflight failure |",
        ]
        for item in expected:
            with self.subTest(item=item):
                self.assertIn(item, text)

    def test_cli_doc_links_runner_lint_compatibility_and_packaging_docs(self) -> None:
        text = self.read_cli()
        related = [
            "docs/runner.md",
            "docs/patch-linting-acceptance.md",
            "docs/compatibility.md",
            "docs/packaging-acceptance.md",
            "docs/cli-command-inventory.md",
            "docs/cli-exit-code-contract.md",
        ]
        for relative in related:
            with self.subTest(relative=relative):
                self.assertIn(relative, text)
                self.assertTrue((ROOT / relative).is_file())

    def test_cli_doc_records_help_output_stability_and_non_goals(self) -> None:
        text = self.read_cli()
        expected = [
            "Help-output contract",
            "top-level help lists public subcommands",
            "help snapshot tests remain the guard",
            "PATCHHARBOR.15b3 does not",
            "change CLI implementation",
            "change runner implementation",
            "edit RepoDossier",
            "Historical migration docs are marked historical by PATCHHARBOR.15b4",
        ]
        for item in expected:
            with self.subTest(item=item):
                self.assertIn(item, text)

    def test_related_docs_link_to_cli_doc(self) -> None:
        public_text = PUBLIC_DOCS_INVENTORY.read_text(encoding="utf-8")
        migration_text = MIGRATION_ARTIFACT_INVENTORY.read_text(encoding="utf-8")
        runner_text = RUNNER_DOC.read_text(encoding="utf-8")
        compat_text = COMPAT_DOC.read_text(encoding="utf-8")

        for text in [public_text, migration_text, runner_text, compat_text]:
            with self.subTest(text=text[:40]):
                self.assertIn("PATCHHARBOR.15b3 applied", text)
                self.assertIn("docs/cli.md", text)

        self.assertIn("No migration artifact is deleted by PATCHHARBOR.15b3", public_text)
        self.assertIn("No migration artifact is deleted by PATCHHARBOR.15b3", migration_text)

    def test_cli_doc_does_not_store_private_local_values_or_fences(self) -> None:
        text = "\n".join(
            path.read_text(encoding="utf-8")
            for path in [CLI_DOC, PUBLIC_DOCS_INVENTORY, MIGRATION_ARTIFACT_INVENTORY, RUNNER_DOC, COMPAT_DOC, Path(__file__).resolve()]
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
