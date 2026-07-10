from __future__ import annotations

from email.parser import Parser
import os
import re
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

TARGET_ROOT = Path(__file__).resolve().parents[1]
BUILD_SMOKE_DOC = TARGET_ROOT / "docs" / "patchharbor-release-build-smoke.md"
RELEASE_NOTES = TARGET_ROOT / "docs" / "patchharbor-release-notes.md"
PATCHHARBOR_VERSION = TARGET_ROOT / "docs" / "patchharbor-version-decision.md"
PUBLIC_READINESS = TARGET_ROOT / "docs" / "public-readiness-acceptance.md"

BUILD_SMOKE_PATHS = [
    "docs/patchharbor-release-build-smoke.md",
    "docs/patchharbor-release-notes.md",
    "docs/patchharbor-version-decision.md",
    "docs/public-readiness-acceptance.md",
    "tests/test_patchharbor_release_build_smoke.py",
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
        "/home/" + "exampleuser",
        "example.user" + "@" + "example.invalid",
        "user" + "@",
        "Example" + "Laptop",
        "Example" + "Machine",
        "~/" + "Projects",
    ]


def _build_wheel(out_dir: Path) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = f"{TARGET_ROOT / 'src'}{os.pathsep}{env.get('PYTHONPATH', '')}".rstrip(os.pathsep)
    return subprocess.run(
        [
            sys.executable,
            "-m",
            "pip",
            "wheel",
            "--no-deps",
            "--no-build-isolation",
            "--wheel-dir",
            str(out_dir),
            str(TARGET_ROOT),
        ],
        cwd=TARGET_ROOT,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def _wheel_metadata(wheel: Path) -> tuple[dict[str, str], str, list[str]]:
    with zipfile.ZipFile(wheel) as archive:
        names = archive.namelist()
        metadata_name = next(name for name in names if name.endswith(".dist-info/METADATA"))
        entry_points_name = next(name for name in names if name.endswith(".dist-info/entry_points.txt"))
        metadata = Parser().parsestr(archive.read(metadata_name).decode("utf-8"))
        entry_points = archive.read(entry_points_name).decode("utf-8")
    return dict(metadata.items()), entry_points, names


class PatchHarborReleaseBuildSmokeTests(unittest.TestCase):
    def test_build_smoke_doc_exists_and_records_plan_contract(self) -> None:
        self.assertTrue(BUILD_SMOKE_DOC.is_file())
        text = BUILD_SMOKE_DOC.read_text(encoding="utf-8")
        required = [
            "PATCHHARBOR.17b2 – PatchHarbor release build smoke",
            "PatchHarbor Release Build Smoke",
            "Add PatchHarbor release build smoke",
            "python -m pip wheel",
            "PATCHHARBOR.17b3 – RepoDossier Follow-up Release Notes",
        ]
        for marker in required:
            with self.subTest(marker=marker):
                self.assertIn(marker, text)

    def test_source_plan_defines_17b2_release_build_smoke_and_commit(self) -> None:
        source = _discover_source_repo()
        before = _source_status(source)

        plan = (source / "planning" / "milestones_migration.md").read_text(encoding="utf-8")
        idx = plan.find("PATCHHARBOR.17b2")
        self.assertGreaterEqual(idx, 0)
        window = plan[idx : idx + 400]
        self.assertIn("PatchHarbor Release Build Smoke", window)
        self.assertIn("Add PatchHarbor release build smoke", window)
        self.assertIn("PATCHHARBOR.17b3", plan)

        after = _source_status(source)
        self.assertEqual(after, before)

    def test_local_wheel_build_smoke_produces_inspectable_patchharbor_wheel(self) -> None:
        name, version = _pyproject_name_and_version(TARGET_ROOT / "pyproject.toml")
        self.assertEqual(name, "patchharbor")

        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp) / "dist"
            out_dir.mkdir()
            result = _build_wheel(out_dir)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

            wheels = sorted(out_dir.glob("*.whl"))
            self.assertEqual(len(wheels), 1, [wheel.name for wheel in wheels])
            wheel = wheels[0]
            self.assertTrue(wheel.name.startswith("patchharbor-"), wheel.name)

            metadata, entry_points, names = _wheel_metadata(wheel)
            self.assertEqual(metadata["Name"], "patchharbor")
            self.assertEqual(metadata["Version"], version)
            self.assertIn("patchharbor = patchharbor.cli:main", entry_points)
            self.assertIn("patchharbor/cli.py", names)
            self.assertIn("patchharbor/__main__.py", names)

    def test_release_build_smoke_matches_version_decision_and_release_notes(self) -> None:
        _name, version = _pyproject_name_and_version(TARGET_ROOT / "pyproject.toml")
        build_text = BUILD_SMOKE_DOC.read_text(encoding="utf-8")
        release_text = RELEASE_NOTES.read_text(encoding="utf-8")
        version_text = PATCHHARBOR_VERSION.read_text(encoding="utf-8")

        self.assertIn(f"Version | `{version}`", build_text)
        self.assertIn(f"Version | `{version}`", release_text)
        self.assertIn(f"Current package version | `{version}`", version_text)

    def test_related_docs_link_to_release_build_smoke(self) -> None:
        for path in [RELEASE_NOTES, PATCHHARBOR_VERSION, PUBLIC_READINESS]:
            text = path.read_text(encoding="utf-8")
            with self.subTest(path=path):
                self.assertIn("PATCHHARBOR.17b2 applied", text)
                self.assertIn("docs/patchharbor-release-build-smoke.md", text)
                self.assertIn("tests/test_patchharbor_release_build_smoke.py", text)

    def test_release_build_smoke_does_not_claim_publish_tag_or_metadata_changes(self) -> None:
        text = BUILD_SMOKE_DOC.read_text(encoding="utf-8")
        expected = [
            "PATCHHARBOR.17b2 is a build smoke only",
            "publish a release",
            "upload to PyPI",
            "create or push git tags",
            "change `pyproject.toml`",
            "change version metadata",
            "clean local branches",
            "clean remote branches",
        ]
        for marker in expected:
            with self.subTest(marker=marker):
                self.assertIn(marker, text)

    def test_release_build_smoke_is_read_only_for_source(self) -> None:
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

    def test_release_build_smoke_does_not_store_private_local_values_or_fences(self) -> None:
        text = "\n".join((TARGET_ROOT / relative).read_text(encoding="utf-8") for relative in BUILD_SMOKE_PATHS)
        for value in _private_patterns():
            with self.subTest(value=value):
                self.assertNotIn(value, text)
        self.assertNotIn(chr(96) * 3, text)


if __name__ == "__main__":
    unittest.main()
