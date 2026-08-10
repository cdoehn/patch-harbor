"""Byte-exact capture of supported Git repository state."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import os
import stat

from patchharbor.errors import (
    PatchHarborError,
    repository_resolution_error,
    unsupported_repository_state_error,
)
from patchharbor.git_commands import (
    nul_records as _nul_records,
    read_boolean_config,
    run_git_bytes as _run_git_bytes,
)
from patchharbor.models import (
    GitObjectFormat,
    GitObjectId,
    RepositoryPath,
    StagedRecord,
    UnstagedRecord,
    UntrackedRecord,
)


def _error(message: str) -> PatchHarborError:
    return repository_resolution_error(message)


class _UnsupportedState(Enum):
    INDEX = "repository index state is not supported"
    SPARSE = "sparse repository state is not supported"
    ENTRY_TYPE = "repository contains an unsupported entry type"


def _unsupported(state: _UnsupportedState) -> PatchHarborError:
    return unsupported_repository_state_error(state.value)


def run_git_bytes(
    repository: RepositoryPath,
    *arguments: str,
    input_bytes: bytes | None = None,
    accepted_returncodes: tuple[int, ...] = (0,),
) -> bytes:
    """Run one canonical Git query in the repository root."""
    return _run_git_bytes(
        *arguments,
        cwd=repository.value,
        input_bytes=input_bytes,
        accepted_returncodes=accepted_returncodes,
    )


def read_head_object_id(repository: RepositoryPath) -> GitObjectId:
    """Read and validate the full SHA-1 or SHA-256 object name of HEAD."""
    raw = run_git_bytes(repository, "rev-parse", "HEAD")
    lines = raw.splitlines()
    if len(lines) != 1:
        raise _error("git returned an invalid HEAD object name")
    try:
        value = lines[0].decode("ascii", errors="strict")
    except UnicodeDecodeError as exc:
        raise _error("git returned a non-ASCII HEAD object name") from exc

    try:
        object_format = GitObjectFormat.for_hex_length(len(value))
        return GitObjectId(value=value, object_format=object_format)
    except ValueError as exc:
        raise _error("git returned an invalid HEAD object name") from exc


_REGULAR_FILE_MODE = b"100644"
_EXECUTABLE_FILE_MODE = b"100755"
_MISSING_FILE_MODE = b"000000"
_SUPPORTED_FILE_MODES = frozenset((_REGULAR_FILE_MODE, _EXECUTABLE_FILE_MODE))


@dataclass(frozen=True)
class _BaseTreeEntry:
    path: bytes
    mode: bytes
    object_name: bytes


@dataclass(frozen=True)
class _IndexEntry:
    path: bytes
    mode: bytes
    object_name: bytes


def _validated_object_name(
    raw: bytes,
    object_format: GitObjectFormat,
    description: str,
) -> bytes:
    if len(raw) != object_format.object_id_hex_length or any(
        byte not in b"0123456789abcdef" for byte in raw
    ):
        raise _error(f"git returned an invalid {description} object name")
    return raw


def _validated_file_mode(raw: bytes) -> bytes:
    if raw not in _SUPPORTED_FILE_MODES:
        raise _unsupported(_UnsupportedState.ENTRY_TYPE)
    return raw


def _canonical_regular_file_mode(
    metadata: os.stat_result,
    *,
    core_file_mode: bool,
) -> bytes:
    if core_file_mode and metadata.st_mode & 0o111:
        return _EXECUTABLE_FILE_MODE
    return _REGULAR_FILE_MODE


def _next_sorted_path(
    previous: bytes | None,
    path: bytes,
    description: str,
) -> bytes:
    if not path or (previous is not None and path <= previous):
        raise _error(f"git returned ambiguous {description} paths")
    return path


def _parse_base_tree(
    raw: bytes,
    object_format: GitObjectFormat,
) -> tuple[_BaseTreeEntry, ...]:
    entries: list[_BaseTreeEntry] = []
    previous_path: bytes | None = None
    for raw_record in _nul_records(raw, "base tree"):
        try:
            metadata, path = raw_record.split(b"\t", 1)
            mode, object_type, object_name = metadata.split(b" ", 2)
        except ValueError as exc:
            raise _error("git returned malformed base tree data") from exc
        validated_mode = _validated_file_mode(mode)
        if object_type != b"blob":
            raise _unsupported(_UnsupportedState.ENTRY_TYPE)
        previous_path = _next_sorted_path(previous_path, path, "base tree")
        entries.append(
            _BaseTreeEntry(
                path=path,
                mode=validated_mode,
                object_name=_validated_object_name(
                    object_name,
                    object_format,
                    "base tree",
                ),
            )
        )
    return tuple(entries)


def _parse_index(
    raw: bytes,
    object_format: GitObjectFormat,
) -> tuple[_IndexEntry, ...]:
    entries: list[_IndexEntry] = []
    previous_path: bytes | None = None
    for raw_record in _nul_records(raw, "index"):
        try:
            metadata, path = raw_record.split(b"\t", 1)
            mode, object_name, stage = metadata.split(b" ", 2)
        except ValueError as exc:
            raise _error("git returned malformed index data") from exc
        if stage != b"0":
            raise _unsupported(_UnsupportedState.INDEX)
        previous_path = _next_sorted_path(previous_path, path, "index")
        entries.append(
            _IndexEntry(
                path=path,
                mode=_validated_file_mode(mode),
                object_name=_validated_object_name(
                    object_name,
                    object_format,
                    "index",
                ),
            )
        )
    return tuple(entries)


def _require_index_blobs(
    repository: RepositoryPath,
    entries: tuple[_IndexEntry, ...],
) -> None:
    object_names = tuple(
        dict.fromkeys(entry.object_name for entry in entries)
    )
    if not object_names:
        return
    response = run_git_bytes(
        repository,
        "cat-file",
        "--batch-check=%(objectname) %(objecttype)",
        input_bytes=b"".join(name + b"\n" for name in object_names),
    )
    lines = response.splitlines()
    if len(lines) != len(object_names):
        raise _error("git returned malformed index object data")
    for expected_name, line in zip(object_names, lines, strict=True):
        try:
            observed_name, object_type = line.split(b" ", 1)
        except ValueError as exc:
            raise _error("git returned malformed index object data") from exc
        if observed_name != expected_name or object_type != b"blob":
            raise _unsupported(_UnsupportedState.ENTRY_TYPE)


def _staged_record(
    path: bytes,
    head: _BaseTreeEntry | None,
    index: _IndexEntry | None,
) -> StagedRecord:
    return StagedRecord(
        path=path,
        head_mode=head.mode if head is not None else b"",
        head_object=head.object_name if head is not None else b"",
        index_mode=index.mode if index is not None else b"",
        index_object=index.object_name if index is not None else b"",
    )


def _compare_staged_entries(
    base_entries: tuple[_BaseTreeEntry, ...],
    index_entries: tuple[_IndexEntry, ...],
) -> tuple[StagedRecord, ...]:
    records: list[StagedRecord] = []
    base_iterator = iter(base_entries)
    index_iterator = iter(index_entries)
    head = next(base_iterator, None)
    index = next(index_iterator, None)

    while head is not None or index is not None:
        if index is None or (head is not None and head.path < index.path):
            records.append(_staged_record(head.path, head, None))
            head = next(base_iterator, None)
            continue
        if head is None or index.path < head.path:
            records.append(_staged_record(index.path, None, index))
            index = next(index_iterator, None)
            continue

        if (head.mode, head.object_name) != (index.mode, index.object_name):
            records.append(_staged_record(head.path, head, index))
        head = next(base_iterator, None)
        index = next(index_iterator, None)

    return tuple(records)


def read_staged_records(
    repository: RepositoryPath,
    base_commit: GitObjectId,
) -> tuple[StagedRecord, ...]:
    """Return canonical base-tree versus index differences in byte order."""
    base_entries = _parse_base_tree(
        run_git_bytes(
            repository,
            "ls-tree",
            "-r",
            "-z",
            "--full-tree",
            str(base_commit),
        ),
        base_commit.object_format,
    )
    index_entries = _parse_index(
        run_git_bytes(repository, "ls-files", "--stage", "-z"),
        base_commit.object_format,
    )
    _require_index_blobs(repository, index_entries)
    return _compare_staged_entries(base_entries, index_entries)


_RAW_UNSTAGED_DIFF_ARGUMENTS = (
    "diff-files",
    "--raw",
    "-z",
    "--no-renames",
    "--no-ext-diff",
    "--no-textconv",
    "--",
)


@dataclass(frozen=True)
class _UnstagedEntry:
    path: bytes
    status: bytes
    index_mode: bytes
    index_object: bytes


def _parse_unstaged_diff(
    raw: bytes,
    object_format: GitObjectFormat,
) -> tuple[_UnstagedEntry, ...]:
    parts = _nul_records(raw, "unstaged diff")
    if len(parts) % 2:
        raise _error("git returned malformed unstaged diff data")

    entries: list[_UnstagedEntry] = []
    seen_paths: set[bytes] = set()
    iterator = iter(parts)
    for metadata, path in zip(iterator, iterator, strict=True):
        if not metadata.startswith(b":") or not path or path in seen_paths:
            raise _error("git returned malformed unstaged diff data")
        seen_paths.add(path)
        try:
            (
                index_mode,
                reported_worktree_mode,
                index_object,
                worktree_object,
                status_byte,
            ) = metadata[1:].split(b" ")
        except ValueError as exc:
            raise _error("git returned malformed unstaged diff data") from exc

        if status_byte not in (b"M", b"D"):
            raise _unsupported(_UnsupportedState.INDEX)
        _validated_file_mode(index_mode)
        _validated_object_name(
            index_object,
            object_format,
            "unstaged index",
        )
        zero_object = b"0" * object_format.object_id_hex_length
        if worktree_object != zero_object:
            raise _error("git returned an invalid unstaged worktree object")
        if status_byte == b"D":
            if reported_worktree_mode != _MISSING_FILE_MODE:
                raise _error("git returned an invalid deleted worktree mode")
        else:
            _validated_file_mode(reported_worktree_mode)

        entries.append(
            _UnstagedEntry(
                path=path,
                status=status_byte,
                index_mode=index_mode,
                index_object=index_object,
            )
        )

    return tuple(sorted(entries, key=lambda entry: entry.path))


def _boolean_config(repository: RepositoryPath, name: str) -> bool:
    return read_boolean_config(repository.value, name, missing=False)


def _core_file_mode(repository: RepositoryPath) -> bool:
    return _boolean_config(repository, "core.fileMode")


def _require_supported_index_flags(repository: RepositoryPath) -> None:
    raw = run_git_bytes(repository, "ls-files", "-v", "-z")
    for record in _nul_records(raw, "index flags"):
        if len(record) < 3 or record[1:2] != b" " or not record[2:]:
            raise _error("git returned malformed index flag data")
        tag = record[0]
        if tag == ord("S"):
            raise _unsupported(_UnsupportedState.INDEX)
        if ord("a") <= tag <= ord("z"):
            raise _unsupported(_UnsupportedState.INDEX)


def _ignored_directory_prefixes(
    repository: RepositoryPath,
) -> tuple[bytes, ...]:
    records = _nul_records(
        run_git_bytes(
            repository,
            "ls-files",
            "--others",
            "--ignored",
            "--exclude-standard",
            "--directory",
            "-z",
            "--",
        ),
        "ignored directories",
    )
    return tuple(record for record in records if record.endswith(b"/"))


def _relative_path_bytes(
    repository: RepositoryPath,
    target: os.PathLike[str],
) -> bytes:
    try:
        relative = os.path.relpath(target, repository.value)
    except (OSError, ValueError) as exc:
        raise _error("cannot inspect a working-tree path") from exc
    return os.fsencode(relative.replace(os.sep, "/"))


def _is_ignored_directory(
    path: bytes,
    ignored_prefixes: tuple[bytes, ...],
) -> bool:
    candidate = path + b"/"
    return any(candidate.startswith(prefix) for prefix in ignored_prefixes)


def _special_worktree_paths(
    repository: RepositoryPath,
) -> tuple[bytes, ...]:
    ignored_prefixes = _ignored_directory_prefixes(repository)
    special_paths: list[bytes] = []
    root = repository.value

    def fail_walk(exc: OSError) -> None:
        raise _error("cannot inspect the working tree") from exc

    for current, directories, files in os.walk(
        root,
        topdown=True,
        onerror=fail_walk,
        followlinks=False,
    ):
        current_path = os.fspath(current)
        retained_directories: list[str] = []
        for name in directories:
            target = os.path.join(current_path, name)
            relative = _relative_path_bytes(repository, target)
            if (
                current_path == os.fspath(root)
                and name in (".git", ".patchharbor")
            ):
                continue
            if _is_ignored_directory(relative, ignored_prefixes):
                continue
            try:
                metadata = os.lstat(target)
            except OSError as exc:
                raise _error("cannot inspect a working-tree path") from exc
            is_junction = bool(
                getattr(os.path, "isjunction", lambda _path: False)(target)
            )
            if is_junction or not stat.S_ISDIR(metadata.st_mode):
                if not stat.S_ISREG(metadata.st_mode):
                    special_paths.append(relative)
                continue
            retained_directories.append(name)
        directories[:] = retained_directories

        for name in files:
            if (
                current_path == os.fspath(root)
                and name in (".git", ".patchharbor")
            ):
                continue
            target = os.path.join(current_path, name)
            relative = _relative_path_bytes(repository, target)
            try:
                metadata = os.lstat(target)
            except OSError as exc:
                raise _error("cannot inspect a working-tree path") from exc
            if not stat.S_ISREG(metadata.st_mode):
                special_paths.append(relative)

    return tuple(sorted(set(special_paths)))


def _require_no_special_worktree_entries(repository: RepositoryPath) -> None:
    special_paths = _special_worktree_paths(repository)
    if not special_paths:
        return
    ignored = set(
        _nul_records(
            run_git_bytes(
                repository,
                "check-ignore",
                "-z",
                "--stdin",
                input_bytes=b"".join(path + b"\0" for path in special_paths),
                accepted_returncodes=(0, 1),
            ),
            "ignored special paths",
        )
    )
    candidates = set(special_paths)
    if not ignored.issubset(candidates):
        raise _error("git returned unexpected ignored path data")
    if candidates - ignored:
        raise _unsupported(_UnsupportedState.ENTRY_TYPE)


def require_supported_repository_state(
    repository: RepositoryPath,
    object_format: GitObjectFormat,
) -> None:
    """Reject Git states the safe repository path cannot describe."""
    if run_git_bytes(repository, "ls-files", "--unmerged", "-z"):
        raise _unsupported(_UnsupportedState.INDEX)

    _require_supported_index_flags(repository)
    if _boolean_config(repository, "core.sparseCheckout"):
        raise _unsupported(_UnsupportedState.SPARSE)
    if _boolean_config(repository, "index.sparse"):
        raise _unsupported(_UnsupportedState.SPARSE)

    _require_no_special_worktree_entries(repository)
    _parse_unstaged_diff(
        run_git_bytes(
            repository,
            *_RAW_UNSTAGED_DIFF_ARGUMENTS,
        ),
        object_format,
    )


@dataclass(frozen=True)
class _RegularFileSnapshot:
    mode: bytes
    content: bytes


def _metadata_signature(metadata: os.stat_result) -> tuple[int, ...]:
    return (
        metadata.st_dev,
        metadata.st_ino,
        stat.S_IFMT(metadata.st_mode),
        stat.S_IMODE(metadata.st_mode),
        metadata.st_size,
        metadata.st_mtime_ns,
        metadata.st_ctime_ns,
    )


def _same_file_state(
    first: os.stat_result,
    second: os.stat_result,
) -> bool:
    return os.path.samestat(first, second) and (
        _metadata_signature(first) == _metadata_signature(second)
    )


def _inspect_worktree_path(target: os.PathLike[str]) -> os.stat_result | None:
    try:
        return os.lstat(target)
    except FileNotFoundError:
        return None
    except OSError as exc:
        raise _error("cannot inspect a working-tree path") from exc


def _require_regular_file(metadata: os.stat_result) -> None:
    if not stat.S_ISREG(metadata.st_mode):
        raise _unsupported(_UnsupportedState.ENTRY_TYPE)


def _read_regular_file(
    target: os.PathLike[str],
    *,
    core_file_mode: bool,
) -> _RegularFileSnapshot:
    initial_metadata = _inspect_worktree_path(target)
    if initial_metadata is None:
        raise _error("working-tree path disappeared while being read")
    _require_regular_file(initial_metadata)

    flags = os.O_RDONLY
    flags |= getattr(os, "O_BINARY", 0)
    flags |= getattr(os, "O_CLOEXEC", 0)
    flags |= getattr(os, "O_NOFOLLOW", 0)

    descriptor: int | None = None
    try:
        descriptor = os.open(target, flags)
        opened_metadata = os.fstat(descriptor)
        _require_regular_file(opened_metadata)
        if not _same_file_state(initial_metadata, opened_metadata):
            raise _error("working-tree file changed while being read")

        current_metadata = _inspect_worktree_path(target)
        if current_metadata is None:
            raise _error("working-tree file changed while being read")
        _require_regular_file(current_metadata)
        if not _same_file_state(opened_metadata, current_metadata):
            raise _error("working-tree file changed while being read")

        with os.fdopen(descriptor, "rb", closefd=True) as handle:
            descriptor = None
            content = handle.read()
            finished_metadata = os.fstat(handle.fileno())
    except PatchHarborError:
        raise
    except OSError as exc:
        raise _error("cannot read a working-tree file") from exc
    finally:
        if descriptor is not None:
            try:
                os.close(descriptor)
            except OSError:
                pass

    final_metadata = _inspect_worktree_path(target)
    if final_metadata is None:
        raise _error("working-tree file changed while being read")
    _require_regular_file(final_metadata)
    if (
        not _same_file_state(opened_metadata, finished_metadata)
        or not _same_file_state(finished_metadata, final_metadata)
        or len(content) != finished_metadata.st_size
    ):
        raise _error("working-tree file changed while being read")

    return _RegularFileSnapshot(
        mode=_canonical_regular_file_mode(
            finished_metadata,
            core_file_mode=core_file_mode,
        ),
        content=content,
    )


def _read_worktree_record(
    repository: RepositoryPath,
    entry: _UnstagedEntry,
    *,
    core_file_mode: bool,
) -> UnstagedRecord:
    target = repository.value / os.fsdecode(entry.path)

    if entry.status == b"D":
        existing = _inspect_worktree_path(target)
        if existing is not None:
            _require_regular_file(existing)
            raise _error("deleted working-tree path still exists")
        return UnstagedRecord(
            path=entry.path,
            status=entry.status,
            index_mode=entry.index_mode,
            index_object=entry.index_object,
            worktree_kind=b"missing",
            worktree_mode=b"",
            worktree_content=b"",
        )
    if entry.status != b"M":
        raise _error("git returned an unsupported unstaged status")

    snapshot = _read_regular_file(
        target,
        core_file_mode=core_file_mode,
    )
    return UnstagedRecord(
        path=entry.path,
        status=entry.status,
        index_mode=entry.index_mode,
        index_object=entry.index_object,
        worktree_kind=b"regular",
        worktree_mode=snapshot.mode,
        worktree_content=snapshot.content,
    )


def read_unstaged_records(
    repository: RepositoryPath,
    object_format: GitObjectFormat,
) -> tuple[UnstagedRecord, ...]:
    """Return canonical index versus working-tree differences."""
    entries = _parse_unstaged_diff(
        run_git_bytes(
            repository,
            *_RAW_UNSTAGED_DIFF_ARGUMENTS,
        ),
        object_format,
    )
    core_file_mode = _core_file_mode(repository)
    return tuple(
        _read_worktree_record(
            repository,
            entry,
            core_file_mode=core_file_mode,
        )
        for entry in entries
    )


@dataclass(frozen=True)
class _UntrackedPath:
    original_bytes: bytes
    comparison_parts: tuple[str, ...]


def _untracked_path(raw: bytes) -> _UntrackedPath:
    try:
        decoded = raw.decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise _error("git returned a non-UTF-8 untracked path") from exc

    parts = tuple(decoded.split("/"))
    if not parts or any(part in ("", ".", "..") for part in parts):
        raise _error("git returned an invalid untracked path")
    return _UntrackedPath(
        original_bytes=raw,
        comparison_parts=parts,
    )


def _parse_untracked_paths(raw: bytes) -> tuple[_UntrackedPath, ...]:
    raw_paths = _nul_records(raw, "untracked paths")
    if (
        any(not path for path in raw_paths)
        or len(set(raw_paths)) != len(raw_paths)
    ):
        raise _error("git returned ambiguous untracked paths")
    return tuple(
        _untracked_path(path)
        for path in sorted(raw_paths)
    )


def read_untracked_records(
    repository: RepositoryPath,
) -> tuple[UntrackedRecord, ...]:
    """Return canonical non-ignored untracked files in byte order."""
    paths = _parse_untracked_paths(
        run_git_bytes(
            repository,
            "ls-files",
            "--others",
            "--exclude-standard",
            "-z",
            "--",
        )
    )
    if not paths:
        return ()

    core_file_mode = _core_file_mode(repository)
    records: list[UntrackedRecord] = []
    for path in paths:
        snapshot = _read_regular_file(
            repository.value.joinpath(*path.comparison_parts),
            core_file_mode=core_file_mode,
        )
        records.append(
            UntrackedRecord(
                path=path.original_bytes,
                mode=snapshot.mode,
                content=snapshot.content,
            )
        )
    return tuple(records)
