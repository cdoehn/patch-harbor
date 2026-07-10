from __future__ import annotations

import os
import re
import subprocess
import unittest
from pathlib import Path

TARGET_ROOT = Path(__file__).resolve().parents[1]
REMOTE_DOC = TARGET_ROOT / "docs" / "remote-branch-cleanup-commands.md"
LOCAL_DOC = TARGET_ROOT / "docs" / "local-branch-cleanup-commands.md"
INVENTORY_DOC = TARGET_ROOT / "docs" / "migration-branch-inventory.md"
PUBLIC_READINESS = TARGET_ROOT / "docs" / "public-readiness-acceptance.md"

REMOTE_CLEANUP_PATHS = [
    "docs/remote-branch-cleanup-commands.md",
    "docs/local-branch-cleanup-commands.md",
    "docs/migration-branch-inventory.md",
    "docs/public-readiness-acceptance.md",
    "tests/test_remote_branch_cleanup_commands.py",
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


class RemoteBranchCleanupCommandsTests(unittest.TestCase):
    def test_remote_cleanup_doc_exists_and_records_plan_contract(self) -> None:
        self.assertTrue(REMOTE_DOC.is_file())
        text = REMOTE_DOC.read_text(encoding="utf-8")
        required = [
            "PATCHHARBOR.17c3 – Remote branch cleanup commands",
            "Remote Branch Cleanup Commands",
            "Document remote branch cleanup commands",
            "PATCHHARBOR.17c4 – Final Repository Hygiene Acceptance",
        ]
        for marker in required:
            with self.subTest(marker=marker):
                self.assertIn(marker, text)

    def test_source_plan_defines_17c3_remote_cleanup_and_commit(self) -> None:
        source = _discover_source_repo()
        before = _source_status(source)

        plan = (source / "planning" / "milestones_migration.md").read_text(encoding="utf-8")
        idx = plan.find("PATCHHARBOR.17c3")
        self.assertGreaterEqual(idx, 0)
        window = plan[idx : idx + 400]
        self.assertIn("Remote Branch Cleanup Commands", window)
        self.assertIn("Document remote branch cleanup commands", window)
        self.assertIn("PATCHHARBOR.17c4", plan)

        after = _source_status(source)
        self.assertEqual(after, before)

    def test_remote_cleanup_commands_are_documented(self) -> None:
        text = REMOTE_DOC.read_text(encoding="utf-8")
        required = [
            "git branch -r --format='%(refname:short)'",
            "git remote",
            "git for-each-ref refs/remotes --format='%(refname:short)'",
            "git show-ref --verify --quiet refs/remotes/origin/main",
            "git push origin --delete BRANCH_NAME",
            "git ls-remote --heads origin BRANCH_NAME",
        ]
        for marker in required:
            with self.subTest(marker=marker):
                self.assertIn(marker, text)

    def test_remote_cleanup_document_requires_manual_review_and_forbids_piped_remote_deletion(self) -> None:
        text = REMOTE_DOC.read_text(encoding="utf-8")
        required = [
            "Remote branch cleanup is destructive for shared repositories",
            "Replace `BRANCH_NAME` manually",
            "Do not pipe branch lists into remote deletion commands",
            "Do not use `xargs` for remote deletion",
            "ask for human confirmation",
            "This document does not execute any remote cleanup command",
        ]
        for marker in required:
            with self.subTest(marker=marker):
                self.assertIn(marker, text)

    def test_remote_cleanup_tests_run_only_read_only_remote_inventory_commands(self) -> None:
        source = _discover_source_repo()
        before = _source_status(source)

        repos = [TARGET_ROOT, source]
        commands = [
            ("branch", "-r", "--format=%(refname:short)"),
            ("remote",),
            ("for-each-ref", "refs/remotes", "--format=%(refname:short)"),
            ("show-ref", "--verify", "--quiet", "refs/remotes/origin/main"),
        ]
        for repo in repos:
            for command in commands:
                with self.subTest(repo=repo.name, command=command):
                    result = _git(repo, *command)
                    self.assertIn(result.returncode, {0, 1}, result.stderr)

        after = _source_status(source)
        self.assertEqual(after, before)

    def test_related_docs_link_to_remote_cleanup_commands(self) -> None:
        for path in [LOCAL_DOC, INVENTORY_DOC, PUBLIC_READINESS]:
            text = path.read_text(encoding="utf-8")
            with self.subTest(path=path):
                self.assertIn("PATCHHARBOR.17c3 applied", text)
                self.assertIn("docs/remote-branch-cleanup-commands.md", text)
                self.assertIn("tests/test_remote_branch_cleanup_commands.py", text)

    def test_remote_cleanup_commands_are_read_only_for_source(self) -> None:
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

    def test_remote_cleanup_commands_do_not_store_private_local_values_or_fences(self) -> None:
        text = "\n".join((TARGET_ROOT / relative).read_text(encoding="utf-8") for relative in REMOTE_CLEANUP_PATHS)
        for value in _private_patterns():
            with self.subTest(value=value):
                self.assertNotIn(value, text)
        self.assertNotIn(chr(96) * 3, text)


if __name__ == "__main__":
    unittest.main()
