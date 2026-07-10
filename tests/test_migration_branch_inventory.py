from __future__ import annotations

import os
import re
import subprocess
import unittest
from pathlib import Path

TARGET_ROOT = Path(__file__).resolve().parents[1]
INVENTORY_DOC = TARGET_ROOT / "docs" / "migration-branch-inventory.md"
REPODOSSIER_RELEASE_NOTES = TARGET_ROOT / "docs" / "repodossier-follow-up-release-notes.md"
PATCHHARBOR_RELEASE_NOTES = TARGET_ROOT / "docs" / "patchharbor-release-notes.md"
PUBLIC_READINESS = TARGET_ROOT / "docs" / "public-readiness-acceptance.md"

INVENTORY_PATHS = [
    "docs/migration-branch-inventory.md",
    "docs/repodossier-follow-up-release-notes.md",
    "docs/patchharbor-release-notes.md",
    "docs/public-readiness-acceptance.md",
    "tests/test_migration_branch_inventory.py",
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


class MigrationBranchInventoryTests(unittest.TestCase):
    def test_branch_inventory_doc_exists_and_records_plan_contract(self) -> None:
        self.assertTrue(INVENTORY_DOC.is_file())
        text = INVENTORY_DOC.read_text(encoding="utf-8")
        required = [
            "PATCHHARBOR.17c1 – Branch inventory",
            "Branch Inventory",
            "Document migration branch inventory",
            "planning/milestones_migration.md",
            "PATCHHARBOR.17c2 – Local Branch Cleanup Commands",
        ]
        for marker in required:
            with self.subTest(marker=marker):
                self.assertIn(marker, text)

    def test_source_plan_defines_17c1_branch_inventory_and_commit(self) -> None:
        source = _discover_source_repo()
        before = _source_status(source)

        plan = (source / "planning" / "milestones_migration.md").read_text(encoding="utf-8")
        idx = plan.find("PATCHHARBOR.17c1")
        self.assertGreaterEqual(idx, 0)
        window = plan[idx : idx + 400]
        self.assertIn("Branch Inventory", window)
        self.assertIn("Document migration branch inventory", window)
        self.assertIn("PATCHHARBOR.17c2", plan)

        after = _source_status(source)
        self.assertEqual(after, before)

    def test_branch_inventory_commands_are_documented_as_read_only(self) -> None:
        text = INVENTORY_DOC.read_text(encoding="utf-8")
        required = [
            "git branch --format='%(refname:short)'",
            "git branch -r --format='%(refname:short)'",
            "git branch --show-current",
            "git branch -vv",
            "git branch --merged main",
            "git branch --no-merged main",
            "git show-ref --verify --quiet refs/heads/main",
            "git show-ref --verify --quiet refs/remotes/origin/main",
            "The branch inventory is read-only",
        ]
        for marker in required:
            with self.subTest(marker=marker):
                self.assertIn(marker, text)

    def test_branch_inventory_does_not_document_cleanup_as_executed(self) -> None:
        text = INVENTORY_DOC.read_text(encoding="utf-8")
        forbidden_claims = [
            "branches were deleted",
            "remote branches were deleted",
            "cleanup was executed",
            "pushed branch deletion",
            "git push origin --delete",
            "git branch -D",
        ]
        for marker in forbidden_claims:
            with self.subTest(marker=marker):
                self.assertNotIn(marker, text)

    def test_patchharbor_and_repodossier_branch_inventory_commands_run_read_only(self) -> None:
        source = _discover_source_repo()
        before = _source_status(source)

        repos = [TARGET_ROOT, source]
        commands = [
            ("branch", "--format=%(refname:short)"),
            ("branch", "-r", "--format=%(refname:short)"),
            ("branch", "--show-current"),
            ("branch", "-vv"),
        ]
        for repo in repos:
            for command in commands:
                with self.subTest(repo=repo.name, command=command):
                    result = _git(repo, *command)
                    self.assertEqual(result.returncode, 0, result.stderr)

        after = _source_status(source)
        self.assertEqual(after, before)

    def test_branch_inventory_checks_main_refs_without_requiring_remotes(self) -> None:
        for repo in [TARGET_ROOT, _discover_source_repo()]:
            local_main = _git(repo, "show-ref", "--verify", "--quiet", "refs/heads/main")
            with self.subTest(repo=repo.name, ref="local-main"):
                self.assertIn(local_main.returncode, {0, 1})

            remote_main = _git(repo, "show-ref", "--verify", "--quiet", "refs/remotes/origin/main")
            with self.subTest(repo=repo.name, ref="origin-main"):
                self.assertIn(remote_main.returncode, {0, 1})

    def test_related_docs_link_to_branch_inventory(self) -> None:
        for path in [REPODOSSIER_RELEASE_NOTES, PATCHHARBOR_RELEASE_NOTES, PUBLIC_READINESS]:
            text = path.read_text(encoding="utf-8")
            with self.subTest(path=path):
                self.assertIn("PATCHHARBOR.17c1 applied", text)
                self.assertIn("docs/migration-branch-inventory.md", text)
                self.assertIn("tests/test_migration_branch_inventory.py", text)

    def test_branch_inventory_is_read_only_for_source(self) -> None:
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

    def test_branch_inventory_does_not_store_private_local_values_or_fences(self) -> None:
        text = "\n".join((TARGET_ROOT / relative).read_text(encoding="utf-8") for relative in INVENTORY_PATHS)
        for value in _private_patterns():
            with self.subTest(value=value):
                self.assertNotIn(value, text)
        self.assertNotIn(chr(96) * 3, text)


if __name__ == "__main__":
    unittest.main()
