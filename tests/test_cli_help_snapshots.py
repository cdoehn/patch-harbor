from __future__ import annotations

import argparse
import os
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from patchharbor.cli import build_parser


EXPECTED_SUBCOMMANDS = {"doctor", "lint-script", "run-script", "audit-public", "check-env"}
DISPLAY_ONLY_HELP_SNAPSHOT_REASON = (
    "display-only help snapshot; command-surface tests below remain active"
)


def run_patchharbor(*args: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(SRC) + os.pathsep + env.get("PYTHONPATH", "")
    return subprocess.run(
        [sys.executable, "-m", "patchharbor", *args],
        cwd=ROOT,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def subcommand_names(parser: argparse.ArgumentParser) -> set[str]:
    for action in parser._actions:
        if isinstance(action, argparse._SubParsersAction):
            return set(action.choices)
    return set()


class PatchHarborCliHelpSnapshotTests(unittest.TestCase):
    def test_parser_subcommands_match_documented_inventory(self) -> None:
        self.assertEqual(subcommand_names(build_parser()), EXPECTED_SUBCOMMANDS)

    def test_top_level_help_lists_current_functional_subcommands(self) -> None:
        result = run_patchharbor("--help")

        self.assertEqual(result.returncode, 0, result.stderr)
        for command in sorted(EXPECTED_SUBCOMMANDS):
            with self.subTest(command=command):
                self.assertIn(command, result.stdout)

    def test_module_entrypoint_help_lists_current_functional_subcommands(self) -> None:
        result = run_patchharbor("--help")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("usage:", result.stdout)
        self.assertIn("doctor", result.stdout)
        self.assertIn("run-script", result.stdout)
        self.assertIn("check-env", result.stdout)

    def test_subcommand_help_exposes_functional_options_without_freezing_layout(self) -> None:
        expectations = {
            "doctor": ["--repo"],
            "lint-script": ["path"],
            "run-script": ["--no-execute", "--lint", "--env", "--workdir"],
            "audit-public": ["--repo", "--pattern", "--target", "--encoding"],
            "check-env": ["--repo", "--no-defaults", "--command", "--file", "--git-config", "--python-module", "--optional"],
        }

        for command, markers in expectations.items():
            with self.subTest(command=command):
                result = run_patchharbor(command, "--help")
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn("usage:", result.stdout)
                for marker in markers:
                    self.assertIn(marker, result.stdout)

    def test_help_surface_is_consistent_with_inventory_and_exit_code_contract_docs(self) -> None:
        inventory = (ROOT / "docs/cli-command-inventory.md").read_text(encoding="utf-8")
        exit_contract = (ROOT / "docs/cli-exit-code-contract.md").read_text(encoding="utf-8")

        for command in EXPECTED_SUBCOMMANDS:
            with self.subTest(command=command):
                self.assertIn(f"`{command}`", inventory)
                self.assertIn(f"`{command}`", exit_contract)

        self.assertIn("Display-only tests should be skipped", exit_contract)
        self.assertIn("functional return-code categories", exit_contract)

    @unittest.skip(DISPLAY_ONLY_HELP_SNAPSHOT_REASON)
    def test_exact_top_level_help_snapshot_display_only(self) -> None:
        result = run_patchharbor("--help")
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "<display-only snapshot intentionally not enforced>")

    @unittest.skip(DISPLAY_ONLY_HELP_SNAPSHOT_REASON)
    def test_exact_subcommand_help_snapshots_display_only(self) -> None:
        for command in sorted(EXPECTED_SUBCOMMANDS):
            with self.subTest(command=command):
                result = run_patchharbor(command, "--help")
                self.assertEqual(result.returncode, 0)
                self.assertEqual(result.stdout, "<display-only snapshot intentionally not enforced>")

    def test_cli_help_snapshot_tests_do_not_store_source_specific_defaults(self) -> None:
        text = Path(__file__).read_text(encoding="utf-8")
        forbidden = [
            "Repo" + "Dossier",
            "repo" + "dossier",
            "check_dev_" + "environment.py",
            "audit_public_" + "repo.py",
            "run_latest_" + "download_patch",
            "c " + "runner",
            "r " + "runner",
            "market_" + "research",
            "/home/" + "christian",
            "christian" + "@",
            "christian.doehn" + "@" + "gmail.com",
            "Think" + "Pad",
            "Blade-" + "15",
            "~/" + "Projekte",
            chr(96) * 3,
        ]
        for value in forbidden:
            with self.subTest(value=value):
                self.assertNotIn(value, text)


if __name__ == "__main__":
    unittest.main()
