from __future__ import annotations

import os
import re
import subprocess
import unittest
from pathlib import Path

TARGET_ROOT = Path(__file__).resolve().parents[1]
CHECKLIST_DOC = TARGET_ROOT / "docs" / "migration-completion-checklist.md"
ROLLBACK_DOC = TARGET_ROOT / "docs" / "migration-rollback-notes.md"
PRIVATE_AUDIT_DOC = TARGET_ROOT / "docs" / "dual-repo-private-value-audit.md"
BOUNDARY_DOC = TARGET_ROOT / "docs" / "dual-repo-boundary-acceptance.md"
FAILURE_DOC = TARGET_ROOT / "docs" / "dual-repo-failure-boundary-acceptance.md"
RECOVERY_DOC = TARGET_ROOT / "docs" / "dual-repo-recovery-acceptance.md"
PUBLIC_READINESS = TARGET_ROOT / "docs" / "public-readiness-acceptance.md"

TARGET_CHECKLIST_PATHS = [
    "docs/migration-completion-checklist.md",
    "docs/migration-rollback-notes.md",
    "docs/dual-repo-private-value-audit.md",
    "docs/dual-repo-boundary-acceptance.md",
    "docs/dual-repo-failure-boundary-acceptance.md",
    "docs/dual-repo-recovery-acceptance.md",
    "docs/public-readiness-acceptance.md",
    "tests/test_migration_completion_checklist.py",
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


def _private_patterns() -> list[str]:
    return [
        "/home/" + "christian",
        "christian.doehn" + "@" + "gmail.com",
        "christian" + "@",
        "Think" + "Pad",
        "Blade-" + "15",
        "~/" + "Projekte",
    ]


class PatchHarborMigrationCompletionChecklistTests(unittest.TestCase):
    def test_completion_checklist_doc_exists_and_records_plan_correct_16b2_contract(self) -> None:
        self.assertTrue(CHECKLIST_DOC.is_file())
        text = CHECKLIST_DOC.read_text(encoding="utf-8")
        required = [
            "PATCHHARBOR.16b2 – Migration completion checklist",
            "PATCHHARBOR.16b2-fix1",
            "Migration Completion Checklist",
            "Add migration completion checklist",
            "PATCHHARBOR.16b3-fix1 – Final Migration Acceptance",
        ]
        for marker in required:
            with self.subTest(marker=marker):
                self.assertIn(marker, text)

    def test_source_plan_defines_16b2_completion_checklist_and_commit(self) -> None:
        source = _discover_source_repo()
        before = _source_status(source)

        plan = (source / "planning" / "milestones_migration.md").read_text(encoding="utf-8")
        idx = plan.find("PATCHHARBOR.16b2")
        self.assertGreaterEqual(idx, 0)
        window = plan[idx : idx + 400]
        self.assertIn("Migration Completion Checklist", window)
        self.assertIn("Add migration completion checklist", window)

        after = _source_status(source)
        self.assertEqual(after, before)

    def test_related_docs_link_to_completion_checklist(self) -> None:
        for path in [ROLLBACK_DOC, PRIVATE_AUDIT_DOC, BOUNDARY_DOC, FAILURE_DOC, RECOVERY_DOC, PUBLIC_READINESS]:
            text = path.read_text(encoding="utf-8")
            with self.subTest(path=path):
                self.assertIn("PATCHHARBOR.16b2-fix1 applied", text)
                self.assertIn("docs/migration-completion-checklist.md", text)
                self.assertIn("tests/test_migration_completion_checklist.py", text)

    def test_completion_checklist_covers_required_evidence_and_non_completion_conditions(self) -> None:
        text = CHECKLIST_DOC.read_text(encoding="utf-8")
        required = [
            "Required completion evidence",
            "PATCHHARBOR.16a4-fix2",
            "PATCHHARBOR.16b1-fix1",
            "PATCHHARBOR.16b2-fix1",
            "Explicit non-completion conditions",
            "PATCHHARBOR.16c1 is treated as a real plan slot",
            "final migration acceptance is missing",
        ]
        for marker in required:
            with self.subTest(marker=marker):
                self.assertIn(marker, text)

    def test_completion_checklist_is_read_only_for_source(self) -> None:
        source = _discover_source_repo()
        before = _source_status(source)

        for relative in [
            "planning/milestones_migration.md",
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

    def test_completion_checklist_do_not_store_private_local_values_or_fences(self) -> None:
        text = "\n".join((TARGET_ROOT / relative).read_text(encoding="utf-8") for relative in TARGET_CHECKLIST_PATHS)
        for value in _private_patterns():
            with self.subTest(value=value):
                self.assertNotIn(value, text)
        self.assertNotIn(chr(96) * 3, text)


if __name__ == "__main__":
    unittest.main()
