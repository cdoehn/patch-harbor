from __future__ import annotations

import os
import re
import subprocess
import sys
import tomllib
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))


class PatchHarborPackagingMetadataTests(unittest.TestCase):
    def read_pyproject(self) -> dict:
        return tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))

    def test_build_system_and_src_layout_are_declared(self) -> None:
        data = self.read_pyproject()
        build_system = data["build-system"]
        find_config = data["tool"]["setuptools"]["packages"]["find"]

        self.assertIn("setuptools>=68", build_system["requires"])
        self.assertEqual(build_system["build-backend"], "setuptools.build_meta")
        self.assertEqual(find_config["where"], ["src"])
        self.assertEqual(find_config["include"], ["patchharbor*"])
        self.assertTrue((ROOT / "src/patchharbor/__init__.py").is_file())
        self.assertTrue((ROOT / "src/patchharbor/__main__.py").is_file())
        self.assertTrue((ROOT / "src/patchharbor/cli.py").is_file())

    def test_project_metadata_is_complete_for_distribution(self) -> None:
        data = self.read_pyproject()
        project = data["project"]

        self.assertEqual(project["name"], "patchharbor")
        self.assertRegex(project["version"], r"^\d+\.\d+\.\d+")
        self.assertIn("repository-agnostic", project["description"].lower())
        self.assertEqual(project["readme"], "README.md")
        self.assertTrue((ROOT / project["readme"]).is_file())
        self.assertEqual(project["requires-python"], ">=3.12")
        self.assertEqual(project["license"], {"text": "MIT"})
        self.assertIn({"name": "PatchHarbor contributors"}, project["authors"])
        self.assertIsInstance(project["dependencies"], list)
        self.assertIn("pytest>=7.4", project["optional-dependencies"]["dev"])

    def test_project_metadata_has_hardened_keywords_and_classifiers(self) -> None:
        project = self.read_pyproject()["project"]

        self.assertGreaterEqual(
            set(project["keywords"]),
            {"cli", "development-tools", "patch-workflow", "repository-automation"},
        )
        self.assertGreaterEqual(
            set(project["classifiers"]),
            {
                "Development Status :: 3 - Alpha",
                "Environment :: Console",
                "Intended Audience :: Developers",
                "License :: OSI Approved :: MIT License",
                "Operating System :: POSIX :: Linux",
                "Programming Language :: Python :: 3",
                "Programming Language :: Python :: 3.12",
                "Topic :: Software Development :: Build Tools",
                "Topic :: Software Development :: Quality Assurance",
            },
        )

    def test_console_and_module_entry_points_are_declared(self) -> None:
        data = self.read_pyproject()
        scripts = data["project"]["scripts"]

        self.assertEqual(scripts["patchharbor"], "patchharbor.cli:main")

        main_text = (ROOT / "src/patchharbor/__main__.py").read_text(encoding="utf-8")
        self.assertIn("from .cli import main", main_text)
        self.assertIn("raise SystemExit(main())", main_text)

    def test_import_version_matches_pyproject_version(self) -> None:
        from patchharbor import __version__

        project = self.read_pyproject()["project"]
        self.assertEqual(__version__, project["version"])

    def test_python_module_help_and_cli_version_are_available(self) -> None:
        env = os.environ.copy()
        env["PYTHONPATH"] = str(SRC) + os.pathsep + env.get("PYTHONPATH", "")

        help_result = subprocess.run(
            [sys.executable, "-m", "patchharbor", "--help"],
            cwd=ROOT,
            env=env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        version_result = subprocess.run(
            [sys.executable, "-m", "patchharbor", "--version"],
            cwd=ROOT,
            env=env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )

        self.assertEqual(help_result.returncode, 0, help_result.stderr)
        self.assertIn("usage:", help_result.stdout)
        self.assertEqual(version_result.returncode, 0, version_result.stderr)
        self.assertIn(self.read_pyproject()["project"]["version"], version_result.stdout)

    def test_packaging_metadata_files_do_not_store_private_local_values(self) -> None:
        checked = [
            ROOT / "pyproject.toml",
            ROOT / "src/patchharbor/__init__.py",
            ROOT / "src/patchharbor/__main__.py",
            ROOT / "src/patchharbor/cli.py",
            Path(__file__).resolve(),
        ]
        text = "\n".join(path.read_text(encoding="utf-8") for path in checked)
        forbidden = [
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
