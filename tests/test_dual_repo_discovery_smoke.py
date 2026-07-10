from __future__ import annotations

import os
import re
import subprocess
import unittest
from pathlib import Path

TARGET_ROOT = Path(__file__).resolve().parents[1]
SMOKE_DOC = TARGET_ROOT / "docs" / "dual-repo-discovery-smoke.md"
PUBLIC_READINESS = TARGET_ROOT / "docs" / "public-readiness-acceptance.md"
PUBLIC_API = TARGET_ROOT / "docs" / "public-api-inventory.md"


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


class PatchHarborDualRepoDiscoverySmokeTests(unittest.TestCase):
    def test_smoke_doc_exists_and_records_16a1_contract(self) -> None:
        self.assertTrue(SMOKE_DOC.is_file())
        text = SMOKE_DOC.read_text(encoding="utf-8")
        required = [
            "PATCHHARBOR.16a1 – Dual repo discovery smoke",
            "Milestone 16 starts end-to-end dual-repository acceptance",
            "PATCHHARBOR_SOURCE_REPO",
            "PATCHHARBOR_TARGET_REPO",
            "sibling `repo_dossier` directory",
            "PATCHHARBOR.16a2",
        ]
        for marker in required:
            with self.subTest(marker=marker):
                self.assertIn(marker, text)

    def test_target_checkout_is_patchharbor_and_public_ready(self) -> None:
        self.assertEqual(_pyproject_name(TARGET_ROOT / "pyproject.toml"), "patchharbor")
        self.assertTrue((TARGET_ROOT / "src" / "patchharbor").is_dir())

        required = [
            "docs/public-readiness-acceptance.md",
            "docs/public-api-inventory.md",
            "docs/cli.md",
            "docs/runner.md",
            "docs/compatibility.md",
            "tests/test_public_readiness_acceptance.py",
            "tests/test_public_api_stability.py",
        ]
        for relative in required:
            with self.subTest(relative=relative):
                self.assertTrue((TARGET_ROOT / relative).is_file())

        self.assertIn("PATCHHARBOR.15c3", PUBLIC_READINESS.read_text(encoding="utf-8"))
        self.assertIn("PATCHHARBOR.15c2 applied", PUBLIC_API.read_text(encoding="utf-8"))

    def test_source_checkout_is_discoverable_as_repodossier(self) -> None:
        source = _discover_source_repo()

        required = [
            "pyproject.toml",
            "src/repodossier",
            "scripts/dev/run_latest_download_patch.sh",
            "scripts/dev/r.sh",
            "docs/installation.md",
            "planning/milestones_migration.md",
            "planning/patchharbor/repodossier-migration-notes.md",
        ]
        for relative in required:
            with self.subTest(relative=relative):
                self.assertTrue((source / relative).exists())

        milestone_text = (source / "planning" / "milestones_migration.md").read_text(encoding="utf-8")
        self.assertIn("PATCHHARBOR.16a1", milestone_text)
        self.assertIn("Dual Repo Discovery Smoke", milestone_text)

    def test_dual_repo_discovery_is_read_only_for_source(self) -> None:
        source = _discover_source_repo()
        before = subprocess.run(
            ["git", "-C", str(source), "status", "--porcelain"],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
        ).stdout

        _ = (source / "planning" / "milestones_migration.md").read_text(encoding="utf-8")
        _ = (source / "scripts" / "dev" / "run_latest_download_patch.sh").read_text(encoding="utf-8")
        _ = (source / "scripts" / "dev" / "r.sh").read_text(encoding="utf-8")

        after = subprocess.run(
            ["git", "-C", str(source), "status", "--porcelain"],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
        ).stdout
        self.assertEqual(after, before)

    def test_related_public_readiness_docs_link_to_dual_repo_smoke(self) -> None:
        for path in [PUBLIC_READINESS, PUBLIC_API]:
            text = path.read_text(encoding="utf-8")
            with self.subTest(path=path):
                self.assertIn("PATCHHARBOR.16a1 applied", text)
                self.assertIn("docs/dual-repo-discovery-smoke.md", text)
                self.assertIn("tests/test_dual_repo_discovery_smoke.py", text)

    def test_dual_repo_discovery_smoke_does_not_store_private_local_values_or_fences(self) -> None:
        text = "\n".join(
            path.read_text(encoding="utf-8")
            for path in [SMOKE_DOC, PUBLIC_READINESS, PUBLIC_API, Path(__file__).resolve()]
        )
        forbidden = [
            "/home/" + "exampleuser",
            "user" + "@",
            "example.user" + "@" + "example.invalid",
            "Example" + "Laptop",
            "Example" + "Machine",
            "~/" + "Projects",
        ]
        for value in forbidden:
            with self.subTest(value=value):
                self.assertNotIn(value, text)
        self.assertNotIn(chr(96) * 3, text)


if __name__ == "__main__":
    unittest.main()
