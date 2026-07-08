from __future__ import annotations

import os
import subprocess
import sys
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


class PatchHarborCliTests(unittest.TestCase):
    def test_parser_exposes_doctor_subcommand(self) -> None:
        parser = build_parser()
        help_text = parser.format_help()
        self.assertIn("patchharbor", help_text)
        self.assertIn("doctor", help_text)

    def test_main_without_command_prints_help(self) -> None:
        self.assertEqual(main([]), 0)

    def test_module_help_exits_zero(self) -> None:
        result = run_patchharbor("--help")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("patchharbor", result.stdout)
        self.assertIn("doctor", result.stdout)

    def test_module_version_exits_zero(self) -> None:
        result = run_patchharbor("--version")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("patchharbor", result.stdout)

    def test_doctor_accepts_target_git_repo(self) -> None:
        result = run_patchharbor("doctor", "--repo", str(ROOT))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("status: ok", result.stdout)

    def test_doctor_rejects_missing_repo(self) -> None:
        missing = ROOT / ".patchharbor-missing-test-repo"
        result = run_patchharbor("doctor", "--repo", str(missing))
        self.assertEqual(result.returncode, 1)
        self.assertIn("status: error", result.stdout)
