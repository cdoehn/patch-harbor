from __future__ import annotations

import os
import re
import subprocess
import unittest
from pathlib import Path

TARGET_ROOT = Path(__file__).resolve().parents[1]
VERSION_DOC = TARGET_ROOT / "docs" / "repodossier-follow-up-version-decision.md"
PATCHHARBOR_VERSION_DOC = TARGET_ROOT / "docs" / "patchharbor-version-decision.md"
FINAL_ACCEPTANCE = TARGET_ROOT / "docs" / "final-migration-acceptance.md"
PUBLIC_READINESS = TARGET_ROOT / "docs" / "public-readiness-acceptance.md"

VERSION_DECISION_PATHS = [
    "docs/repodossier-follow-up-version-decision.md",
    "docs/patchharbor-version-decision.md",
    "docs/final-migration-acceptance.md",
    "docs/public-readiness-acceptance.md",
    "tests/test_repodossier_follow_up_version_decision.py",
]


def _pyproject_name_and_version(path: Path) -> tuple[str, str]:
    text = path.read_text(encoding="utf-8")
    name_match = re.search(r'^name\s*=\s*["\']([^"\']+)["\']\s*$', text, re.M)
    version_match = re.search(r'^version\s*=\s*["\']([^"\']+)["\']\s*$', text, re.M)
    if not name_match or not version_match:
        raise AssertionError("pyproject.toml must contain project name and version")
    return name_match.group(1), version_match.group(1)


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
            and _pyproject_name_and_version(path / "pyproject.toml")[0] == "repodossier"
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


class RepoDossierFollowUpVersionDecisionTests(unittest.TestCase):
    def test_follow_up_version_decision_doc_exists_and_records_plan_contract(self) -> None:
        self.assertTrue(VERSION_DOC.is_file())
        text = VERSION_DOC.read_text(encoding="utf-8")
        required = [
            "PATCHHARBOR.17a2 – RepoDossier follow-up version decision",
            "RepoDossier Follow-up Version Decision",
            "Document RepoDossier follow-up release version",
            "planning/milestones_migration.md",
            "PATCHHARBOR.17b1 – PatchHarbor Release Notes",
        ]
        for marker in required:
            with self.subTest(marker=marker):
                self.assertIn(marker, text)

    def test_follow_up_decision_matches_current_repodossier_source_version(self) -> None:
        source = _discover_source_repo()
        name, version = _pyproject_name_and_version(source / "pyproject.toml")
        self.assertEqual(name, "repodossier")

        text = VERSION_DOC.read_text(encoding="utf-8")
        self.assertIn(f"Current source package version | `{version}`", text)
        self.assertIn(f"use `{version}` as the RepoDossier follow-up release candidate", text)

    def test_follow_up_decision_mentions_patchharbor_version_for_pairing_context(self) -> None:
        name, version = _pyproject_name_and_version(TARGET_ROOT / "pyproject.toml")
        self.assertEqual(name, "patchharbor")

        text = VERSION_DOC.read_text(encoding="utf-8")
        self.assertIn(f"PatchHarbor release candidate version | `{version}`", text)

    def test_follow_up_decision_does_not_modify_package_metadata(self) -> None:
        text = VERSION_DOC.read_text(encoding="utf-8")
        expected = [
            "This patch intentionally does not change RepoDossier `pyproject.toml` or PatchHarbor `pyproject.toml`",
            "Source metadata change in this patch | none",
            "Target package metadata change in this patch | none",
            "PATCHHARBOR.17a2 does not",
            "change RepoDossier `pyproject.toml`",
            "change PatchHarbor `pyproject.toml`",
        ]
        for marker in expected:
            with self.subTest(marker=marker):
                self.assertIn(marker, text)

    def test_source_plan_defines_17a2_follow_up_version_decision_and_commit(self) -> None:
        source = _discover_source_repo()
        before = _source_status(source)

        plan = (source / "planning" / "milestones_migration.md").read_text(encoding="utf-8")
        idx = plan.find("PATCHHARBOR.17a2")
        self.assertGreaterEqual(idx, 0)
        window = plan[idx : idx + 400]
        self.assertIn("RepoDossier Follow-up Version Decision", window)
        self.assertIn("Document RepoDossier follow-up release version", window)
        self.assertIn("PATCHHARBOR.17b1", plan)

        after = _source_status(source)
        self.assertEqual(after, before)

    def test_related_docs_link_to_follow_up_version_decision(self) -> None:
        for path in [PATCHHARBOR_VERSION_DOC, FINAL_ACCEPTANCE, PUBLIC_READINESS]:
            text = path.read_text(encoding="utf-8")
            with self.subTest(path=path):
                self.assertIn("PATCHHARBOR.17a2 applied", text)
                self.assertIn("docs/repodossier-follow-up-version-decision.md", text)
                self.assertIn("tests/test_repodossier_follow_up_version_decision.py", text)

    def test_follow_up_version_decision_is_read_only_for_source(self) -> None:
        source = _discover_source_repo()
        before = _source_status(source)

        for relative in [
            "planning/milestones_migration.md",
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

    def test_follow_up_version_decision_does_not_store_private_local_values_or_fences(self) -> None:
        text = "\n".join((TARGET_ROOT / relative).read_text(encoding="utf-8") for relative in VERSION_DECISION_PATHS)
        for value in _private_patterns():
            with self.subTest(value=value):
                self.assertNotIn(value, text)
        self.assertNotIn(chr(96) * 3, text)


if __name__ == "__main__":
    unittest.main()
