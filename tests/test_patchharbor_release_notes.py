from __future__ import annotations

import os
import re
import subprocess
import unittest
from pathlib import Path

TARGET_ROOT = Path(__file__).resolve().parents[1]
RELEASE_NOTES = TARGET_ROOT / "docs" / "patchharbor-release-notes.md"
PATCHHARBOR_VERSION = TARGET_ROOT / "docs" / "patchharbor-version-decision.md"
REPODOSSIER_VERSION = TARGET_ROOT / "docs" / "repodossier-follow-up-version-decision.md"
PUBLIC_READINESS = TARGET_ROOT / "docs" / "public-readiness-acceptance.md"

RELEASE_NOTE_PATHS = [
    "docs/patchharbor-release-notes.md",
    "docs/patchharbor-version-decision.md",
    "docs/repodossier-follow-up-version-decision.md",
    "docs/public-readiness-acceptance.md",
    "tests/test_patchharbor_release_notes.py",
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


class PatchHarborReleaseNotesTests(unittest.TestCase):
    def test_release_notes_doc_exists_and_records_plan_contract(self) -> None:
        self.assertTrue(RELEASE_NOTES.is_file())
        text = RELEASE_NOTES.read_text(encoding="utf-8")
        required = [
            "PATCHHARBOR.17b1 – PatchHarbor release notes",
            "PatchHarbor Release Notes",
            "Add PatchHarbor release notes",
            "PATCHHARBOR.17b2 – PatchHarbor Release Build Smoke",
        ]
        for marker in required:
            with self.subTest(marker=marker):
                self.assertIn(marker, text)

    def test_release_notes_match_current_patchharbor_version(self) -> None:
        name, version = _pyproject_name_and_version(TARGET_ROOT / "pyproject.toml")
        self.assertEqual(name, "patchharbor")
        text = RELEASE_NOTES.read_text(encoding="utf-8")
        self.assertIn(f"Version | `{version}`", text)

    def test_release_notes_reference_repodossier_follow_up_version(self) -> None:
        source = _discover_source_repo()
        name, version = _pyproject_name_and_version(source / "pyproject.toml")
        self.assertEqual(name, "repodossier")
        text = RELEASE_NOTES.read_text(encoding="utf-8")
        self.assertIn(f"Related RepoDossier follow-up version | `{version}`", text)

    def test_source_plan_defines_17b1_release_notes_and_commit(self) -> None:
        source = _discover_source_repo()
        before = _source_status(source)

        plan = (source / "planning" / "milestones_migration.md").read_text(encoding="utf-8")
        idx = plan.find("PATCHHARBOR.17b1")
        self.assertGreaterEqual(idx, 0)
        window = plan[idx : idx + 400]
        self.assertIn("PatchHarbor Release Notes", window)
        self.assertIn("Add PatchHarbor release notes", window)
        self.assertIn("PATCHHARBOR.17b2", plan)

        after = _source_status(source)
        self.assertEqual(after, before)

    def test_release_notes_include_required_sections_and_command_surface(self) -> None:
        text = RELEASE_NOTES.read_text(encoding="utf-8")
        required = [
            "Release identity",
            "Summary",
            "Highlights",
            "Migration acceptance evidence",
            "Public command surface",
            "Compatibility notes",
            "Known non-goals for this patch",
            "patchharbor --help",
            "patchharbor --version",
            "patchharbor doctor --repo",
            "patchharbor lint-script",
            "patchharbor run-script",
            "patchharbor audit-public",
            "patchharbor check-env",
        ]
        for marker in required:
            with self.subTest(marker=marker):
                self.assertIn(marker, text)

    def test_release_notes_do_not_claim_build_publish_or_metadata_changes(self) -> None:
        text = RELEASE_NOTES.read_text(encoding="utf-8")
        expected = [
            "PATCHHARBOR.17b1 does not",
            "change `pyproject.toml`",
            "change package version metadata",
            "build a release artifact",
            "publish a release",
            "create or push git tags",
            "clean local branches",
            "clean remote branches",
        ]
        for marker in expected:
            with self.subTest(marker=marker):
                self.assertIn(marker, text)

    def test_related_docs_link_to_release_notes(self) -> None:
        for path in [PATCHHARBOR_VERSION, REPODOSSIER_VERSION, PUBLIC_READINESS]:
            text = path.read_text(encoding="utf-8")
            with self.subTest(path=path):
                self.assertIn("PATCHHARBOR.17b1 applied", text)
                self.assertIn("docs/patchharbor-release-notes.md", text)
                self.assertIn("tests/test_patchharbor_release_notes.py", text)

    def test_release_notes_are_read_only_for_source(self) -> None:
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

    def test_release_notes_do_not_store_private_local_values_or_fences(self) -> None:
        text = "\n".join((TARGET_ROOT / relative).read_text(encoding="utf-8") for relative in RELEASE_NOTE_PATHS)
        for value in _private_patterns():
            with self.subTest(value=value):
                self.assertNotIn(value, text)
        self.assertNotIn(chr(96) * 3, text)


if __name__ == "__main__":
    unittest.main()
