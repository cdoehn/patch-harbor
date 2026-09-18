"""Permission contracts for core payload publication; no presentation checks."""
from __future__ import annotations

from io import BytesIO
import os
from pathlib import Path
import stat
import zipfile

import pytest

from patchharbor.models import BundlePayload
from patchharbor.payload_files import PayloadTargetError, write_bundle_payloads
from patchharbor.payload_modes import validate_existing_payload_mode, validate_payload_mode
from patchharbor.platform import filesystem
from patchharbor.zip_payloads import InvalidZipArchiveError, read_zip_payload_bytes

POSIX = pytest.mark.skipif(os.name != "posix", reason="POSIX permission contract")
SAFE = (0o644, 0o755, 0o600, 0o640, 0o750, 0o400, 0o500, 0o444, 0o700)
SHARED = (0o664, 0o666, 0o677, 0o775, 0o777)
SPECIAL = (0o4644, 0o2644, 0o1644, 0o4664, 0o2666, 0o1777)
UNSAFE = (*SHARED, *SPECIAL)


def archive_bytes(mode: int | None, *, host: int = 3) -> bytes:
    data = BytesIO()
    with zipfile.ZipFile(data, "w") as archive:
        info = zipfile.ZipInfo("file.bin")
        info.create_system = host
        # A low-byte flag prevents ZipFile from silently supplying 0600 when
        # the test explicitly requests no high-word Unix metadata.
        info.external_attr = 0x20 if mode is None else (stat.S_IFREG | mode) << 16
        archive.writestr(info, b"new\x00\xff")
    return data.getvalue()


@pytest.mark.parametrize("mode", SAFE)
def test_safe_modes_are_retained_without_normalization(mode: int) -> None:
    assert validate_payload_mode(mode) == mode


@pytest.mark.parametrize("mode", (*UNSAFE, -1, 0o10000, True, "0644", 644.0))
def test_unsafe_or_malformed_permission_fields_are_rejected(mode: object) -> None:
    with pytest.raises(ValueError):
        validate_payload_mode(mode)


@POSIX
@pytest.mark.parametrize("mode", (*SAFE, *SHARED))
def test_existing_ordinary_mode_wins_over_zip_mode(tmp_path: Path, mode: int) -> None:
    target = tmp_path / "file.bin"
    target.write_bytes(b"old")
    target.chmod(mode)
    try:
        write_bundle_payloads((BundlePayload("file.bin", b"new", 0o755),), cwd=tmp_path)
        assert stat.S_IMODE(target.stat().st_mode) == mode
        assert target.read_bytes() == b"new"
    finally:
        target.chmod(0o600)


@POSIX
@pytest.mark.parametrize("mode", SAFE)
def test_new_file_receives_exact_explicit_zip_permissions(tmp_path: Path, mode: int) -> None:
    payloads = read_zip_payload_bytes(archive_bytes(mode))
    assert payloads[0].unix_mode == mode
    write_bundle_payloads(payloads, cwd=tmp_path)
    target = tmp_path / "file.bin"
    try:
        assert stat.S_IMODE(target.stat().st_mode) == mode
        assert target.read_bytes() == b"new\x00\xff"
    finally:
        target.chmod(0o600)


@POSIX
@pytest.mark.parametrize("host", (0, 3, 10))
def test_missing_unix_metadata_defaults_to_644(tmp_path: Path, host: int) -> None:
    payloads = read_zip_payload_bytes(archive_bytes(None, host=host))
    assert payloads[0].unix_mode is None
    write_bundle_payloads(payloads, cwd=tmp_path)
    assert stat.S_IMODE((tmp_path / "file.bin").stat().st_mode) == 0o644


def test_non_unix_high_word_never_grants_unix_executability() -> None:
    payload = read_zip_payload_bytes(archive_bytes(0o777, host=0))[0]
    assert payload.unix_mode is None


@pytest.mark.parametrize("mode", UNSAFE)
def test_unsafe_unix_archive_modes_are_rejected(mode: int) -> None:
    with pytest.raises(InvalidZipArchiveError):
        read_zip_payload_bytes(archive_bytes(mode))


@POSIX
@pytest.mark.parametrize("mode", SPECIAL)
def test_existing_special_bits_stop_entire_preflight(tmp_path: Path, mode: int) -> None:
    first = tmp_path / "first.bin"
    first.write_bytes(b"unchanged")
    first.chmod(0o644)
    unsafe = tmp_path / "unsafe.bin"
    unsafe.write_bytes(b"old")
    unsafe.chmod(mode)
    try:
        with pytest.raises(PayloadTargetError):
            write_bundle_payloads((BundlePayload("first.bin", b"new"),
                                   BundlePayload("unsafe.bin", b"bad")), cwd=tmp_path)
        assert first.read_bytes() == b"unchanged"
        assert unsafe.read_bytes() == b"old"
        assert stat.S_IMODE(unsafe.stat().st_mode) == mode
        assert not list(tmp_path.glob(".patchharbor-*.tmp"))
    finally:
        unsafe.chmod(0o600)


@pytest.mark.parametrize("mode", UNSAFE)
def test_direct_payload_cannot_bypass_mode_validation(tmp_path: Path, mode: int) -> None:
    with pytest.raises(PayloadTargetError):
        write_bundle_payloads((BundlePayload("nested/file.bin", b"new", mode),), cwd=tmp_path)
    assert list(tmp_path.iterdir()) == []


@POSIX
def test_default_atomic_writer_remains_private(tmp_path: Path) -> None:
    for name in ("state.json", "registry.json", "config.json"):
        target = tmp_path / name
        target.write_bytes(b"old")
        target.chmod(0o644)
        filesystem.atomic_replace_bytes(target, b"private")
        assert target.read_bytes() == b"private"
        assert stat.S_IMODE(target.stat().st_mode) == 0o600


@POSIX
def test_mode_is_already_correct_at_atomic_publication(tmp_path: Path, monkeypatch) -> None:
    target = tmp_path / "file.bin"
    target.write_bytes(b"old")
    target.chmod(0o644)
    replace = filesystem.os.replace
    observed = []
    def publish(source, destination):
        observed.append(stat.S_IMODE(Path(source).stat().st_mode))
        assert target.read_bytes() == b"old"
        replace(source, destination)
    monkeypatch.setattr(filesystem.os, "replace", publish)
    write_bundle_payloads((BundlePayload("file.bin", b"new"),), cwd=tmp_path)
    assert observed == [0o644]


def test_windows_boundary_does_not_emulate_posix_mode(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(filesystem, "is_windows", lambda: True)
    def forbidden(*args):
        raise AssertionError("Windows must not call fchmod")
    monkeypatch.setattr(filesystem.os, "fchmod", forbidden, raising=False)
    target = tmp_path / "file.bin"
    target.write_bytes(b"old")
    write_bundle_payloads((BundlePayload("file.bin", b"new", 0o755),), cwd=tmp_path)
    assert target.read_bytes() == b"new"


def test_existing_policy_preserves_all_ordinary_bits_but_rejects_special_bits() -> None:
    for mode in range(0o1000):
        assert validate_existing_payload_mode(mode) == mode
    for special in (0o1000, 0o2000, 0o4000, 0o7000):
        for ordinary in (0o000, 0o644, 0o664, 0o666, 0o777):
            with pytest.raises(ValueError):
                validate_existing_payload_mode(special | ordinary)


@pytest.mark.parametrize("mode", (-1, 0o10000, 0o100644, True, False, "0664", 664.0, None))
def test_existing_policy_rejects_invalid_permission_types_and_ranges(mode: object) -> None:
    with pytest.raises(ValueError):
        validate_existing_payload_mode(mode)


@POSIX
@pytest.mark.parametrize("requested", (0o664, 0o666, 0o777, 0o4644))
def test_existing_shared_target_does_not_legalize_unsafe_request(tmp_path: Path, requested: int) -> None:
    target = tmp_path / "shared.bin"
    target.write_bytes(b"old")
    target.chmod(0o664)
    with pytest.raises(PayloadTargetError):
        write_bundle_payloads((BundlePayload("shared.bin", b"new", requested),), cwd=tmp_path)
    assert target.read_bytes() == b"old"
    assert stat.S_IMODE(target.stat().st_mode) == 0o664
    assert not list(tmp_path.glob(".patchharbor-*.tmp"))


@POSIX
def test_shared_existing_and_new_payload_have_distinct_mode_policies(tmp_path: Path) -> None:
    target = tmp_path / "existing.bin"
    target.write_bytes(b"old")
    target.chmod(0o664)
    previous = os.umask(0o002)
    try:
        write_bundle_payloads((BundlePayload("existing.bin", b"changed", 0o644),
                               BundlePayload("new.bin", b"new"),
                               BundlePayload("executable.sh", b"#!/bin/sh\n", 0o755)), cwd=tmp_path)
    finally:
        os.umask(previous)
    assert target.read_bytes() == b"changed"
    assert stat.S_IMODE(target.stat().st_mode) == 0o664
    assert stat.S_IMODE((tmp_path / "new.bin").stat().st_mode) == 0o644
    assert stat.S_IMODE((tmp_path / "executable.sh").stat().st_mode) == 0o755
