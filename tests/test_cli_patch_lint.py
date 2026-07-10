from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from patchharbor.cli import build_parser, main


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


def write_script(directory: Path, text: str, name: str = "patch.sh") -> Path:
    path = directory / name
    path.write_text(text, encoding="utf-8")
    return path


CLEAN_PATCH_SCRIPT = """#!/usr/bin/env bash
set -euo pipefail

print_footer() {
  echo done
}
trap print_footer EXIT

python3 -m compileall src tests
git --no-pager diff
"""


class PatchHarborPatchLintCliTests(unittest.TestCase):
    def test_parser_exposes_lint_script_subcommand(self) -> None:
        help_text = build_parser().format_help()
        self.assertIn("lint-script", help_text)
        self.assertIn("doctor", help_text)

    def test_lint_script_clean_file_exits_zero(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = write_script(Path(tmp), CLEAN_PATCH_SCRIPT)
            result = run_patchharbor("lint-script", str(path))

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("PatchHarbor lint-script", result.stdout)
        self.assertIn("status: ok", result.stdout)

    def test_lint_script_findings_exit_one_and_print_findings(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = write_script(Path(tmp), "git diff\n")
            result = run_patchharbor("lint-script", str(path))

        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn("status: warning", result.stdout)
        self.assertIn("patch.git_no_pager", result.stdout)
        self.assertIn("patch.footer", result.stdout)
        self.assertIn("patch.tests", result.stdout)

    def test_lint_script_missing_file_exits_two(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "missing.sh"
            result = run_patchharbor("lint-script", str(path))

        self.assertEqual(result.returncode, 2)
        self.assertIn("status: error", result.stdout)
        self.assertIn("problem:", result.stdout)

    def test_main_lint_script_accepts_file_directly(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = write_script(Path(tmp), CLEAN_PATCH_SCRIPT)
            self.assertEqual(main(["lint-script", str(path)]), 0)

    def test_module_help_includes_lint_script(self) -> None:
        result = run_patchharbor("--help")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("lint-script", result.stdout)

    def test_cli_patch_lint_files_do_not_store_local_private_values(self) -> None:
        checked = [
            ROOT / "src/patchharbor/cli.py",
            ROOT / "tests/test_cli_patch_lint.py",
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
