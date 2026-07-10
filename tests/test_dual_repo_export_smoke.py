from __future__ import annotations

import os
import re
import subprocess
import unittest
from pathlib import Path

TARGET_ROOT = Path(__file__).resolve().parents[1]
SMOKE_DOC = TARGET_ROOT / "docs" / "dual-repo-export-smoke.md"
SOURCE_WRAPPER_DOC = TARGET_ROOT / "docs" / "dual-repo-source-wrapper-smoke.md"
PUBLIC_READINESS = TARGET_ROOT / "docs" / "public-readiness-acceptance.md"

EXPORT_WRAPPERS = [
    "scripts/dev/r.sh",
    "scripts/dev/run_repodossier_exports.sh",
]


def _pyproject_name(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    match = re.search(r'^name\s*=\s*["\']([^"\']+)["\']\s*$', text, re.M)
    if not match:
        return ""
    return match.group(1)


def _source_candidates() -> list[Path]:
    candidates: list[Path] = []
    env_source = os.environ.get("PATCHHARBOR_SOURCE_REPO")
    if env_source:
        candidates.append(Path(env_source).expanduser())
    candidates.append(TARGET_ROOT.parent / "repo_dossier")
    candidates.append(TARGET_ROOT.parent / "repodossier")
    return candidates


def _discover_source_repo() -> Path:
    for candidate in _source_candidates():
        path = candidate.resolve()
        if (
            (path / "pyproject.toml").is_file()
            and (path / "src" / "repodossier").is_dir()
            and _pyproject_name(path / "pyproject.toml") == "repodossier"
        ):
            return path
    raise AssertionError("RepoDossier source checkout was not discoverable")


def _source_status(source: Path) -> str:
    return subprocess.run(
        ["git", "-C", str(source), "status", "--porcelain"],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
    ).stdout


def _run_source_command(source: Path, args: list[str]) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = f"{source / 'src'}{os.pathsep}{env.get('PYTHONPATH', '')}".rstrip(os.pathsep)
    env["REPODOSSIER_REPO"] = str(source)
    return subprocess.run(
        args,
        cwd=source,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


class PatchHarborDualRepoExportSmokeTests(unittest.TestCase):
    def test_smoke_doc_exists_and_records_16a4_contract(self) -> None:
        self.assertTrue(SMOKE_DOC.is_file())
        text = SMOKE_DOC.read_text(encoding="utf-8")
        required = [
            "PATCHHARBOR.16a4 – Dual repo export smoke",
            "PATCHHARBOR.16a3 proved source wrapper syntax",
            "scripts/dev/r.sh",
            "scripts/dev/run_repodossier_exports.sh",
            "r --list-modes",
            "r --dry-run",
            "PATCHHARBOR.16b1",
        ]
        for marker in required:
            with self.subTest(marker=marker):
                self.assertIn(marker, text)

    def test_export_wrappers_exist_and_are_bash_syntax_valid(self) -> None:
        source = _discover_source_repo()
        for relative in EXPORT_WRAPPERS:
            with self.subTest(relative=relative):
                path = source / relative
                self.assertTrue(path.is_file())
                result = subprocess.run(
                    ["bash", "-n", str(path)],
                    text=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    check=False,
                )
                self.assertEqual(result.returncode, 0, result.stderr)

    def test_export_wrappers_keep_expected_dry_run_and_mode_markers(self) -> None:
        source = _discover_source_repo()
        combined = "\n".join((source / relative).read_text(encoding="utf-8") for relative in EXPORT_WRAPPERS)
        for marker in [
            "--dry-run",
            "--list-modes",
            "run_repodossier_exports.sh",
            "full",
            "ai",
            "docs",
            "changed",
        ]:
            with self.subTest(marker=marker):
                self.assertIn(marker, combined)

    def test_export_list_modes_smoke_is_read_only_for_source(self) -> None:
        source = _discover_source_repo()
        before = _source_status(source)
        result = _run_source_command(
            source,
            ["bash", str(source / "scripts" / "dev" / "run_repodossier_exports.sh"), "--list-modes"],
        )
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        output = (result.stdout + result.stderr).lower()
        self.assertTrue(any(marker in output for marker in ["full", "ai", "docs", "changed", "mode"]))
        after = _source_status(source)
        self.assertEqual(after, before)

    def test_export_dry_run_smoke_is_read_only_for_source(self) -> None:
        source = _discover_source_repo()
        before = _source_status(source)
        result = _run_source_command(
            source,
            ["bash", str(source / "scripts" / "dev" / "run_repodossier_exports.sh"), "--dry-run", "ai"],
        )
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        output = (result.stdout + result.stderr).lower()
        self.assertTrue(any(marker in output for marker in ["dry", "ai", "repodossier", "export"]))
        after = _source_status(source)
        self.assertEqual(after, before)

    def test_related_docs_link_to_export_smoke(self) -> None:
        for path in [SOURCE_WRAPPER_DOC, PUBLIC_READINESS]:
            text = path.read_text(encoding="utf-8")
            with self.subTest(path=path):
                self.assertIn("PATCHHARBOR.16a4 applied", text)
                self.assertIn("docs/dual-repo-export-smoke.md", text)
                self.assertIn("tests/test_dual_repo_export_smoke.py", text)

    def test_export_smoke_does_not_store_private_local_values_or_fences(self) -> None:
        text = "\n".join(
            path.read_text(encoding="utf-8")
            for path in [SMOKE_DOC, SOURCE_WRAPPER_DOC, PUBLIC_READINESS, Path(__file__).resolve()]
        )
        forbidden = [
            "/home/" + "christian",
            "christian" + "@",
            "christian.doehn" + "@" + "gmail.com",
            "Think" + "Pad",
            "Blade-" + "15",
            "~/" + "Projekte",
        ]
        for value in forbidden:
            with self.subTest(value=value):
                self.assertNotIn(value, text)
        self.assertNotIn(chr(96) * 3, text)


if __name__ == "__main__":
    unittest.main()
