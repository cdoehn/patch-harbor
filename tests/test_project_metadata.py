from __future__ import annotations

import tomllib
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class PatchHarborProjectMetadataTests(unittest.TestCase):
    def read_pyproject(self) -> dict:
        return tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))

    def test_project_name_and_package_layout(self) -> None:
        data = self.read_pyproject()
        self.assertEqual(data["project"]["name"], "patchharbor")
        self.assertEqual(data["project"]["readme"], "README.md")
        self.assertTrue((ROOT / "src/patchharbor/__init__.py").is_file())
        self.assertTrue((ROOT / "src/patchharbor/__main__.py").is_file())
        self.assertTrue((ROOT / "src/patchharbor/cli.py").is_file())

    def test_patchharbor_console_script_is_declared(self) -> None:
        data = self.read_pyproject()
        scripts = data["project"].get("scripts", {})
        self.assertEqual(scripts.get("patchharbor"), "patchharbor.cli:main")

    def test_dev_extra_keeps_pytest_available_for_later(self) -> None:
        data = self.read_pyproject()
        dev = data["project"].get("optional-dependencies", {}).get("dev", [])
        self.assertIn("pytest>=7.4", dev)

    def test_repository_files_do_not_store_local_private_values(self) -> None:
        checked = [
            ROOT / "pyproject.toml",
            ROOT / "README.md",
            ROOT / "src/patchharbor/__init__.py",
            ROOT / "src/patchharbor/__main__.py",
            ROOT / "src/patchharbor/cli.py",
            ROOT / "tests/test_cli.py",
            ROOT / "tests/test_project_metadata.py",
        ]
        text = "\n".join(path.read_text(encoding="utf-8") for path in checked)
        forbidden = [
            "/home/" + "christian",
            "christian" + "@",
            "christian.doehn" + "@" + "gmail.com",
            "Think" + "Pad",
            "~/" + "Projekte",
        ]
        for value in forbidden:
            with self.subTest(value=value):
                self.assertNotIn(value, text)
