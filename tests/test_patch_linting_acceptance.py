from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from patchharbor.patch_lint_api import lint_patch_file, lint_patch_text, render_patch_lint_result
from patchharbor.patch_lint_rules import RULE_GIT_NO_PAGER, lint_git_pager_commands
from patchharbor.shell_scan import ShellCodeLine, iter_shell_code_lines_outside_heredocs

ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / "docs/patch-linting-acceptance.md"
SRC = ROOT / "src"


CLEAN_PATCH_SCRIPT = """#!/usr/bin/env bash
set -euo pipefail

print_footer() {
  echo done
}
trap print_footer EXIT

python3 -m compileall src tests
git --no-pager diff
"""


class PatchHarborPatchLintingAcceptanceTests(unittest.TestCase):
    def test_acceptance_document_exists_and_sets_boundaries(self) -> None:
        text = DOC.read_text(encoding="utf-8")
        self.assertIn("PatchHarbor.05 patch-script linting acceptance", text)
        self.assertIn("Accepted scope", text)
        self.assertIn("Explicit non-goals", text)
        self.assertIn("RepoDossier remains unchanged", text)

    def test_phase_components_are_present(self) -> None:
        expected = [
            ROOT / "docs/patch-linting-migration.md",
            ROOT / "src/patchharbor/patch_lint.py",
            ROOT / "tests/test_patch_lint.py",
            ROOT / "src/patchharbor/shell_scan.py",
            ROOT / "tests/test_shell_scan.py",
            ROOT / "src/patchharbor/patch_lint_rules.py",
            ROOT / "tests/test_patch_lint_rules.py",
            ROOT / "src/patchharbor/patch_lint_api.py",
            ROOT / "tests/test_patch_lint_api.py",
            ROOT / "src/patchharbor/cli.py",
            ROOT / "tests/test_cli_patch_lint.py",
        ]
        for path in expected:
            with self.subTest(path=path.relative_to(ROOT)):
                self.assertTrue(path.is_file())

    def test_phase_detects_git_pager_cases_from_acceptance_matrix(self) -> None:
        text = (
            "git diff\n"
            "git log --oneline\n"
            "if git log --oneline; then\n"
            "while git diff --check; do\n"
            "echo ok; git diff\n"
            "true && git log\n"
            "false || git diff\n"
            "git --no-pager diff\n"
            "GIT_PAGER=cat git log\n"
            "# git diff\n"
            "echo 'git log'\n"
            "cat <<EOF\n"
            "git diff\n"
            "EOF\n"
        )
        result = lint_git_pager_commands(text)
        self.assertEqual(len(result.findings), 7)
        self.assertEqual({finding.rule_id for finding in result.findings}, {RULE_GIT_NO_PAGER})

    def test_phase_lint_api_detects_findings_and_renders_status(self) -> None:
        result = lint_patch_text("git diff\n")
        rendered = render_patch_lint_result(result)
        self.assertEqual(rendered[0], "status: warning")
        self.assertTrue(any("patch.git_no_pager" in line for line in rendered))
        self.assertTrue(any("patch.footer" in line for line in rendered))
        self.assertTrue(any("patch.tests" in line for line in rendered))

    def test_phase_lint_api_accepts_clean_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "clean.sh"
            path.write_text(CLEAN_PATCH_SCRIPT, encoding="utf-8")
            result = lint_patch_file(path)
        self.assertEqual(render_patch_lint_result(result), ("status: ok",))

    def test_phase_shell_scanner_skips_heredoc_payload(self) -> None:
        text = "cat <<EOF\nhidden git diff\nEOF\ngit --no-pager diff\n"
        self.assertEqual(
            iter_shell_code_lines_outside_heredocs(text),
            (
                ShellCodeLine(1, "cat <<EOF"),
                ShellCodeLine(4, "git --no-pager diff"),
            ),
        )

    def test_phase_cli_lint_script_is_available(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "clean.sh"
            path.write_text(CLEAN_PATCH_SCRIPT, encoding="utf-8")

            env = os.environ.copy()
            env["PYTHONPATH"] = str(SRC) + os.pathsep + env.get("PYTHONPATH", "")
            result = subprocess.run(
                [sys.executable, "-m", "patchharbor", "lint-script", str(path)],
                cwd=ROOT,
                env=env,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("PatchHarbor lint-script", result.stdout)
        self.assertIn("status: ok", result.stdout)

    def test_acceptance_document_keeps_runner_integration_out_of_scope(self) -> None:
        text = DOC.read_text(encoding="utf-8")
        expected = [
            "download patch runner",
            "`c` workflow",
            "automatic patch execution",
            "source-repository wrappers",
            "later phases",
        ]
        for item in expected:
            with self.subTest(item=item):
                self.assertIn(item, text)

    def test_acceptance_files_do_not_store_local_private_values(self) -> None:
        checked = [
            DOC,
            ROOT / "tests/test_patch_linting_acceptance.py",
        ]
        text = "\n".join(path.read_text(encoding="utf-8") for path in checked)
        forbidden = [
            "/home/" + "exampleuser",
            "user" + "@",
            "example.user" + "@" + "example.invalid",
            "Example" + "Laptop",
            "~/" + "Projects",
            chr(96) * 3,
        ]
        for value in forbidden:
            with self.subTest(value=value):
                self.assertNotIn(value, text)
