from __future__ import annotations

import os
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"


class PatchHarborSkeletonAcceptanceTests(unittest.TestCase):
    def test_migration_document_exists_and_sets_boundaries(self) -> None:
        text = (ROOT / "docs/migration.md").read_text(encoding="utf-8")
        self.assertIn("repository-agnostic", text)
        self.assertIn("thin wrappers", text)
        self.assertIn("Next migration step", text)
        self.assertIn("private email addresses", text)

    def test_skeleton_contains_expected_baseline_files(self) -> None:
        expected = [
            ROOT / "pyproject.toml",
            ROOT / "README.md",
            ROOT / "docs/bootstrap.md",
            ROOT / "docs/migration.md",
            ROOT / "src/patchharbor/__init__.py",
            ROOT / "src/patchharbor/__main__.py",
            ROOT / "src/patchharbor/cli.py",
            ROOT / "tests/test_cli.py",
            ROOT / "tests/test_project_metadata.py",
            ROOT / "tests/test_skeleton_acceptance.py",
        ]
        for path in expected:
            with self.subTest(path=path.relative_to(ROOT)):
                self.assertTrue(path.is_file())

    def test_doctor_smoke_accepts_repository_root(self) -> None:
        env = os.environ.copy()
        env["PYTHONPATH"] = str(SRC) + os.pathsep + env.get("PYTHONPATH", "")
        result = subprocess.run(
            [sys.executable, "-m", "patchharbor", "doctor", "--repo", str(ROOT)],
            cwd=ROOT,
            env=env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("status: ok", result.stdout)

    def test_no_tracked_baseline_file_contains_local_private_values(self) -> None:
        checked = [
            ROOT / "pyproject.toml",
            ROOT / "README.md",
            ROOT / "docs/bootstrap.md",
            ROOT / "docs/migration.md",
            ROOT / "src/patchharbor/__init__.py",
            ROOT / "src/patchharbor/__main__.py",
            ROOT / "src/patchharbor/cli.py",
            ROOT / "tests/test_cli.py",
            ROOT / "tests/test_project_metadata.py",
            ROOT / "tests/test_skeleton_acceptance.py",
        ]
        text = "\n".join(path.read_text(encoding="utf-8") for path in checked)
        forbidden = [
            "/home/" + "exampleuser",
            "user" + "@",
            "example.user" + "@" + "example.invalid",
            "Example" + "Laptop",
            "~/" + "Projects",
        ]
        for value in forbidden:
            with self.subTest(value=value):
                self.assertNotIn(value, text)
