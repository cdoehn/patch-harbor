from __future__ import annotations

import os
import re
import subprocess
import unittest
from pathlib import Path

TARGET_ROOT = Path(__file__).resolve().parents[1]
ACCEPTANCE_DOC = TARGET_ROOT / "docs" / "dual-repo-boundary-acceptance.md"
PUBLIC_READINESS = TARGET_ROOT / "docs" / "public-readiness-acceptance.md"

SMOKE_EVIDENCE = {
    "PATCHHARBOR.16a1": (
        "docs/dual-repo-discovery-smoke.md",
        "tests/test_dual_repo_discovery_smoke.py",
    ),
    "PATCHHARBOR.16a2": (
        "docs/dual-repo-patch-runner-smoke.md",
        "tests/test_dual_repo_patch_runner_smoke.py",
    ),
    "PATCHHARBOR.16a3": (
        "docs/dual-repo-source-wrapper-smoke.md",
        "tests/test_dual_repo_source_wrapper_smoke.py",
    ),
    "PATCHHARBOR.16a4": (
        "docs/dual-repo-export-smoke.md",
        "tests/test_dual_repo_export_smoke.py",
    ),
}

SOURCE_FILES = [
    "planning/milestones_migration.md",
    "scripts/dev/run_latest_download_patch.sh",
    "scripts/dev/run_patchharbor_patch.sh",
    "scripts/dev/r.sh",
    "scripts/dev/run_repodossier_exports.sh",
    "scripts/dev/install_aliases.sh",
    "docs/installation.md",
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


class PatchHarborDualRepoBoundaryAcceptanceTests(unittest.TestCase):
    def test_boundary_acceptance_doc_exists_and_records_16b1_contract(self) -> None:
        self.assertTrue(ACCEPTANCE_DOC.is_file())
        text = ACCEPTANCE_DOC.read_text(encoding="utf-8")
        required = [
            "PATCHHARBOR.16b1 – Dual repo boundary acceptance",
            "PATCHHARBOR.16a1",
            "PATCHHARBOR.16a2",
            "PATCHHARBOR.16a3",
            "PATCHHARBOR.16a4",
            "Boundary contract",
            "PATCHHARBOR.16b2",
        ]
        for marker in required:
            with self.subTest(marker=marker):
                self.assertIn(marker, text)

    def test_all_16a_smoke_evidence_exists_and_is_linked(self) -> None:
        text = ACCEPTANCE_DOC.read_text(encoding="utf-8")
        for patch_id, paths in SMOKE_EVIDENCE.items():
            with self.subTest(patch_id=patch_id):
                self.assertIn(patch_id, text)
            for relative in paths:
                with self.subTest(relative=relative):
                    self.assertIn(relative, text)
                    self.assertTrue((TARGET_ROOT / relative).is_file())

    def test_public_readiness_and_smoke_docs_link_to_boundary_acceptance(self) -> None:
        docs = [PUBLIC_READINESS] + [TARGET_ROOT / paths[0] for paths in SMOKE_EVIDENCE.values()]
        for path in docs:
            text = path.read_text(encoding="utf-8")
            with self.subTest(path=path):
                self.assertIn("PATCHHARBOR.16b1 applied", text)
                self.assertIn("docs/dual-repo-boundary-acceptance.md", text)
                self.assertIn("tests/test_dual_repo_boundary_acceptance.py", text)

    def test_source_boundary_files_exist_and_source_status_is_read_only(self) -> None:
        source = _discover_source_repo()
        before = _source_status(source)

        for relative in SOURCE_FILES:
            with self.subTest(relative=relative):
                path = source / relative
                self.assertTrue(path.exists())
                if path.is_file():
                    _ = path.read_text(encoding="utf-8")

        after = _source_status(source)
        self.assertEqual(after, before)

    def test_shell_source_files_are_syntax_valid_without_executing_workflows(self) -> None:
        source = _discover_source_repo()
        shell_files = [
            "scripts/dev/run_latest_download_patch.sh",
            "scripts/dev/run_patchharbor_patch.sh",
            "scripts/dev/r.sh",
            "scripts/dev/run_repodossier_exports.sh",
            "scripts/dev/install_aliases.sh",
        ]
        for relative in shell_files:
            with self.subTest(relative=relative):
                result = subprocess.run(
                    ["bash", "-n", str(source / relative)],
                    text=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    check=False,
                )
                self.assertEqual(result.returncode, 0, result.stderr)

    def test_boundary_acceptance_keeps_runtime_code_out_of_scope(self) -> None:
        text = ACCEPTANCE_DOC.read_text(encoding="utf-8")
        expected = [
            "PATCHHARBOR.16b1 does not",
            "change PatchHarbor runtime code",
            "change RepoDossier runtime code",
            "change source wrappers",
            "change aliases",
            "edit shell rc files",
            "run downloaded patches",
            "write real RepoDossier exports",
            "change version numbers",
        ]
        for marker in expected:
            with self.subTest(marker=marker):
                self.assertIn(marker, text)

    def test_boundary_acceptance_does_not_store_private_local_values_or_fences(self) -> None:
        text = "\n".join(
            path.read_text(encoding="utf-8")
            for path in [
                ACCEPTANCE_DOC,
                PUBLIC_READINESS,
                Path(__file__).resolve(),
                *(TARGET_ROOT / paths[0] for paths in SMOKE_EVIDENCE.values()),
            ]
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
