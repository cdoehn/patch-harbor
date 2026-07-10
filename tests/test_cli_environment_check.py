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


def run_patchharbor(*args: str, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(SRC) + os.pathsep + env.get("PYTHONPATH", "")
    return subprocess.run(
        [sys.executable, "-m", "patchharbor", *args],
        cwd=ROOT if cwd is None else cwd,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def init_repo(root: Path) -> None:
    subprocess.run(["git", "init"], cwd=root, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
    subprocess.run(["git", "config", "user.name", "Patch Harbor"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.email", "patchharbor@example.test"], cwd=root, check=True)


class PatchHarborEnvironmentCheckCliTests(unittest.TestCase):
    def test_parser_exposes_check_env_subcommand(self) -> None:
        help_text = build_parser().format_help()
        self.assertIn("check-env", help_text)

    def test_check_env_defaults_pass_in_git_repo(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            init_repo(repo)

            result = run_patchharbor("check-env", "--repo", str(repo))

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("PatchHarbor check-env", result.stdout)
        self.assertIn("status: ok", result.stdout)
        self.assertIn("[OK] git repository:", result.stdout)
        self.assertIn("[OK] git user.name:", result.stdout)
        self.assertIn("[OK] git user.email:", result.stdout)
        self.assertIn("[OK] python:", result.stdout)

    def test_check_env_command_and_file_checks(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            init_repo(repo)
            (repo / "README.md").write_text("ok\n", encoding="utf-8")

            result = run_patchharbor(
                "check-env",
                "--repo",
                str(repo),
                "--no-defaults",
                "--file",
                "readme=README.md",
                "--command",
                f"python={sys.executable} --version",
            )

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("[OK] readme:", result.stdout)
        self.assertIn("[OK] python:", result.stdout)
        self.assertIn("status: ok", result.stdout)

    def test_check_env_required_failure_exits_one(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            init_repo(repo)

            result = run_patchharbor(
                "check-env",
                "--repo",
                str(repo),
                "--no-defaults",
                "--command",
                "missing=__patchharbor_missing_binary__ --version",
            )

        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("[FAIL] missing:", result.stdout)
        self.assertIn("status: failed", result.stdout)

    def test_check_env_optional_failure_exits_zero_with_warning(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            init_repo(repo)

            result = run_patchharbor(
                "check-env",
                "--repo",
                str(repo),
                "--no-defaults",
                "--command",
                "missing:optional=__patchharbor_missing_binary__ --version",
            )

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("[WARN] missing:", result.stdout)
        self.assertIn("status: warning", result.stdout)

    def test_check_env_optional_flag_can_mark_named_check_optional(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            init_repo(repo)

            result = run_patchharbor(
                "check-env",
                "--repo",
                str(repo),
                "--no-defaults",
                "--optional",
                "missing_file",
                "--file",
                "missing_file=missing.txt",
            )

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("[WARN] missing_file:", result.stdout)
        self.assertIn("status: warning", result.stdout)

    def test_check_env_git_config_and_python_module_checks(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            init_repo(repo)

            result = run_patchharbor(
                "check-env",
                "--repo",
                str(repo),
                "--no-defaults",
                "--git-config",
                "user=user.name",
                "--python-module",
                "json=json",
            )

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("[OK] user:", result.stdout)
        self.assertIn("[OK] json:", result.stdout)
        self.assertIn("module available: json", result.stdout)

    def test_check_env_bad_spec_reports_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            init_repo(repo)

            result = run_patchharbor("check-env", "--repo", str(repo), "--command", "broken")

        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertIn("status: error", result.stdout)
        self.assertIn("NAME=VALUE", result.stdout)

    def test_check_env_missing_repo_reports_error(self) -> None:
        missing = ROOT / ".patchharbor-missing-env-repo"

        result = run_patchharbor("check-env", "--repo", str(missing))

        self.assertEqual(result.returncode, 2)
        self.assertIn("status: error", result.stdout)
        self.assertIn("repository path does not exist", result.stdout)

    def test_main_check_env_accepts_args_directly(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            init_repo(repo)

            self.assertEqual(main(["check-env", "--repo", str(repo), "--no-defaults"]), 0)

    def test_cli_environment_check_files_do_not_store_source_specific_defaults(self) -> None:
        checked = [
            ROOT / "src/patchharbor/cli.py",
            ROOT / "tests/test_cli_environment_check.py",
        ]
        text = "\n".join(path.read_text(encoding="utf-8") for path in checked)
        forbidden = [
            "Repo" + "Dossier",
            "repo" + "dossier",
            "check_dev_" + "environment.py",
            "repo" + "dossier",
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
