from __future__ import annotations

import os
from pathlib import Path

import pytest

from patchharbor.errors import ExitCode, PatchHarborError
import patchharbor.payload_files as payload_files
from patchharbor.payload_files import (
    is_safe_payload_name,
    prepare_payload_files,
    write_payload_files,
)


@pytest.mark.parametrize(
    "name",
    (
        "file.txt",
        ".env",
        "UPPER-lower_123.data",
        "COM0.txt",
        "LPT10",
    ),
)
def test_safe_payload_names_are_portable(name: str) -> None:
    assert is_safe_payload_name(name)


@pytest.mark.parametrize(
    "name",
    (
        "",
        ".",
        "..",
        "folder/file.txt",
        r"folder\file.txt",
        "/absolute.txt",
        "name.",
        "name ",
        "CON",
        "con.txt",
        "PRN.log",
        "AUX",
        "NUL.data",
        "COM1",
        "com9.txt",
        "LPT1",
        "lpt9.log",
        "ä.txt",
        "a" * 129,
    ),
)
def test_unsafe_payload_names_are_rejected(name: str) -> None:
    assert not is_safe_payload_name(name)


def test_payload_is_staged_in_target_directory_and_atomically_replaced(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    target = tmp_path / "payload.txt"
    target.write_text("old", encoding="utf-8")
    observed: list[tuple[Path, Path]] = []
    real_replace = os.replace

    def recording_replace(source: str | os.PathLike[str], destination: str | os.PathLike[str]) -> None:
        observed.append((Path(source), Path(destination)))
        real_replace(source, destination)

    monkeypatch.setattr(payload_files.os, "replace", recording_replace)

    write_payload_files((("payload.txt", "new"),), cwd=tmp_path)

    assert target.read_text(encoding="utf-8") == "new"
    assert len(observed) == 1
    staged, destination = observed[0]
    assert staged.parent == tmp_path
    assert destination == target
    assert not staged.exists()


def test_non_regular_payload_target_is_not_replaced(tmp_path: Path) -> None:
    target = tmp_path / "payload.txt"
    target.mkdir()

    with pytest.raises(PatchHarborError) as raised:
        write_payload_files((("payload.txt", "content"),), cwd=tmp_path)

    assert raised.value.exit_code is ExitCode.FILE_PREPARATION_ERROR
    assert "target is not a regular file" in str(raised.value)
    assert target.is_dir()


def test_symbolic_link_payload_target_is_not_replaced(tmp_path: Path) -> None:
    real_target = tmp_path / "real.txt"
    real_target.write_text("original", encoding="utf-8")
    link = tmp_path / "payload.txt"
    try:
        link.symlink_to(real_target)
    except (OSError, NotImplementedError) as exc:
        pytest.skip(f"symbolic links unavailable: {exc}")

    with pytest.raises(PatchHarborError) as raised:
        write_payload_files((("payload.txt", "replacement"),), cwd=tmp_path)

    assert raised.value.exit_code is ExitCode.FILE_PREPARATION_ERROR
    assert "target is not a regular file" in str(raised.value)
    assert real_target.read_text(encoding="utf-8") == "original"
    assert link.is_symlink()


def test_staging_failure_is_a_file_preparation_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    target = tmp_path / "payload.txt"
    target.write_text("original", encoding="utf-8")

    def fail_staging(*args: object, **kwargs: object) -> object:
        raise PermissionError("denied")

    monkeypatch.setattr(payload_files.tempfile, "NamedTemporaryFile", fail_staging)

    with pytest.raises(PatchHarborError) as raised:
        write_payload_files((("payload.txt", "replacement"),), cwd=tmp_path)

    assert raised.value.exit_code is ExitCode.FILE_PREPARATION_ERROR
    assert "cannot write FILE 'payload.txt': denied" == str(raised.value)
    assert target.read_text(encoding="utf-8") == "original"


def test_failed_atomic_replace_removes_staged_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    target = tmp_path / "payload.txt"
    target.write_text("original", encoding="utf-8")

    def fail_replace(*args: object, **kwargs: object) -> None:
        raise PermissionError("replace denied")

    monkeypatch.setattr(payload_files.os, "replace", fail_replace)

    with pytest.raises(PatchHarborError) as raised:
        write_payload_files((("payload.txt", "replacement"),), cwd=tmp_path)

    assert raised.value.exit_code is ExitCode.FILE_PREPARATION_ERROR
    assert str(raised.value) == (
        "cannot write FILE 'payload.txt': replace denied"
    )
    assert target.read_text(encoding="utf-8") == "original"
    assert list(tmp_path.glob(".patchharbor-*.tmp")) == []


def test_prepare_payload_files_discards_invalid_name_with_warning() -> None:
    prepared, warnings = prepare_payload_files(
        (("../outside.txt", "ignored"), ("good.txt", "retained"))
    )

    assert prepared == (("good.txt", "retained"),)
    assert warnings == (
        "discarded FILE '../outside.txt': invalid file name",
    )


def test_prepare_payload_files_reports_large_payload(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(payload_files, "PAYLOAD_WARNING_BYTES", 3)
    monkeypatch.setattr(payload_files, "MAX_PAYLOAD_BYTES", 10)

    prepared, warnings = prepare_payload_files((("large.txt", "1234"),))

    assert prepared == (("large.txt", "1234"),)
    assert warnings == ("FILE 'large.txt' is large (4 bytes)",)


def test_prepare_payload_files_rejects_hard_budget(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(payload_files, "MAX_PAYLOAD_BYTES", 3)

    with pytest.raises(PatchHarborError) as raised:
        prepare_payload_files((("too-large.txt", "1234"),))

    assert raised.value.exit_code is ExitCode.SOURCE_ERROR
    assert str(raised.value) == "FILE 'too-large.txt' exceeds the 3 byte limit"
