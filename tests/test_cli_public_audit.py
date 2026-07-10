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


class PatchHarborPublicAuditCliTests(unittest.TestCase):
    def test_parser_exposes_audit_public_subcommand(self) -> None:
        help_text = build_parser().format_help()
        self.assertIn("audit-public", help_text)

    def test_audit_public_explicit_target_reports_error_findings(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            init_repo(repo)
            (repo / "docs").mkdir()
            target = repo / "docs/readme.md"
            target.write_text("safe\ncontains SECRET_TOKEN here\n", encoding="utf-8")
            subprocess.run(["git", "add", "docs/readme.md"], cwd=repo, check=True)

            result = run_patchharbor(
                "audit-public",
                "--repo",
                str(repo),
                "--target",
                "docs/readme.md",
                "--pattern",
                "secret=SECRET_TOKEN",
            )

        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("PatchHarbor audit-public", result.stdout)
        self.assertIn("status: failed", result.stdout)
        self.assertIn("scanned targets: 1", result.stdout)
        self.assertIn("findings: 1", result.stdout)
        self.assertIn("docs/readme.md:2:10: error/secret: contains SECRET_TOKEN here", result.stdout)

    def test_audit_public_warning_findings_exit_zero(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            init_repo(repo)
            path = repo / "notice.txt"
            path.write_text("contact@example.test\n", encoding="utf-8")
            subprocess.run(["git", "add", "notice.txt"], cwd=repo, check=True)

            result = run_patchharbor(
                "audit-public",
                "--repo",
                str(repo),
                "--target",
                "notice.txt",
                "--pattern",
                "mail:warning=contact@example.test",
            )

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("status: warning", result.stdout)
        self.assertIn("warning/mail", result.stdout)

    def test_audit_public_defaults_to_git_tracked_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            init_repo(repo)
            tracked = repo / "tracked.txt"
            untracked = repo / "untracked.txt"
            tracked.write_text("TRACKED_SECRET\n", encoding="utf-8")
            untracked.write_text("TRACKED_SECRET\n", encoding="utf-8")
            subprocess.run(["git", "add", "tracked.txt"], cwd=repo, check=True)

            result = run_patchharbor(
                "audit-public",
                "--repo",
                str(repo),
                "--pattern",
                "secret=TRACKED_SECRET",
            )

        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("tracked.txt:1:1: error/secret", result.stdout)
        self.assertNotIn("untracked.txt", result.stdout)

    def test_audit_public_no_findings_exits_zero(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            init_repo(repo)
            path = repo / "clean.txt"
            path.write_text("clean\n", encoding="utf-8")
            subprocess.run(["git", "add", "clean.txt"], cwd=repo, check=True)

            result = run_patchharbor(
                "audit-public",
                "--repo",
                str(repo),
                "--pattern",
                "secret=SECRET_TOKEN",
            )

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("status: ok", result.stdout)
        self.assertIn("findings: 0", result.stdout)

    def test_audit_public_reports_bad_pattern_as_problem(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            init_repo(repo)
            (repo / "file.txt").write_text("x\n", encoding="utf-8")
            subprocess.run(["git", "add", "file.txt"], cwd=repo, check=True)

            result = run_patchharbor("audit-public", "--repo", str(repo), "--pattern", "broken")

        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertIn("status: error", result.stdout)
        self.assertIn("problem:", result.stdout)
        self.assertIn("NAME=VALUE", result.stdout)

    def test_main_audit_public_accepts_args_directly(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            init_repo(repo)
            path = repo / "clean.txt"
            path.write_text("clean\n", encoding="utf-8")
            subprocess.run(["git", "add", "clean.txt"], cwd=repo, check=True)

            self.assertEqual(main(["audit-public", "--repo", str(repo), "--pattern", "secret=SECRET"]), 0)

    def test_module_help_includes_audit_public(self) -> None:
        result = run_patchharbor("--help")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("audit-public", result.stdout)

    def test_cli_public_audit_files_do_not_store_source_specific_defaults(self) -> None:
        checked = [
            ROOT / "src/patchharbor/cli.py",
            ROOT / "tests/test_cli_public_audit.py",
        ]
        text = "\n".join(path.read_text(encoding="utf-8") for path in checked)
        forbidden = [
            "Repo" + "Dossier public audit defaults",
            "audit_public_" + "repo.py",
            "FORBIDDEN_" + "PATTERNS",
            "market_" + "research",
            "/home/" + "exampleuser",
            "user" + "@",
            "example.user" + "@" + "example.invalid",
            "Example" + "Laptop",
            "Example" + "Machine",
            "~/" + "Projects",
            chr(96) * 3,
        ]
        for value in forbidden:
            with self.subTest(value=value):
                self.assertNotIn(value, text)


if __name__ == "__main__":
    unittest.main()
