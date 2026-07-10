from __future__ import annotations

import os
import re
import subprocess
import unittest
from pathlib import Path

TARGET_ROOT = Path(__file__).resolve().parents[1]
CLEANUP_DOC = TARGET_ROOT / "docs" / "local-branch-cleanup-commands.md"
INVENTORY_DOC = TARGET_ROOT / "docs" / "migration-branch-inventory.md"
REPODOSSIER_RELEASE_NOTES = TARGET_ROOT / "docs" / "repodossier-follow-up-release-notes.md"
PUBLIC_READINESS = TARGET_ROOT / "docs" / "public-readiness-acceptance.md"

CLEANUP_PATHS = [
    "docs/local-branch-cleanup-commands.md",
    "docs/migration-branch-inventory.md",
    "docs/repodossier-follow-up-release-notes.md",
    "docs/public-readiness-acceptance.md",
    "tests/test_local_branch_cleanup_commands.py",
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


class LocalBranchCleanupCommandsTests(unittest.TestCase):
    def test_local_cleanup_doc_exists_and_records_plan_contract(self) -> None:
        self.assertTrue(CLEANUP_DOC.is_file())
        text = CLEANUP_DOC.read_text(encoding="utf-8")
        required = [
            "PATCHHARBOR.17c2 – Local branch cleanup commands",
            "Local Branch Cleanup Commands",
            "Document local branch cleanup commands",
            "PATCHHARBOR.17c3 – Remote Branch Cleanup Commands",
        ]
        for marker in required:
            with self.subTest(marker=marker):
                self.assertIn(marker, text)

    def test_source_plan_defines_17c2_local_cleanup_and_commit(self) -> None:
        source = _discover_source_repo()
        before = _source_status(source)

        plan = (source / "planning" / "milestones_migration.md").read_text(encoding="utf-8")
        idx = plan.find("PATCHHARBOR.17c2")
        self.assertGreaterEqual(idx, 0)
        window = plan[idx : idx + 400]
        self.assertIn("Local Branch Cleanup Commands", window)
        self.assertIn("Document local branch cleanup commands", window)
        self.assertIn("PATCHHARBOR.17c3", plan)

        after = _source_status(source)
        self.assertEqual(after, before)

    def test_local_cleanup_commands_are_documented(self) -> None:
        text = CLEANUP_DOC.read_text(encoding="utf-8")
        required = [
            "git branch --show-current",
            "git status --short",
            "git show-ref --verify --quiet refs/heads/main",
            "git branch --format='%(refname:short)'",
            "git branch --merged main --format='%(refname:short)'",
            "git branch --no-merged main --format='%(refname:short)'",
            "git switch main",
            "xargs -r git branch -d",
            "git branch -D BRANCH_NAME",
        ]
        for marker in required:
            with self.subTest(marker=marker):
                self.assertIn(marker, text)

    def test_local_cleanup_document_explicitly_excludes_remote_and_publish_actions(self) -> None:
        text = CLEANUP_DOC.read_text(encoding="utf-8")
        expected = [
            "does not delete remote branches",
            "remote cleanup is explicitly out of scope",
            "delete remote branches",
            "push branch deletion",
            "fetch from remotes",
            "create or push git tags",
            "publish a release",
            "change package metadata",
        ]
        for marker in expected:
            with self.subTest(marker=marker):
                self.assertIn(marker, text)

    def test_cleanup_tests_run_only_read_only_git_inventory_commands(self) -> None:
        source = _discover_source_repo()
        before = _source_status(source)

        repos = [TARGET_ROOT, source]
        commands = [
            ("branch", "--show-current"),
            ("status", "--short"),
            ("branch", "--format=%(refname:short)"),
            ("branch", "--merged", "main", "--format=%(refname:short)"),
            ("branch", "--no-merged", "main", "--format=%(refname:short)"),
        ]
        for repo in repos:
            for command in commands:
                with self.subTest(repo=repo.name, command=command):
                    result = _git(repo, *command)
                    self.assertIn(result.returncode, {0, 1}, result.stderr)

        after = _source_status(source)
        self.assertEqual(after, before)

    def test_related_docs_link_to_local_cleanup_commands(self) -> None:
        for path in [INVENTORY_DOC, REPODOSSIER_RELEASE_NOTES, PUBLIC_READINESS]:
            text = path.read_text(encoding="utf-8")
            with self.subTest(path=path):
                self.assertIn("PATCHHARBOR.17c2 applied", text)
                self.assertIn("docs/local-branch-cleanup-commands.md", text)
                self.assertIn("tests/test_local_branch_cleanup_commands.py", text)

    def test_local_cleanup_commands_are_read_only_for_source(self) -> None:
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

    def test_local_cleanup_commands_do_not_store_private_local_values_or_fences(self) -> None:
        text = "\n".join((TARGET_ROOT / relative).read_text(encoding="utf-8") for relative in CLEANUP_PATHS)
        for value in _private_patterns():
            with self.subTest(value=value):
                self.assertNotIn(value, text)
        self.assertNotIn(chr(96) * 3, text)


if __name__ == "__main__":
    unittest.main()
