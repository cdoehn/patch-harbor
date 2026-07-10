from __future__ import annotations

import os
import subprocess
import sys
import tomllib
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
ACCEPTANCE = ROOT / "docs/packaging-acceptance.md"
SMOKE = ROOT / "scripts/smoke_pipx_install.sh"


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


class PatchHarborPackagingAcceptanceTests(unittest.TestCase):
    def acceptance_text(self) -> str:
        return ACCEPTANCE.read_text(encoding="utf-8")

    def pyproject(self) -> dict:
        return tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))

    def test_packaging_acceptance_document_links_predecessor_contracts(self) -> None:
        text = self.acceptance_text()

        required = [
            "PATCHHARBOR.13b4 – Packaging Acceptance",
            "PATCHHARBOR.13b1",
            "PATCHHARBOR.13b2",
            "PATCHHARBOR.13b3",
            "Harden PatchHarbor pyproject metadata",
            "Document PatchHarbor installation",
            "Add pipx smoke script",
            "PATCHHARBOR.14a1 – RepoDossier Script Cleanup Inventory",
        ]
        missing = [marker for marker in required if marker not in text]
        self.assertFalse(missing, missing)

    def test_acceptance_gates_match_current_packaging_files(self) -> None:
        text = self.acceptance_text()
        project = self.pyproject()["project"]

        self.assertEqual(project["name"], "patchharbor")
        self.assertEqual(project["scripts"]["patchharbor"], "patchharbor.cli:main")
        self.assertEqual(self.pyproject()["tool"]["setuptools"]["packages"]["find"]["where"], ["src"])
        self.assertTrue((ROOT / "src/patchharbor/__main__.py").is_file())
        self.assertTrue((ROOT / "README.md").is_file())
        self.assertTrue(SMOKE.is_file())
        self.assertTrue(os.access(SMOKE, os.X_OK))

        for marker in [
            "virtual-environment installation",
            "pipx install -e .",
            "patchharbor --help",
            "patchharbor --version",
            "patchharbor doctor --repo",
            "patchharbor check-env --repo",
        ]:
            with self.subTest(marker=marker):
                self.assertIn(marker, text)

    def test_pipx_smoke_dry_run_is_part_of_packaging_acceptance(self) -> None:
        result = subprocess.run(
            [
                str(SMOKE),
                "--dry-run",
                "--repo",
                str(ROOT),
                "--pipx",
                "__patchharbor_missing_pipx__",
                "--python",
                sys.executable,
            ],
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("install --force --editable", result.stdout)
        self.assertIn("patchharbor --help", result.stdout)
        self.assertIn("patchharbor --version", result.stdout)
        self.assertIn("doctor --repo", result.stdout)
        self.assertIn("check-env --repo", result.stdout)
        self.assertIn("pipx-smoke: ok", result.stdout)

    def test_cli_entrypoints_remain_available_for_packaging_acceptance(self) -> None:
        checks = [
            ("--help",),
            ("--version",),
            ("doctor", "--repo", str(ROOT)),
            ("check-env", "--repo", str(ROOT), "--no-defaults"),
        ]

        for args in checks:
            with self.subTest(args=args):
                result = run_patchharbor(*args)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_packaging_acceptance_runs_existing_functional_test_modules(self) -> None:
        modules = [
            "tests.test_packaging_metadata",
            "tests.test_readme_installation",
            "tests.test_pipx_smoke_script",
        ]

        for module in modules:
            with self.subTest(module=module):
                result = subprocess.run(
                    [sys.executable, "-m", "unittest", module],
                    cwd=ROOT,
                    env={**os.environ, "PYTHONPATH": str(SRC) + os.pathsep + os.environ.get("PYTHONPATH", "")},
                    text=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    check=False,
                )
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_packaging_acceptance_excludes_display_only_assertions(self) -> None:
        text = self.acceptance_text()

        self.assertIn("Exact terminal formatting is not part", text)
        self.assertIn("Functional status, command availability, return codes", text)
        self.assertIn("This patch does not:", text)

    def test_packaging_acceptance_files_do_not_store_private_local_values(self) -> None:
        checked = [
            ACCEPTANCE,
            Path(__file__).resolve(),
            ROOT / "README.md",
            ROOT / "pyproject.toml",
            SMOKE,
        ]
        text = "\n".join(path.read_text(encoding="utf-8") for path in checked)
        forbidden = [
            "/home/" + "christian",
            "christian" + "@",
            "christian.doehn" + "@" + "gmail.com",
            "Think" + "Pad",
            "Blade-" + "15",
            "~/" + "Projekte",
            "run_latest_" + "download_patch",
            chr(96) * 3,
        ]
        for value in forbidden:
            with self.subTest(value=value):
                self.assertNotIn(value, text)


if __name__ == "__main__":
    unittest.main()
