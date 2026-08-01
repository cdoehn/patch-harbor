from __future__ import annotations

import os
from pathlib import Path

import pytest

from patchharbor.errors import ExitCode, PatchHarborError
from patchharbor.models import BundlePayload
import patchharbor.payload_files as payload_files
from patchharbor.payload_files import (
    is_safe_bundle_path,
    is_safe_payload_name,
    prepare_payload_files,
    write_bundle_payloads,
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


def test_bundle_payload_is_written_byte_exactly_in_relative_directory(
    tmp_path: Path,
) -> None:
    content = bytes((0, 1, 2, 255)) + b"PATCH"

    assert is_safe_bundle_path("assets/blob.bin")
    write_bundle_payloads(
        (BundlePayload("assets/blob.bin", content),),
        cwd=tmp_path,
    )

    assert (tmp_path / "assets" / "blob.bin").read_bytes() == content


def test_bundle_validates_every_target_before_replacing_any_file(
    tmp_path: Path,
) -> None:
    first_target = tmp_path / "first.bin"
    first_target.write_bytes(b"old")
    blocked_parent = tmp_path / "blocked"
    blocked_parent.write_bytes(b"not a directory")

    with pytest.raises(PatchHarborError) as raised:
        write_bundle_payloads(
            (
                BundlePayload("first.bin", b"new"),
                BundlePayload("blocked/second.bin", b"second"),
            ),
            cwd=tmp_path,
        )

    assert raised.value.exit_code is ExitCode.FILE_PREPARATION_ERROR
    assert first_target.read_bytes() == b"old"
    assert blocked_parent.read_bytes() == b"not a directory"


def test_bundle_stages_every_payload_before_first_target_replace(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payloads = (
        BundlePayload("one.bin", b"one"),
        BundlePayload("nested/two.bin", b"two"),
    )
    real_replace = payload_files._replace_staged_bytes
    calls = 0

    def verify_complete_stage(
        target: Path,
        staged_source: Path,
        *,
        relative_path: str,
    ) -> None:
        nonlocal calls
        calls += 1
        if relative_path == "one.bin":
            stage_root = staged_source.parent
            assert (stage_root / "nested" / "two.bin").read_bytes() == b"two"
        real_replace(
            target,
            staged_source,
            relative_path=relative_path,
        )

    monkeypatch.setattr(
        payload_files,
        "_replace_staged_bytes",
        verify_complete_stage,
    )

    write_bundle_payloads(payloads, cwd=tmp_path)

    assert calls == 2
    assert (tmp_path / "one.bin").read_bytes() == b"one"
    assert (tmp_path / "nested" / "two.bin").read_bytes() == b"two"


def test_bundle_rejects_duplicate_payload_targets_before_writing(
    tmp_path: Path,
) -> None:
    with pytest.raises(PatchHarborError) as raised:
        write_bundle_payloads(
            (
                BundlePayload("Payload.bin", b"one"),
                BundlePayload("payload.bin", b"two"),
            ),
            cwd=tmp_path,
        )

    assert raised.value.exit_code is ExitCode.FILE_PREPARATION_ERROR
    assert list(tmp_path.iterdir()) == []


def test_bundle_does_not_follow_symbolic_link_parent(tmp_path: Path) -> None:
    outside = tmp_path / "outside"
    outside.mkdir()
    linked_parent = tmp_path / "assets"
    try:
        linked_parent.symlink_to(outside, target_is_directory=True)
    except (OSError, NotImplementedError) as exc:
        pytest.skip(f"symbolic links unavailable: {exc}")

    with pytest.raises(PatchHarborError) as raised:
        write_bundle_payloads(
            (BundlePayload("assets/blob.bin", b"payload"),),
            cwd=tmp_path,
        )

    assert raised.value.exit_code is ExitCode.FILE_PREPARATION_ERROR
    assert not (outside / "blob.bin").exists()


def test_bundle_staging_failure_happens_before_any_target_replace(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    target = tmp_path / "first.bin"
    target.write_bytes(b"old")
    real_stage = payload_files._stage_bundle_payload
    calls = 0

    def fail_second_stage(
        stage_root: Path,
        payload: BundlePayload,
    ) -> Path:
        nonlocal calls
        calls += 1
        if calls == 2:
            raise PatchHarborError(
                "cannot write bundle file 'second.bin': denied",
                ExitCode.FILE_PREPARATION_ERROR,
            )
        return real_stage(stage_root, payload)

    monkeypatch.setattr(
        payload_files,
        "_stage_bundle_payload",
        fail_second_stage,
    )

    with pytest.raises(PatchHarborError) as raised:
        write_bundle_payloads(
            (
                BundlePayload("first.bin", b"new"),
                BundlePayload("second.bin", b"second"),
            ),
            cwd=tmp_path,
        )

    assert raised.value.exit_code is ExitCode.FILE_PREPARATION_ERROR
    assert target.read_bytes() == b"old"
    assert not (tmp_path / "second.bin").exists()


def test_bundle_atomic_replace_failure_is_fatal_and_cleans_local_stage(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_replace(*args: object, **kwargs: object) -> None:
        raise PermissionError("replace denied")

    monkeypatch.setattr(payload_files.os, "replace", fail_replace)

    with pytest.raises(PatchHarborError) as raised:
        write_bundle_payloads(
            (BundlePayload("payload.bin", b"payload"),),
            cwd=tmp_path,
        )

    assert raised.value.exit_code is ExitCode.FILE_PREPARATION_ERROR
    assert "replace denied" in str(raised.value)
    assert not (tmp_path / "payload.bin").exists()
    assert list(tmp_path.glob(".patchharbor-*.tmp")) == []
