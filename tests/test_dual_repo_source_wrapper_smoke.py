from __future__ import annotations

import os
import re
import subprocess
import unittest
from pathlib import Path

TARGET_ROOT = Path(__file__).resolve().parents[1]
SMOKE_DOC = TARGET_ROOT / "docs" / "dual-repo-source-wrapper-smoke.md"
DISCOVERY_DOC = TARGET_ROOT / "docs" / "dual-repo-discovery-smoke.md"
PATCH_RUNNER_DOC = TARGET_ROOT / "docs" / "dual-repo-patch-runner-smoke.md"
PUBLIC_READINESS = TARGET_ROOT / "docs" / "public-readiness-acceptance.md"

SOURCE_WRAPPERS = [
    "scripts/dev/run_latest_download_patch.sh",
    "scripts/dev/run_patchharbor_patch.sh",
    "scripts/dev/r.sh",
    "scripts/dev/install_aliases.sh",
]

REMOVED_HELPERS = [
    "scripts/dev/validate_patch_metadata.py",
    "scripts/dev/lint_patch_script.py",
    "scripts/dev/run_latest_download_patch_patchharbor_candidate.sh",
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


class PatchHarborDualRepoSourceWrapperSmokeTests(unittest.TestCase):
    def test_smoke_doc_exists_and_records_16a3_contract(self) -> None:
        self.assertTrue(SMOKE_DOC.is_file())
        text = SMOKE_DOC.read_text(encoding="utf-8")
        required = [
            "PATCHHARBOR.16a3 – Dual repo source wrapper smoke",
            "PATCHHARBOR.16a1 proved dual-repo discovery",
            "PATCHHARBOR.16a2 proved PatchHarbor runner execution",
            "scripts/dev/run_latest_download_patch.sh",
            "scripts/dev/run_patchharbor_patch.sh",
            "scripts/dev/r.sh",
            "scripts/dev/install_aliases.sh",
            "PATCHHARBOR.16a4",
        ]
        for marker in required:
            with self.subTest(marker=marker):
                self.assertIn(marker, text)

    def test_source_wrappers_exist_and_removed_helpers_do_not(self) -> None:
        source = _discover_source_repo()

        for relative in SOURCE_WRAPPERS:
            with self.subTest(relative=relative):
                self.assertTrue((source / relative).is_file())

        for relative in REMOVED_HELPERS:
            with self.subTest(relative=relative):
                self.assertFalse((source / relative).exists())

    def test_source_wrappers_are_bash_syntax_valid_without_executing_them(self) -> None:
        source = _discover_source_repo()
        before = _source_status(source)

        for relative in SOURCE_WRAPPERS:
            with self.subTest(relative=relative):
                result = subprocess.run(
                    ["bash", "-n", str(source / relative)],
                    text=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    check=False,
                )
                self.assertEqual(result.returncode, 0, result.stderr)

        after = _source_status(source)
        self.assertEqual(after, before)

    def test_source_wrappers_keep_expected_boundary_markers(self) -> None:
        source = _discover_source_repo()

        c_runner = (source / "scripts/dev/run_latest_download_patch.sh").read_text(encoding="utf-8")
        patchharbor_wrapper = (source / "scripts/dev/run_patchharbor_patch.sh").read_text(encoding="utf-8")
        r_runner = (source / "scripts/dev/r.sh").read_text(encoding="utf-8")
        alias_installer = (source / "scripts/dev/install_aliases.sh").read_text(encoding="utf-8")

        self.assertIn("run_patchharbor_cli lint-script", c_runner)
        self.assertIn("PY_META_C_RUNNER_14B2", c_runner)
        self.assertIn("patchharbor", patchharbor_wrapper)
        self.assertIn("run-script", patchharbor_wrapper)
        self.assertIn('exec patchharbor run-script "$@"', patchharbor_wrapper)
        self.assertIn("run_repodossier_exports.sh", r_runner)
        self.assertIn("alias c=", alias_installer)
        self.assertIn("alias r=", alias_installer)
        self.assertIn("patchharbor-patch", alias_installer)

    def test_source_wrapper_smoke_is_read_only_for_source(self) -> None:
        source = _discover_source_repo()
        before = _source_status(source)

        for relative in SOURCE_WRAPPERS:
            _ = (source / relative).read_text(encoding="utf-8")

        _ = (source / "planning/milestones_migration.md").read_text(encoding="utf-8")

        after = _source_status(source)
        self.assertEqual(after, before)

    def test_related_docs_link_to_source_wrapper_smoke(self) -> None:
        for path in [DISCOVERY_DOC, PATCH_RUNNER_DOC, PUBLIC_READINESS]:
            text = path.read_text(encoding="utf-8")
            with self.subTest(path=path):
                self.assertIn("PATCHHARBOR.16a3 applied", text)
                self.assertIn("docs/dual-repo-source-wrapper-smoke.md", text)
                self.assertIn("tests/test_dual_repo_source_wrapper_smoke.py", text)

    def test_source_wrapper_smoke_does_not_store_private_local_values_or_fences(self) -> None:
        text = "\n".join(
            path.read_text(encoding="utf-8")
            for path in [SMOKE_DOC, DISCOVERY_DOC, PATCH_RUNNER_DOC, PUBLIC_READINESS, Path(__file__).resolve()]
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
