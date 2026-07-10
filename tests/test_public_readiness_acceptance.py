from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ACCEPTANCE = ROOT / "docs" / "public-readiness-acceptance.md"
PUBLIC_API = ROOT / "docs" / "public-api-inventory.md"
PUBLIC_DOCS = ROOT / "docs" / "public-docs-inventory.md"
MIGRATION_ARTIFACTS = ROOT / "docs" / "migration-artifact-inventory.md"
CLI_DOC = ROOT / "docs" / "cli.md"
RUNNER_DOC = ROOT / "docs" / "runner.md"
COMPAT_DOC = ROOT / "docs" / "compatibility.md"

PUBLIC_DOC_PATHS = [
    "README.md",
    "docs/bootstrap.md",
    "docs/runner.md",
    "docs/compatibility.md",
    "docs/cli.md",
    "docs/public-api-inventory.md",
    "docs/public-readiness-acceptance.md",
]

MATRIX_TESTS = [
    "tests/test_public_readiness_acceptance.py",
    "tests/test_public_api_stability.py",
    "tests/test_public_api_inventory.py",
    "tests/test_cli_docs_consolidation.py",
    "tests/test_compatibility_docs_consolidation.py",
    "tests/test_runner_docs_consolidation.py",
    "tests/test_historical_migration_docs.py",
    "tests/test_public_docs_inventory.py",
    "tests/test_migration_artifact_inventory.py",
    "tests/test_packaging_acceptance.py",
]

PUBLIC_COMMANDS = [
    "doctor",
    "lint-script",
    "run-script",
    "audit-public",
    "check-env",
]


class PatchHarborPublicReadinessAcceptanceTests(unittest.TestCase):
    def read_acceptance(self) -> str:
        return ACCEPTANCE.read_text(encoding="utf-8")

    def test_public_readiness_acceptance_doc_exists(self) -> None:
        self.assertTrue(ACCEPTANCE.is_file())
        text = self.read_acceptance()
        self.assertIn("PATCHHARBOR.15c3 – Public readiness acceptance", text)
        self.assertIn("target-only", text)

    def test_acceptance_summary_lists_required_public_readiness_evidence(self) -> None:
        text = self.read_acceptance()
        expected = [
            "docs/runner.md",
            "docs/compatibility.md",
            "docs/cli.md",
            "docs/public-api-inventory.md",
            "tests/test_public_api_stability.py",
            "PATCHHARBOR.15b4 historical-migration-doc",
            "docs/public-docs-inventory.md",
            "docs/migration-artifact-inventory.md",
            "tests/test_packaging_acceptance.py",
            "RepoDossier source repository unchanged",
        ]
        for item in expected:
            with self.subTest(item=item):
                self.assertIn(item, text)

    def test_public_documentation_set_exists(self) -> None:
        text = self.read_acceptance()
        for relative in PUBLIC_DOC_PATHS:
            with self.subTest(relative=relative):
                self.assertIn(relative, text)
                self.assertTrue((ROOT / relative).is_file())

    def test_acceptance_matrix_tests_exist(self) -> None:
        text = self.read_acceptance()
        for relative in MATRIX_TESTS:
            with self.subTest(relative=relative):
                self.assertIn(relative, text)
                self.assertTrue((ROOT / relative).is_file())

    def test_public_cli_commands_are_listed_and_help_is_available(self) -> None:
        text = self.read_acceptance()
        for command in [
            "patchharbor --help",
            "patchharbor --version",
            "patchharbor doctor --repo",
            "patchharbor lint-script",
            "patchharbor run-script",
            "patchharbor audit-public",
            "patchharbor check-env",
        ]:
            with self.subTest(command=command):
                self.assertIn(command, text)

        for command in PUBLIC_COMMANDS:
            with self.subTest(command=command):
                result = subprocess.run(
                    [sys.executable, "-m", "patchharbor", command, "--help"],
                    cwd=ROOT,
                    text=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    check=False,
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn(command, result.stdout)

    def test_related_docs_link_to_public_readiness_acceptance(self) -> None:
        for path in [PUBLIC_API, PUBLIC_DOCS, MIGRATION_ARTIFACTS, CLI_DOC, RUNNER_DOC, COMPAT_DOC]:
            text = path.read_text(encoding="utf-8")
            with self.subTest(path=path):
                self.assertIn("PATCHHARBOR.15c3 applied", text)
                self.assertIn("docs/public-readiness-acceptance.md", text)

    def test_handoff_to_milestone_16_is_explicit(self) -> None:
        text = self.read_acceptance()
        self.assertIn("PATCHHARBOR.16a1 – Dual Repo Discovery Smoke", text)
        self.assertIn("dual-repository end-to-end acceptance", text)
        self.assertIn("fresh dual-repo checkouts", text)

    def test_public_readiness_non_goals_keep_runtime_and_source_unchanged(self) -> None:
        text = self.read_acceptance()
        expected = [
            "PATCHHARBOR.15c3 does not",
            "change runtime code",
            "change CLI behavior",
            "change runner behavior",
            "change compatibility behavior",
            "edit RepoDossier",
            "edit source wrappers",
            "edit source aliases",
            "delete migration artifacts",
            "change release versioning",
        ]
        for item in expected:
            with self.subTest(item=item):
                self.assertIn(item, text)

    def test_public_readiness_docs_do_not_store_private_local_values_or_fences(self) -> None:
        text = "\n".join(
            path.read_text(encoding="utf-8")
            for path in [
                ACCEPTANCE,
                PUBLIC_API,
                PUBLIC_DOCS,
                MIGRATION_ARTIFACTS,
                CLI_DOC,
                RUNNER_DOC,
                COMPAT_DOC,
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
