"""Shared byte-exact reading of validated ZIP bundle payloads."""

from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO, DEFAULT_BUFFER_SIZE
from pathlib import Path
import stat
import zipfile

from patchharbor.bundle_paths import (
    BundlePathError,
    validate_bundle_member_paths,
)
from patchharbor.models import BundlePayload
from patchharbor.platform.errors import describe_os_error
from patchharbor.resource_policy import DEFAULT_RESOURCE_POLICY, ResourcePolicy


class ZipPayloadError(Exception):
    """Base failure while validating or reading one ZIP payload container."""


class NotZipArchiveError(ZipPayloadError):
    """The supplied artifact is not a ZIP archive."""


class InvalidZipArchiveError(ZipPayloadError):
    """The ZIP structure or one original member name is unsafe."""


class ZipResourceLimitError(ZipPayloadError):
    """The declared or observed ZIP data exceeds the shared policy."""


class ZipArchiveReadError(ZipPayloadError):
    """The ZIP artifact or one member could not be read completely."""


@dataclass(frozen=True, slots=True)
class _ValidatedZipMember:
    entry: zipfile.ZipInfo
    relative_path: str
    is_directory: bool


@dataclass(slots=True)
class _ZipReadBudget:
    policy: ResourcePolicy
    total_bytes_read: int = 0

    def validate_declared_entries(
        self,
        entries: list[zipfile.ZipInfo],
    ) -> None:
        if len(entries) > self.policy.max_zip_entries:
            raise ZipResourceLimitError(
                f"more than {self.policy.max_zip_entries} entries"
            )

        declared_total = 0
        for entry in entries:
            if entry.file_size > self.policy.max_content_bytes:
                raise ZipResourceLimitError(
                    f"entry {entry.orig_filename!r} exceeds "
                    f"{self.policy.max_content_bytes} bytes"
                )
            declared_total += entry.file_size
            if declared_total > self.policy.max_zip_total_bytes:
                raise ZipResourceLimitError(
                    "uncompressed data exceeds "
                    f"{self.policy.max_zip_total_bytes} bytes"
                )

    def read_member(
        self,
        archive: zipfile.ZipFile,
        member: _ValidatedZipMember,
    ) -> bytes:
        content = bytearray()
        entry_bytes_read = 0
        try:
            with archive.open(member.entry, "r") as stream:
                while chunk := stream.read(DEFAULT_BUFFER_SIZE):
                    entry_bytes_read += len(chunk)
                    self.total_bytes_read += len(chunk)
                    if entry_bytes_read > self.policy.max_content_bytes:
                        raise ZipResourceLimitError(
                            f"entry {member.relative_path!r} exceeds "
                            f"{self.policy.max_content_bytes} bytes"
                        )
                    if self.total_bytes_read > self.policy.max_zip_total_bytes:
                        raise ZipResourceLimitError(
                            "uncompressed data exceeds "
                            f"{self.policy.max_zip_total_bytes} bytes"
                        )
                    content.extend(chunk)
        except ZipPayloadError:
            raise
        except (
            NotImplementedError,
            OSError,
            RuntimeError,
            zipfile.BadZipFile,
        ) as exc:
            raise ZipArchiveReadError(
                f"cannot read entry {member.relative_path!r}: {exc}"
            ) from exc

        if entry_bytes_read != member.entry.file_size:
            raise ZipArchiveReadError(
                f"entry {member.relative_path!r} size changed while reading"
            )
        return bytes(content)


def _validate_input_artifact(path: Path, policy: ResourcePolicy) -> None:
    try:
        metadata = path.stat()
    except OSError as exc:
        raise ZipArchiveReadError(describe_os_error(exc)) from exc
    if not stat.S_ISREG(metadata.st_mode):
        raise ZipArchiveReadError("not a regular file")
    if metadata.st_size > policy.max_input_artifact_bytes:
        raise ZipResourceLimitError(
            "input artifact exceeds "
            f"{policy.max_input_artifact_bytes} bytes"
        )


def _validate_input_bytes(content: bytes, policy: ResourcePolicy) -> None:
    if len(content) > policy.max_input_artifact_bytes:
        raise ZipResourceLimitError(
            "input artifact exceeds "
            f"{policy.max_input_artifact_bytes} bytes"
        )


def _member_is_directory(entry: zipfile.ZipInfo) -> bool:
    if entry.create_system != 3:
        if entry.is_dir() and entry.file_size != 0:
            raise InvalidZipArchiveError(
                f"directory entry {entry.orig_filename!r} has content"
            )
        return entry.is_dir()

    file_type = stat.S_IFMT(entry.external_attr >> 16)
    if entry.is_dir():
        if entry.file_size != 0:
            raise InvalidZipArchiveError(
                f"directory entry {entry.orig_filename!r} has content"
            )
        if file_type not in (0, stat.S_IFDIR):
            raise InvalidZipArchiveError(
                f"unsupported entry type for {entry.orig_filename!r}"
            )
        return True

    if file_type not in (0, stat.S_IFREG):
        raise InvalidZipArchiveError(
            f"unsupported entry type for {entry.orig_filename!r}"
        )
    return False


def _validate_members(
    entries: list[zipfile.ZipInfo],
) -> tuple[_ValidatedZipMember, ...]:
    member_kinds = tuple(
        (entry, _member_is_directory(entry)) for entry in entries
    )
    try:
        normalized_paths = validate_bundle_member_paths(
            (entry.orig_filename, is_directory)
            for entry, is_directory in member_kinds
        )
    except BundlePathError as exc:
        raise InvalidZipArchiveError(str(exc)) from exc

    return tuple(
        _ValidatedZipMember(
            entry=entry,
            relative_path=relative_path,
            is_directory=is_directory,
        )
        for (entry, is_directory), relative_path in zip(
            member_kinds,
            normalized_paths,
            strict=True,
        )
    )


def _read_open_archive(
    archive: zipfile.ZipFile,
    *,
    policy: ResourcePolicy,
) -> tuple[BundlePayload, ...]:
    try:
        with archive:
            entries = archive.infolist()
            budget = _ZipReadBudget(policy)
            budget.validate_declared_entries(entries)
            members = _validate_members(entries)
            return tuple(
                BundlePayload(
                    relative_path=member.relative_path,
                    content=budget.read_member(archive, member),
                )
                for member in members
                if not member.is_directory
            )
    except ZipPayloadError:
        raise
    except (
        NotImplementedError,
        OSError,
        RuntimeError,
        ValueError,
        zipfile.BadZipFile,
        zipfile.LargeZipFile,
    ) as exc:
        raise ZipArchiveReadError(str(exc)) from exc


def _open_archive(source: object) -> zipfile.ZipFile:
    try:
        return zipfile.ZipFile(source, "r")
    except zipfile.BadZipFile as exc:
        raise NotZipArchiveError("artifact is not a ZIP archive") from exc
    except (
        NotImplementedError,
        OSError,
        RuntimeError,
        ValueError,
        zipfile.LargeZipFile,
    ) as exc:
        raise ZipArchiveReadError(str(exc)) from exc


def read_zip_payloads(
    path: Path,
    *,
    policy: ResourcePolicy = DEFAULT_RESOURCE_POLICY,
) -> tuple[BundlePayload, ...]:
    """Fully validate and read every regular ZIP member in archive order."""
    _validate_input_artifact(path, policy)
    return _read_open_archive(_open_archive(path), policy=policy)


def read_zip_payload_bytes(
    content: bytes,
    *,
    policy: ResourcePolicy = DEFAULT_RESOURCE_POLICY,
) -> tuple[BundlePayload, ...]:
    """Validate ZIP bytes already captured through a stable file boundary."""
    _validate_input_bytes(content, policy)
    return _read_open_archive(_open_archive(BytesIO(content)), policy=policy)


def zip_payload_warnings(
    payloads: tuple[BundlePayload, ...],
    *,
    policy: ResourcePolicy = DEFAULT_RESOURCE_POLICY,
) -> tuple[str, ...]:
    """Return shared large-content warnings without copying payload bytes."""
    return tuple(
        warning
        for payload in payloads
        if (
            warning := policy.large_content_warning(
                f"ZIP entry {payload.relative_path!r}",
                len(payload.content),
            )
        )
        is not None
    )
