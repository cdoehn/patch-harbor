from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/smoke_pipx_install.sh"


def run_smoke_script(*args: str, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env.pop("PIPX_HOME", None)
    env.pop("PIPX_BIN_DIR", None)
    env.pop("PIPX_MAN_DIR", None)
    return subprocess.run(
        [str(SCRIPT), *args],
        cwd=ROOT if cwd is None else cwd,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


class PatchHarborPipxSmokeScriptTests(unittest.TestCase):
    def test_script_exists_is_executable_and_has_valid_bash_syntax(self) -> None:
        self.assertTrue(SCRIPT.is_file())
        self.assertTrue(os.access(SCRIPT, os.X_OK))

        result = subprocess.run(
            ["bash", "-n", str(SCRIPT)],
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )

        self.assertEqual(result.returncode, 0, result.stderr)

    def test_help_documents_isolated_pipx_smoke_contract(self) -> None:
        result = run_smoke_script("--help")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("isolated pipx install smoke", result.stdout)
        self.assertIn("--dry-run", result.stdout)
        self.assertIn("--keep-temp", result.stdout)
        self.assertIn("--skip-uninstall", result.stdout)
        self.assertIn("--pipx PATH", result.stdout)
        self.assertIn("--python PATH", result.stdout)
        self.assertIn("PIPX_HOME", result.stdout)
        self.assertIn("pipx install --force --editable REPO", result.stdout)

    def test_dry_run_prints_pipx_install_and_cli_smoke_without_requiring_pipx(self) -> None:
        result = run_smoke_script(
            "--dry-run",
            "--repo",
            str(ROOT),
            "--pipx",
            "__patchharbor_missing_pipx__",
            "--python",
            sys.executable,
        )

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("dry-run", result.stdout)
        self.assertIn("__patchharbor_missing_pipx__", result.stdout)
        self.assertIn("install --force --editable", result.stdout)
        self.assertIn("PIPX_HOME=", result.stdout)
        self.assertIn("PIPX_BIN_DIR=", result.stdout)
        self.assertIn("PIPX_DEFAULT_PYTHON=", result.stdout)
        self.assertIn("patchharbor --help", result.stdout)
        self.assertIn("patchharbor --version", result.stdout)
        self.assertIn("doctor --repo", result.stdout)
        self.assertIn("check-env --repo", result.stdout)
        self.assertIn("uninstall patchharbor", result.stdout)
        self.assertIn("pipx-smoke: ok", result.stdout)

    def test_dry_run_validates_repository_metadata_before_printing_smoke_plan(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            subprocess.run(["git", "init"], cwd=repo, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)

            result = run_smoke_script("--dry-run", "--repo", str(repo), "--pipx", "__missing_pipx__")

        self.assertEqual(result.returncode, 2)
        self.assertIn("pyproject.toml missing", result.stderr)

    def test_script_uses_temporary_pipx_environment_instead_of_user_pipx_state(self) -> None:
        text = SCRIPT.read_text(encoding="utf-8")

        required = [
            "mktemp -d",
            "PIPX_HOME_VALUE",
            "PIPX_BIN_DIR_VALUE",
            "PIPX_MAN_DIR_VALUE",
            "PIPX_DEFAULT_PYTHON",
            "pipx-home",
            "pipx-bin",
            "pipx-man",
            "install --force --editable",
            "uninstall patchharbor",
        ]
        missing = [marker for marker in required if marker not in text]
        self.assertFalse(missing, missing)

    def test_script_checks_functional_patchharbor_entrypoints(self) -> None:
        text = SCRIPT.read_text(encoding="utf-8")

        required = [
            "run_installed_patchharbor --help",
            "run_installed_patchharbor --version",
            "run_installed_patchharbor doctor --repo",
            "run_installed_patchharbor check-env --repo",
        ]
        missing = [marker for marker in required if marker not in text]
        self.assertFalse(missing, missing)

    def test_pipx_smoke_files_do_not_store_private_local_values(self) -> None:
        checked = [
            SCRIPT,
            Path(__file__).resolve(),
            ROOT / "README.md",
            ROOT / "pyproject.toml",
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
