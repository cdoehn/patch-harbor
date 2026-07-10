from __future__ import annotations

import os
import re
import subprocess
import unittest
from pathlib import Path

TARGET_ROOT = Path(__file__).resolve().parents[1]
FINAL_DOC = TARGET_ROOT / "docs" / "final-migration-acceptance.md"
CHECKLIST_DOC = TARGET_ROOT / "docs" / "migration-completion-checklist.md"
ROLLBACK_DOC = TARGET_ROOT / "docs" / "migration-rollback-notes.md"
PRIVATE_AUDIT_DOC = TARGET_ROOT / "docs" / "dual-repo-private-value-audit.md"
PUBLIC_READINESS = TARGET_ROOT / "docs" / "public-readiness-acceptance.md"

FINAL_ACCEPTANCE_PATHS = [
    "docs/final-migration-acceptance.md",
    "docs/migration-completion-checklist.md",
    "docs/migration-rollback-notes.md",
    "docs/dual-repo-private-value-audit.md",
    "docs/public-readiness-acceptance.md",
    "tests/test_final_migration_acceptance.py",
]

REQUIRED_EVIDENCE = {
    "PATCHHARBOR.16a4-fix2": (
        "docs/dual-repo-private-value-audit.md",
        "tests/test_dual_repo_private_value_audit.py",
    ),
    "PATCHHARBOR.16b1-fix1": (
        "docs/migration-rollback-notes.md",
        "tests/test_migration_rollback_notes.py",
    ),
    "PATCHHARBOR.16b2-fix1": (
        "docs/migration-completion-checklist.md",
        "tests/test_migration_completion_checklist.py",
    ),
    "PATCHHARBOR.16b3-fix1": (
        "docs/final-migration-acceptance.md",
        "tests/test_final_migration_acceptance.py",
    ),
}


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


class PatchHarborFinalMigrationAcceptanceTests(unittest.TestCase):
    def test_final_acceptance_doc_exists_and_records_plan_correct_16b3_contract(self) -> None:
        self.assertTrue(FINAL_DOC.is_file())
        text = FINAL_DOC.read_text(encoding="utf-8")
        required = [
            "PATCHHARBOR.16b3 – Final migration acceptance",
            "PATCHHARBOR.16b3-fix1",
            "Final Migration Acceptance",
            "Add final migration acceptance",
            "PATCHHARBOR.17a1 – PatchHarbor Version Decision",
        ]
        for marker in required:
            with self.subTest(marker=marker):
                self.assertIn(marker, text)

    def test_source_plan_defines_16b3_final_acceptance_and_next_17a1(self) -> None:
        source = _discover_source_repo()
        before = _source_status(source)

        plan = (source / "planning" / "milestones_migration.md").read_text(encoding="utf-8")
        idx = plan.find("PATCHHARBOR.16b3")
        self.assertGreaterEqual(idx, 0)
        window = plan[idx : idx + 500]
        self.assertIn("Final Migration Acceptance", window)
        self.assertIn("Add final migration acceptance", window)
        self.assertIn("PATCHHARBOR.17a1", plan)

        after = _source_status(source)
        self.assertEqual(after, before)

    def test_source_plan_does_not_require_16c1(self) -> None:
        source = _discover_source_repo()
        plan = (source / "planning" / "milestones_migration.md").read_text(encoding="utf-8")
        self.assertNotIn("PATCHHARBOR.16c1", plan)

    def test_required_final_acceptance_evidence_exists_and_is_listed(self) -> None:
        text = FINAL_DOC.read_text(encoding="utf-8")
        for patch_id, paths in REQUIRED_EVIDENCE.items():
            with self.subTest(patch_id=patch_id):
                self.assertIn(patch_id, text)
            for relative in paths:
                with self.subTest(relative=relative):
                    self.assertIn(relative, text)
                    self.assertTrue((TARGET_ROOT / relative).is_file())

    def test_related_docs_link_to_final_acceptance(self) -> None:
        for path in [CHECKLIST_DOC, ROLLBACK_DOC, PRIVATE_AUDIT_DOC, PUBLIC_READINESS]:
            text = path.read_text(encoding="utf-8")
            with self.subTest(path=path):
                self.assertIn("PATCHHARBOR.16b3-fix1 applied", text)
                self.assertIn("docs/final-migration-acceptance.md", text)
                self.assertIn("tests/test_final_migration_acceptance.py", text)

    def test_final_acceptance_is_read_only_for_source(self) -> None:
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

    def test_final_acceptance_closes_16_without_claiming_release_readiness(self) -> None:
        text = FINAL_DOC.read_text(encoding="utf-8")
        expected = [
            "no PATCHHARBOR.16c1 patch is required",
            "PATCHHARBOR.16c1 is not part of the operative plan",
            "PATCHHARBOR.16b3-fix1 does not",
            "publish a release",
            "change version numbers",
            "PATCHHARBOR.17a1 – PatchHarbor Version Decision",
        ]
        for marker in expected:
            with self.subTest(marker=marker):
                self.assertIn(marker, text)

    def test_final_acceptance_does_not_store_private_local_values_or_fences(self) -> None:
        text = "\n".join((TARGET_ROOT / relative).read_text(encoding="utf-8") for relative in FINAL_ACCEPTANCE_PATHS)
        for value in _private_patterns():
            with self.subTest(value=value):
                self.assertNotIn(value, text)
        self.assertNotIn(chr(96) * 3, text)


if __name__ == "__main__":
    unittest.main()
