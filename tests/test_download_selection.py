from __future__ import annotations

import os
import tempfile
import unittest
import zipfile
from pathlib import Path

from patchharbor.download_selection import (
    DEFAULT_ARCHIVE_SUFFIX,
    DEFAULT_DONE_DIRNAME,
    DEFAULT_FAILED_DIRNAME,
    DEFAULT_LEDGER_FILENAME,
    DEFAULT_SCRIPT_SUFFIX,
    DownloadArtifactCandidate,
    DownloadArtifactSelection,
    DownloadSelectionError,
    artifact_type_for_path,
    discover_download_artifacts,
    select_download_artifact,
    select_latest_download_artifact,
    single_script_in_archive,
)


def write_file(directory: Path, name: str, text: str = "echo ok\n", *, mtime: float = 100.0) -> Path:
    path = directory / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    os.utime(path, (mtime, mtime))
    return path


def write_zip(directory: Path, name: str, members: dict[str, str], *, mtime: float = 100.0) -> Path:
    path = directory / name
    with zipfile.ZipFile(path, "w") as archive:
        for member_name, text in members.items():
            archive.writestr(member_name, text)
    os.utime(path, (mtime, mtime))
    return path


class PatchHarborDownloadSelectionTests(unittest.TestCase):
    def test_artifact_type_for_path_accepts_script_and_zip_only(self) -> None:
        self.assertEqual(artifact_type_for_path("patch.sh"), "script")
        self.assertEqual(artifact_type_for_path("patch.zip"), "archive")
        self.assertEqual(DEFAULT_SCRIPT_SUFFIX, ".sh")
        self.assertEqual(DEFAULT_ARCHIVE_SUFFIX, ".zip")
        with self.assertRaisesRegex(DownloadSelectionError, "unsupported download artifact suffix"):
            artifact_type_for_path("patch.txt")

    def test_candidate_from_script_path_reads_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            script = write_file(root, "patch.sh", mtime=123.0)
            candidate = DownloadArtifactCandidate.from_path(script)

            self.assertEqual(candidate.path, script)
            self.assertEqual(candidate.name, "patch.sh")
            self.assertEqual(candidate.artifact_type, "script")
            self.assertTrue(candidate.is_script)
            self.assertFalse(candidate.is_archive)
            self.assertIsNone(candidate.embedded_script_name)
            self.assertEqual(candidate.modified_time, 123.0)
            self.assertGreater(candidate.size_bytes, 0)
            self.assertEqual(candidate.to_mapping()["path"], str(script))

    def test_candidate_from_zip_path_validates_single_visible_script(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            archive = write_zip(root, "patch.zip", {"inside_patch.sh": "echo ok\n"}, mtime=200.0)
            candidate = DownloadArtifactCandidate.from_path(archive)

            self.assertEqual(candidate.path, archive)
            self.assertEqual(candidate.artifact_type, "archive")
            self.assertTrue(candidate.is_archive)
            self.assertEqual(candidate.embedded_script_name, "inside_patch.sh")
            self.assertEqual(single_script_in_archive(archive), "inside_patch.sh")

    def test_zip_validation_rejects_zero_or_multiple_visible_scripts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            no_script = write_zip(root, "no_script.zip", {"README.txt": "x"})
            many_scripts = write_zip(root, "many_scripts.zip", {"a.sh": "a", "b.sh": "b"})

            with self.assertRaisesRegex(DownloadSelectionError, "exactly one visible .sh script, found 0"):
                DownloadArtifactCandidate.from_path(no_script)
            with self.assertRaisesRegex(DownloadSelectionError, "exactly one visible .sh script, found 2"):
                DownloadArtifactCandidate.from_path(many_scripts)

    def test_discover_download_artifacts_ignores_lifecycle_noise(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            done = root / DEFAULT_DONE_DIRNAME
            failed = root / DEFAULT_FAILED_DIRNAME
            done.mkdir()
            failed.mkdir()
            write_file(root, "patch.sh", mtime=100.0)
            write_zip(root, "patch.zip", {"patch_zip.sh": "echo ok\n"}, mtime=90.0)
            write_file(root, "runner.log", mtime=300.0)
            write_file(root, DEFAULT_LEDGER_FILENAME, mtime=400.0)
            write_file(root, ".hidden_patch.sh", mtime=500.0)
            write_file(done, "old_done.sh", mtime=600.0)
            write_file(failed, "old_failed.sh", mtime=700.0)

            candidates = discover_download_artifacts(root)

            self.assertEqual([candidate.name for candidate in candidates], ["patch.sh", "patch.zip"])

    def test_select_latest_download_artifact_uses_mtime_then_path_tiebreaker(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_file(root, "b_patch.sh", mtime=200.0)
            write_file(root, "a_patch.sh", mtime=200.0)
            write_zip(root, "z_patch.zip", {"z_patch.sh": "echo ok\n"}, mtime=100.0)

            selection = select_latest_download_artifact(root)

            self.assertIsNotNone(selection)
            assert selection is not None
            self.assertEqual(selection.selection_source, "latest")
            self.assertEqual(selection.artifact_path.name, "a_patch.sh")
            self.assertEqual(selection.artifact_type, "script")
            self.assertEqual(selection.download_directory, root)

    def test_select_download_artifact_accepts_explicit_path_without_directory_scan(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            explicit = write_file(root, "explicit.sh", mtime=1.0)
            newer = write_file(root, "newer.sh", mtime=999.0)

            selection = select_download_artifact(download_directory=root, explicit_path=explicit)

            self.assertEqual(selection.selection_source, "explicit")
            self.assertEqual(selection.artifact_path, explicit)
            self.assertNotEqual(selection.artifact_path, newer)
            self.assertEqual(selection.to_mapping()["selection_source"], "explicit")

    def test_select_download_artifact_reports_no_candidate(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_file(root, "ignored.log")

            with self.assertRaisesRegex(DownloadSelectionError, "no download patch artifact found"):
                select_download_artifact(download_directory=root)

    def test_invalid_candidate_values_are_rejected(self) -> None:
        with self.assertRaises(DownloadSelectionError):
            DownloadArtifactCandidate(Path("patch.sh"), True, 1, "script")  # type: ignore[arg-type]
        with self.assertRaises(DownloadSelectionError):
            DownloadArtifactCandidate(Path("patch.sh"), 1.0, -1, "script")
        with self.assertRaises(DownloadSelectionError):
            DownloadArtifactCandidate(Path("patch.sh"), 1.0, 1, "bad")
        with self.assertRaises(DownloadSelectionError):
            DownloadArtifactCandidate(Path("patch.zip"), 1.0, 1, "archive")
        with self.assertRaises(DownloadSelectionError):
            DownloadArtifactSelection("candidate")  # type: ignore[arg-type]

    def test_download_selection_files_do_not_store_local_private_values(self) -> None:
        root = Path(__file__).resolve().parents[1]
        checked = [
            root / "src/patchharbor/download_selection.py",
            root / "tests/test_download_selection.py",
        ]
        text = "\n".join(path.read_text(encoding="utf-8") for path in checked)
        forbidden = [
            "/home/" + "exampleuser",
            "user" + "@",
            "example.user" + "@" + "example.invalid",
            "Example" + "Laptop",
            "~/" + "Projects",
            chr(96) * 3,
        ]
        for value in forbidden:
            self.assertNotIn(value, text)
