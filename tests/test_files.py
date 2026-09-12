from __future__ import annotations

import os
from pathlib import Path

import pytest

from patchharbor.exit_status import ExitCode, exit_code_for_error
from patchharbor.errors import PatchHarborError
from patchharbor.models import BundlePayload
import patchharbor.platform.filesystem as platform_filesystem
from patchharbor.payload_files import write_bundle_payloads

from tests.platform_support import (
    REQUIRES_POSIX_SPECIAL_FILES,
    create_symlink_or_skip,
)


def test_bundle_payload_is_written_byte_exactly_in_relative_directory(
    tmp_path: Path,
) -> None:
    content = bytes((0, 1, 2, 255)) + b"PATCH"

    write_bundle_payloads(
        (BundlePayload("assets/blob.bin", content),),
        cwd=tmp_path,
    )

    assert (tmp_path / "assets" / "blob.bin").read_bytes() == content


def test_bundle_payload_atomically_replaces_existing_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    target = tmp_path / "payload.bin"
    target.write_bytes(b"old")
    observed: list[tuple[Path, Path]] = []
    real_replace = os.replace

    def recording_replace(
        source: str | os.PathLike[str],
        destination: str | os.PathLike[str],
    ) -> None:
        observed.append((Path(source), Path(destination)))
        real_replace(source, destination)

    monkeypatch.setattr(platform_filesystem.os, "replace", recording_replace)

    write_bundle_payloads(
        (BundlePayload("payload.bin", bytes((0, 255)) + b"new"),),
        cwd=tmp_path,
    )

    assert target.read_bytes() == bytes((0, 255)) + b"new"
    assert len(observed) == 1
    staged, destination = observed[0]
    assert staged.parent == tmp_path
    assert destination == target
    assert not staged.exists()


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

    assert exit_code_for_error(raised.value) is ExitCode.PAYLOAD_PREPARATION_ERROR
    assert first_target.read_bytes() == b"old"
    assert blocked_parent.read_bytes() == b"not a directory"


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

    assert exit_code_for_error(raised.value) is ExitCode.PAYLOAD_PREPARATION_ERROR
    assert list(tmp_path.iterdir()) == []


def test_bundle_does_not_follow_symbolic_link_parent(tmp_path: Path) -> None:
    outside = tmp_path / "outside"
    outside.mkdir()
    linked_parent = tmp_path / "assets"
    create_symlink_or_skip(
        linked_parent,
        outside,
        target_is_directory=True,
    )

    with pytest.raises(PatchHarborError) as raised:
        write_bundle_payloads(
            (BundlePayload("assets/blob.bin", b"payload"),),
            cwd=tmp_path,
        )

    assert exit_code_for_error(raised.value) is ExitCode.PAYLOAD_PREPARATION_ERROR
    assert not (outside / "blob.bin").exists()


def test_bundle_atomic_replace_failure_is_fatal_and_cleans_local_stage(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_replace(*args: object, **kwargs: object) -> None:
        raise PermissionError("replace denied")

    monkeypatch.setattr(platform_filesystem.os, "replace", fail_replace)

    with pytest.raises(PatchHarborError) as raised:
        write_bundle_payloads(
            (BundlePayload("payload.bin", b"payload"),),
            cwd=tmp_path,
        )

    assert exit_code_for_error(raised.value) is ExitCode.PAYLOAD_PREPARATION_ERROR
    assert "cannot replace target" in str(raised.value)
    assert not (tmp_path / "payload.bin").exists()
    assert list(tmp_path.glob(".patchharbor-*.tmp")) == []


def test_bundle_does_not_replace_symbolic_link_target(tmp_path: Path) -> None:
    real_target = tmp_path / "real.bin"
    real_target.write_bytes(b"original")
    link = tmp_path / "payload.bin"
    create_symlink_or_skip(link, real_target)

    with pytest.raises(PatchHarborError) as raised:
        write_bundle_payloads(
            (BundlePayload("payload.bin", b"replacement"),),
            cwd=tmp_path,
        )

    assert exit_code_for_error(raised.value) is ExitCode.PAYLOAD_PREPARATION_ERROR
    assert real_target.read_bytes() == b"original"
    assert link.is_symlink()


@REQUIRES_POSIX_SPECIAL_FILES
def test_posix_fifo_bundle_target_is_not_replaced(tmp_path: Path) -> None:
    target = tmp_path / "payload.bin"
    os.mkfifo(target)

    with pytest.raises(PatchHarborError) as raised:
        write_bundle_payloads(
            (BundlePayload("payload.bin", b"replacement"),),
            cwd=tmp_path,
        )

    assert exit_code_for_error(raised.value) is ExitCode.PAYLOAD_PREPARATION_ERROR
    assert "target is not a regular file" in str(raised.value)
    assert target.exists()
