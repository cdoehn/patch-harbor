from __future__ import annotations

import os
import re
import subprocess
import unittest
from pathlib import Path

TARGET_ROOT = Path(__file__).resolve().parents[1]
HYGIENE_DOC = TARGET_ROOT / "docs" / "final-repository-hygiene-acceptance.md"
REMOTE_DOC = TARGET_ROOT / "docs" / "remote-branch-cleanup-commands.md"
LOCAL_DOC = TARGET_ROOT / "docs" / "local-branch-cleanup-commands.md"
INVENTORY_DOC = TARGET_ROOT / "docs" / "migration-branch-inventory.md"
PUBLIC_READINESS = TARGET_ROOT / "docs" / "public-readiness-acceptance.md"

HYGIENE_PATHS = [
    "docs/final-repository-hygiene-acceptance.md",
    "docs/remote-branch-cleanup-commands.md",
    "docs/local-branch-cleanup-commands.md",
    "docs/migration-branch-inventory.md",
    "docs/public-readiness-acceptance.md",
    "tests/test_final_repository_hygiene_acceptance.py",
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


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def _private_patterns() -> list[str]:
    return [
        "/home/" + "christian",
        "christian.doehn" + "@" + "gmail.com",
        "christian" + "@",
        "Think" + "Pad",
        "Blade-" + "15",
        "~/" + "Projekte",
    ]


class FinalRepositoryHygieneAcceptanceTests(unittest.TestCase):
    def test_final_hygiene_doc_exists_and_records_plan_contract(self) -> None:
        self.assertTrue(HYGIENE_DOC.is_file())
        text = HYGIENE_DOC.read_text(encoding="utf-8")
        required = [
            "PATCHHARBOR.17c4 – Final repository hygiene acceptance",
            "Final Repository Hygiene Acceptance",
            "Add final repository hygiene acceptance",
            "planning/milestones_migration.md",
        ]
        for marker in required:
            with self.subTest(marker=marker):
                self.assertIn(marker, text)

    def test_source_plan_defines_17c4_final_hygiene_and_commit(self) -> None:
        source = _discover_source_repo()
        before = _source_status(source)

        plan = (source / "planning" / "milestones_migration.md").read_text(encoding="utf-8")
        idx = plan.find("PATCHHARBOR.17c4")
        self.assertGreaterEqual(idx, 0)
        window = plan[idx : idx + 500]
        self.assertIn("Final Repository Hygiene Acceptance", window)
        self.assertIn("Add final repository hygiene acceptance", window)

        after = _source_status(source)
        self.assertEqual(after, before)

    def test_final_hygiene_acceptance_lists_required_evidence(self) -> None:
        text = HYGIENE_DOC.read_text(encoding="utf-8")
        required = [
            "PATCHHARBOR.17c1",
            "docs/migration-branch-inventory.md",
            "tests/test_migration_branch_inventory.py",
            "PATCHHARBOR.17c2",
            "docs/local-branch-cleanup-commands.md",
            "tests/test_local_branch_cleanup_commands.py",
            "PATCHHARBOR.17c3",
            "docs/remote-branch-cleanup-commands.md",
            "tests/test_remote_branch_cleanup_commands.py",
            "PATCHHARBOR.17c4",
            "docs/final-repository-hygiene-acceptance.md",
            "tests/test_final_repository_hygiene_acceptance.py",
        ]
        for marker in required:
            with self.subTest(marker=marker):
                self.assertIn(marker, text)
                if marker.startswith("docs/") or marker.startswith("tests/"):
                    self.assertTrue((TARGET_ROOT / marker).is_file())

    def test_final_hygiene_acceptance_explicitly_says_cleanup_was_not_executed(self) -> None:
        text = HYGIENE_DOC.read_text(encoding="utf-8")
        required = [
            "PATCHHARBOR.17c4 does not execute",
            "git branch -d",
            "git branch -D",
            "git push origin --delete",
            "git fetch",
            "git push",
            "git tag",
            "package publish commands",
            "The cleanup documents are command references",
            "not evidence that cleanup has already been performed",
        ]
        for marker in required:
            with self.subTest(marker=marker):
                self.assertIn(marker, text)

    def test_related_docs_link_to_final_hygiene_acceptance(self) -> None:
        for path in [REMOTE_DOC, LOCAL_DOC, INVENTORY_DOC, PUBLIC_READINESS]:
            text = path.read_text(encoding="utf-8")
            with self.subTest(path=path):
                self.assertIn("PATCHHARBOR.17c4 applied", text)
                self.assertIn("docs/final-repository-hygiene-acceptance.md", text)
                self.assertIn("tests/test_final_repository_hygiene_acceptance.py", text)

    def test_final_hygiene_tests_run_only_read_only_git_inventory_commands(self) -> None:
        source = _discover_source_repo()
        before = _source_status(source)

        repos = [TARGET_ROOT, source]
        commands = [
            ("branch", "--show-current"),
            ("status", "--short"),
            ("branch", "--format=%(refname:short)"),
            ("branch", "-r", "--format=%(refname:short)"),
            ("remote",),
        ]
        for repo in repos:
            for command in commands:
                with self.subTest(repo=repo.name, command=command):
                    result = _git(repo, *command)
                    self.assertIn(result.returncode, {0, 1}, result.stderr)

        after = _source_status(source)
        self.assertEqual(after, before)

    def test_final_hygiene_acceptance_is_read_only_for_source(self) -> None:
        source = _discover_source_repo()
        before = _source_status(source)

        for relative in [
            "planning/milestones_migration.md",
            "README.md",
            "pyproject.toml",
            "scripts/dev/run_latest_download_patch.sh",
            "scripts/dev/run_patchharbor_patch.sh",
            "scripts/dev/r.sh",
            "scripts/dev/run_repodossier_exports.sh",
        ]:
            with self.subTest(relative=relative):
                path = source / relative
                self.assertTrue(path.exists())
                if path.is_file():
                    _ = path.read_text(encoding="utf-8")

        after = _source_status(source)
        self.assertEqual(after, before)

    def test_final_hygiene_acceptance_does_not_store_private_local_values_or_fences(self) -> None:
        text = "\n".join((TARGET_ROOT / relative).read_text(encoding="utf-8") for relative in HYGIENE_PATHS)
        for value in _private_patterns():
            with self.subTest(value=value):
                self.assertNotIn(value, text)
        self.assertNotIn(chr(96) * 3, text)


if __name__ == "__main__":
    unittest.main()
