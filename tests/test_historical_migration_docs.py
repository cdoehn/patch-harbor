from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PUBLIC_DOCS_INVENTORY = ROOT / "docs" / "public-docs-inventory.md"
MIGRATION_ARTIFACT_INVENTORY = ROOT / "docs" / "migration-artifact-inventory.md"
RUNNER_DOC = ROOT / "docs" / "runner.md"
COMPAT_DOC = ROOT / "docs" / "compatibility.md"
CLI_DOC = ROOT / "docs" / "cli.md"

HISTORICAL_DOCS = [
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
    "docs/extraction-03.md",
]


class PatchHarborHistoricalMigrationDocsTests(unittest.TestCase):
    def test_historical_docs_are_marked_not_deleted(self) -> None:
        for relative in HISTORICAL_DOCS:
            path = ROOT / relative
            if not path.exists() and relative == "docs/extraction-03.md":
                continue
            with self.subTest(relative=relative):
                self.assertTrue(path.is_file())
                text = path.read_text(encoding="utf-8")
                self.assertIn("PATCHHARBOR.15b4 historical-migration-doc", text)
                self.assertIn("Historical migration document.", text)
                self.assertIn("not the current public command contract", text)
                self.assertIn("docs/runner.md", text)
                self.assertIn("docs/compatibility.md", text)
                self.assertIn("docs/cli.md", text)

    def test_current_public_contract_docs_remain_unmarked_as_historical(self) -> None:
        current_docs = [RUNNER_DOC, COMPAT_DOC, CLI_DOC]
        for path in current_docs:
            with self.subTest(path=path):
                text = path.read_text(encoding="utf-8")
                self.assertNotIn("PATCHHARBOR.15b4 historical-migration-doc", text)
                self.assertIn("PATCHHARBOR.15b4 applied", text)

    def test_inventories_record_15b4_historical_marking(self) -> None:
        public_text = PUBLIC_DOCS_INVENTORY.read_text(encoding="utf-8")
        migration_text = MIGRATION_ARTIFACT_INVENTORY.read_text(encoding="utf-8")

        for text in [public_text, migration_text]:
            with self.subTest(text=text[:40]):
                self.assertIn("PATCHHARBOR.15b4 applied", text)
                self.assertIn("PATCHHARBOR.15b4 historical-migration-doc", text)

        self.assertIn("No migration artifact is deleted by PATCHHARBOR.15b4", public_text)
        self.assertIn("not deleted", migration_text)

    def test_public_docs_inventory_no_longer_uses_future_15b4_language(self) -> None:
        text = PUBLIC_DOCS_INVENTORY.read_text(encoding="utf-8")
        forbidden = [
            "mark historical in PATCHHARBOR.15b4",
            "mark historical after compatibility docs are consolidated",
            "mark historical after runner docs are consolidated",
        ]
        for marker in forbidden:
            with self.subTest(marker=marker):
                self.assertNotIn(marker, text)
        self.assertIn("marked historical by PATCHHARBOR.15b4", text)

    def test_historical_marking_does_not_store_private_local_values_or_fences_in_new_test_or_inventories(self) -> None:
        text = "\n".join(
            path.read_text(encoding="utf-8")
            for path in [
                PUBLIC_DOCS_INVENTORY,
                MIGRATION_ARTIFACT_INVENTORY,
                RUNNER_DOC,
                COMPAT_DOC,
                CLI_DOC,
                Path(__file__).resolve(),
            ]
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
