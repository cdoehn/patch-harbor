"""Byte-safe committed Git object capture for Result Bundles."""

from __future__ import annotations

from dataclasses import dataclass

from patchharbor.errors import PatchHarborError, result_bundle_error
from patchharbor.git_commands import run_git_bytes
from patchharbor.models import GitObjectFormat, GitObjectId, RepositoryPath
from patchharbor.repository_paths import (
    RepositoryRelativePath,
    validate_repository_paths,
)


_REGULAR_FILE_MODE = b"100644"
_EXECUTABLE_FILE_MODE = b"100755"
_SUPPORTED_BASE_MODES = frozenset((_REGULAR_FILE_MODE, _EXECUTABLE_FILE_MODE))


@dataclass(frozen=True)
class BaseTreeEntry:
    """One validated regular blob reference in the committed base tree."""

    path: RepositoryRelativePath
    mode: bytes
    object_id: GitObjectId


@dataclass(frozen=True)
class BaseBundleEntry:
    """One byte-exact committed file ready for Result Bundle writing."""

    path: RepositoryRelativePath
    mode: bytes
    object_id: GitObjectId
    content: memoryview

    @property
    def executable(self) -> bool:
        """Whether the committed Git mode marks this file executable."""
        return self.mode == _EXECUTABLE_FILE_MODE


def _error(message: str) -> PatchHarborError:
    return result_bundle_error(message)


def _nul_records(raw: bytes, description: str) -> tuple[bytes, ...]:
    if not raw:
        return ()
    if not raw.endswith(b"\0"):
        raise _error(f"git returned malformed {description}")
    records = tuple(raw[:-1].split(b"\0"))
    if any(not record for record in records):
        raise _error(f"git returned malformed {description}")
    return records


def _object_id(raw: bytes, object_format: GitObjectFormat) -> GitObjectId:
    try:
        value = raw.decode("ascii", errors="strict")
        return GitObjectId(value=value, object_format=object_format)
    except (UnicodeDecodeError, ValueError) as exc:
        raise _error("git returned an invalid base object name") from exc


def parse_base_tree_entries(
    raw: bytes,
    object_format: GitObjectFormat,
) -> tuple[BaseTreeEntry, ...]:
    """Parse, validate, and byte-sort one recursive Git tree response."""
    by_path: dict[bytes, tuple[bytes, GitObjectId]] = {}
    for record in _nul_records(raw, "base tree data"):
        try:
            metadata, raw_path = record.split(b"\t", 1)
            fields = metadata.split(b" ")
            if len(fields) != 3:
                raise ValueError
            mode, object_type, raw_object_id = fields
        except ValueError as exc:
            raise _error("git returned malformed base tree data") from exc

        if mode not in _SUPPORTED_BASE_MODES or object_type != b"blob":
            raise _error("base tree contains an unsupported entry")
        if raw_path in by_path:
            raise _error("git returned ambiguous base tree paths")
        by_path[raw_path] = (mode, _object_id(raw_object_id, object_format))

    paths = validate_repository_paths(by_path)
    return tuple(
        BaseTreeEntry(
            path=path,
            mode=by_path[path.original_bytes][0],
            object_id=by_path[path.original_bytes][1],
        )
        for path in paths
    )


def _reported_size(raw: bytes) -> int:
    if not raw or any(byte not in b"0123456789" for byte in raw):
        raise _error("git returned malformed blob data")
    try:
        return int(raw)
    except (ValueError, OverflowError) as exc:
        raise _error("git returned malformed blob data") from exc


def parse_batch_blob_response(
    raw: bytes,
    entries: tuple[BaseTreeEntry, ...],
) -> tuple[BaseBundleEntry, ...]:
    """Validate one complete ``git cat-file --batch`` byte response."""
    cursor = 0
    response = memoryview(raw)
    materialized: list[BaseBundleEntry] = []

    for entry in entries:
        header_end = raw.find(b"\n", cursor)
        if header_end < 0:
            raise _error("git returned truncated blob data")
        header = raw[cursor:header_end]
        fields = header.split(b" ")
        if len(fields) != 3:
            raise _error("git returned malformed blob data")
        raw_object_id, object_type, raw_size = fields
        observed_object_id = _object_id(
            raw_object_id,
            entry.object_id.object_format,
        )
        size = _reported_size(raw_size)
        if observed_object_id != entry.object_id or object_type != b"blob":
            raise _error("git returned an unexpected base object")

        content_start = header_end + 1
        content_end = content_start + size
        if content_end >= len(response) or response[content_end] != 0x0A:
            raise _error("git returned truncated blob data")
        content = response[content_start:content_end]

        materialized.append(
            BaseBundleEntry(
                path=entry.path,
                mode=entry.mode,
                object_id=entry.object_id,
                content=content,
            )
        )
        cursor = content_end + 1

    if cursor != len(raw):
        raise _error("git returned trailing blob data")
    return tuple(materialized)


def _run_bundle_git(
    repository: RepositoryPath,
    *arguments: str,
    input_bytes: bytes | None = None,
) -> bytes:
    try:
        return run_git_bytes(
            *arguments,
            cwd=repository.value,
            input_bytes=input_bytes,
        )
    except PatchHarborError as exc:
        raise _error("cannot read committed Git objects") from exc


def capture_base_bundle_entries(
    repository: RepositoryPath,
    base_commit: GitObjectId,
) -> tuple[BaseBundleEntry, ...]:
    """Read every supported committed file as exact stored blob bytes."""
    tree_entries = parse_base_tree_entries(
        _run_bundle_git(
            repository,
            "ls-tree",
            "-r",
            "-z",
            "--full-tree",
            str(base_commit),
        ),
        base_commit.object_format,
    )
    if not tree_entries:
        return ()

    response = _run_bundle_git(
        repository,
        "cat-file",
        "--batch",
        input_bytes=b"".join(
            str(entry.object_id).encode("ascii") + b"\n"
            for entry in tree_entries
        ),
    )
    return parse_batch_blob_response(response, tree_entries)
