from __future__ import annotations

from io import StringIO
from pathlib import Path
import stat
import zipfile

import pytest

from patchharbor.errors import ExitCode, PatchHarborError
import patchharbor.application as script_application
from patchharbor.application import discover_directory_candidates, run_script_path
import patchharbor.bundles as script_bundles


REQUIRED_MARKER = "# PATCHHARBOR"


def _write_zip(path: Path, entries: list[tuple[str, str]]) -> None:
    with zipfile.ZipFile(path, "w") as archive:
        for name, content in entries:
            archive.writestr(name, content)


def _run_path(path: Path, cwd: Path, *, timeout_seconds: float = 1) -> int:
    return run_script_path(
        path,
        cwd=cwd,
        timeout_seconds=timeout_seconds,
        selection_input=StringIO(),
        selection_output=StringIO(),
    )


def test_directory_discovery_includes_zip_with_valid_script(tmp_path: Path) -> None:
    archive_path = tmp_path / "scripts.zip"
    _write_zip(
        archive_path,
        [("run.sh", f"{REQUIRED_MARKER}\n")],
    )

    candidates = discover_directory_candidates(tmp_path)

    assert [candidate.path for candidate in candidates] == [archive_path]


def test_zip_without_scripts_is_rejected_even_with_binary_payloads(
    tmp_path: Path,
) -> None:
    nested_path = tmp_path / "nested.zip"
    _write_zip(nested_path, [("nested.sh", f"{REQUIRED_MARKER}\n")])

    archive_path = tmp_path / "payloads.zip"
    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.writestr("folder/", b"")
        archive.writestr("notes.txt", "not executable\n")
        archive.writestr("nested.zip", nested_path.read_bytes())

    with pytest.raises(PatchHarborError) as raised:
        _run_path(archive_path, tmp_path)

    assert raised.value.exit_code is ExitCode.NO_VALID_SCRIPT
    assert str(raised.value).startswith("no valid PatchHarbor scripts found")


@pytest.mark.parametrize("entry_type", (stat.S_IFLNK, stat.S_IFIFO))
def test_zip_rejects_links_and_special_entries_before_any_script_runs(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    entry_type: int,
) -> None:
    archive_path = tmp_path / "linked.zip"
    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.writestr("run.sh", f"{REQUIRED_MARKER}\n")
        special = zipfile.ZipInfo("special.bin")
        special.create_system = 3
        special.external_attr = (entry_type | 0o777) << 16
        archive.writestr(special, b"target")

    executed: list[str] = []
    monkeypatch.setattr(
        script_application,
        "execute_script_text",
        lambda script_text, **kwargs: executed.append(script_text) or 0,
    )

    with pytest.raises(PatchHarborError) as raised:
        _run_path(archive_path, tmp_path)

    assert raised.value.exit_code is ExitCode.SOURCE_ERROR
    assert "unsupported entry type" in str(raised.value)
    assert executed == []


@pytest.mark.parametrize(
    "member_name",
    (
        "../escape.bin",
        "/absolute.bin",
        "folder\\payload.bin",
        "CON/data.bin",
        "folder/./payload.bin",
        f"{'a' * 129}/payload.bin",
    ),
)
def test_zip_rejects_unsafe_member_paths_before_execution(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    member_name: str,
) -> None:
    archive_path = tmp_path / "unsafe.zip"
    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.writestr("run.sh", f"{REQUIRED_MARKER}\n")
        archive.writestr("safe.bin", b"must-not-be-written")
        archive.writestr(member_name, b"payload")

    executed: list[str] = []
    monkeypatch.setattr(
        script_application,
        "execute_script_text",
        lambda script_text, **kwargs: executed.append(script_text) or 0,
    )

    with pytest.raises(PatchHarborError) as raised:
        _run_path(archive_path, tmp_path)

    assert raised.value.exit_code is ExitCode.SOURCE_ERROR
    assert "invalid PatchBundle" in str(raised.value)
    assert executed == []
    assert not (tmp_path / "safe.bin").exists()


@pytest.mark.parametrize(
    "member_names",
    (
        ("payload.bin", "payload.bin"),
        ("Payload.bin", "payload.bin"),
        ("Assets/one.bin", "assets/two.bin"),
        ("assets", "assets/two.bin"),
    ),
)
def test_zip_rejects_duplicate_and_ambiguous_member_trees(
    tmp_path: Path,
    member_names: tuple[str, str],
) -> None:
    archive_path = tmp_path / "ambiguous.zip"
    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.writestr("run.sh", f"{REQUIRED_MARKER}\n")
        archive.writestr(member_names[0], b"one")
        if member_names[0] == member_names[1]:
            with pytest.warns(UserWarning):
                archive.writestr(member_names[1], b"two")
        else:
            archive.writestr(member_names[1], b"two")

    with pytest.raises(PatchHarborError) as raised:
        _run_path(archive_path, tmp_path)

    assert raised.value.exit_code is ExitCode.SOURCE_ERROR
    assert "invalid PatchBundle" in str(raised.value)


def test_bundle_write_failure_prevents_every_script_execution(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    archive_path = tmp_path / "write-failure.zip"
    _write_zip(
        archive_path,
        [
            ("run.sh", f"{REQUIRED_MARKER}\n"),
            ("payload.txt", "payload"),
        ],
    )
    executed: list[str] = []

    def fail_payload_write(*args: object, **kwargs: object) -> None:
        raise PatchHarborError(
            "cannot write bundle file 'payload.txt': denied",
            ExitCode.FILE_PREPARATION_ERROR,
        )

    monkeypatch.setattr(
        script_application,
        "write_bundle_payloads",
        fail_payload_write,
    )
    monkeypatch.setattr(
        script_application,
        "execute_script_text",
        lambda script_text, **kwargs: executed.append(script_text) or 0,
    )

    with pytest.raises(PatchHarborError) as raised:
        _run_path(archive_path, tmp_path)

    assert raised.value.exit_code is ExitCode.FILE_PREPARATION_ERROR
    assert executed == []


@pytest.mark.parametrize(
    ("constant_name", "limit", "entries"),
    [
        (
            "MAX_ZIP_ENTRIES",
            1,
            [("one.txt", "1"), ("two.txt", "2")],
        ),
        (
            "MAX_ZIP_ENTRY_BYTES",
            4,
            [("large.txt", "12345")],
        ),
        (
            "MAX_ZIP_TOTAL_BYTES",
            8,
            [("one.txt", "12345"), ("two.txt", "67890")],
        ),
    ],
)
def test_zip_resource_budgets_fail_before_execution(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    constant_name: str,
    limit: int,
    entries: list[tuple[str, str]],
) -> None:
    archive_path = tmp_path / "limited.zip"
    _write_zip(archive_path, entries)
    monkeypatch.setattr(script_bundles, constant_name, limit)

    with pytest.raises(PatchHarborError) as raised:
        _run_path(archive_path, tmp_path)

    assert raised.value.exit_code is ExitCode.SOURCE_ERROR
    assert "resource limit exceeded" in str(raised.value)


def test_each_zip_script_receives_its_own_timeout(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    archive_path = tmp_path / "scripts.zip"
    _write_zip(
        archive_path,
        [
            ("first.sh", f"{REQUIRED_MARKER}\n"),
            ("second.sh", f"{REQUIRED_MARKER}\n"),
        ],
    )
    observed: list[tuple[str, str, float]] = []

    def fake_execute_script_text(
        script_text: str,
        *,
        suffix: str,
        cwd: Path,
        timeout_seconds: float,
    ) -> int:
        observed.append((script_text, suffix, timeout_seconds))
        return 0

    monkeypatch.setattr(
        script_application, "execute_script_text", fake_execute_script_text
    )

    result = _run_path(archive_path, tmp_path, timeout_seconds=7.5)

    assert result == 0
    assert len(observed) == 2
    assert [timeout for _, _, timeout in observed] == [7.5, 7.5]
