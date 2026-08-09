"""Byte-exact Git command boundary for repository-state capture."""

from __future__ import annotations

from dataclasses import dataclass
import os
import stat
import subprocess

from patchharbor.errors import PatchHarborError, repository_resolution_error
from patchharbor.models import (
    GitObjectFormat,
    GitObjectId,
    RepositoryPath,
    StagedRecord,
    UnstagedRecord,
)


_REDIRECTING_GIT_ENVIRONMENT = (
    "GIT_ALTERNATE_OBJECT_DIRECTORIES",
    "GIT_CEILING_DIRECTORIES",
    "GIT_COMMON_DIR",
    "GIT_DIR",
    "GIT_DIFF_OPTS",
    "GIT_EXTERNAL_DIFF",
    "GIT_GLOB_PATHSPECS",
    "GIT_ICASE_PATHSPECS",
    "GIT_INDEX_FILE",
    "GIT_LITERAL_PATHSPECS",
    "GIT_NAMESPACE",
    "GIT_NOGLOB_PATHSPECS",
    "GIT_OBJECT_DIRECTORY",
    "GIT_WORK_TREE",
)


def _error(message: str) -> PatchHarborError:
    return repository_resolution_error(message)


def _controlled_git_environment() -> dict[str, str]:
    environment = os.environ.copy()
    for name in _REDIRECTING_GIT_ENVIRONMENT:
        environment.pop(name, None)
    environment.pop("GIT_CONFIG_PARAMETERS", None)
    environment.pop("GIT_CONFIG_COUNT", None)
    for name in tuple(environment):
        if name.startswith(("GIT_CONFIG_KEY_", "GIT_CONFIG_VALUE_")):
            environment.pop(name, None)
    environment.update(
        {
            "GIT_OPTIONAL_LOCKS": "0",
            "GIT_PAGER": "cat",
            "GIT_TERMINAL_PROMPT": "0",
            "LANG": "C",
            "LC_ALL": "C",
        }
    )
    return environment


def run_git_bytes(
    repository: RepositoryPath,
    *arguments: str,
    input_bytes: bytes | None = None,
) -> bytes:
    """Run one non-interactive Git query and return stdout unchanged."""
    command = [
        "git",
        "--no-pager",
        "-c",
        "color.ui=false",
        "-c",
        "diff.external=",
        *arguments,
    ]
    run_options: dict[str, object] = {
        "cwd": repository.value,
        "env": _controlled_git_environment(),
        "stdout": subprocess.PIPE,
        "stderr": subprocess.PIPE,
        "check": False,
    }
    if input_bytes is None:
        run_options["stdin"] = subprocess.DEVNULL
    else:
        run_options["input"] = input_bytes

    try:
        completed = subprocess.run(command, **run_options)
    except FileNotFoundError as exc:
        raise _error("git executable is not available") from exc
    except OSError as exc:
        raise _error(f"cannot start git: {exc}") from exc

    if completed.returncode != 0:
        detail = completed.stderr.decode("utf-8", errors="replace").strip()
        suffix = f": {detail}" if detail else ""
        raise _error(f"cannot capture repository context{suffix}")
    return completed.stdout


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


def _nul_records(raw: bytes, description: str) -> tuple[bytes, ...]:
    if not raw:
        return ()
    if not raw.endswith(b"\0"):
        raise _error(f"git returned malformed {description}")
    return tuple(raw[:-1].split(b"\0"))


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


def _validated_file_mode(raw: bytes, description: str) -> bytes:
    if raw not in _SUPPORTED_FILE_MODES:
        raise _error(f"git returned an unsupported {description} mode")
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
        if object_type != b"blob":
            raise _error("git returned an unsupported base tree object type")
        previous_path = _next_sorted_path(previous_path, path, "base tree")
        entries.append(
            _BaseTreeEntry(
                path=path,
                mode=_validated_file_mode(mode, "base tree"),
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
            raise _error("git returned an unsupported index state")
        previous_path = _next_sorted_path(previous_path, path, "index")
        entries.append(
            _IndexEntry(
                path=path,
                mode=_validated_file_mode(mode, "index"),
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
            raise _error("git returned an unsupported index object type")


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
            raise _error("git returned an unsupported unstaged status")
        _validated_file_mode(index_mode, "unstaged index")
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
            _validated_file_mode(reported_worktree_mode, "worktree")

        entries.append(
            _UnstagedEntry(
                path=path,
                status=status_byte,
                index_mode=index_mode,
                index_object=index_object,
            )
        )

    return tuple(sorted(entries, key=lambda entry: entry.path))


def _core_file_mode(repository: RepositoryPath) -> bool:
    value = run_git_bytes(
        repository,
        "config",
        "--bool",
        "--null",
        "--default=false",
        "--get",
        "core.fileMode",
    )
    if value == b"true\0":
        return True
    if value == b"false\0":
        return False
    raise _error("git returned an invalid core.fileMode value")


@dataclass(frozen=True)
class _WorktreeSnapshot:
    kind: bytes
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
        raise _error("cannot inspect an unstaged working-tree path") from exc


def _require_regular_file(metadata: os.stat_result) -> None:
    if not stat.S_ISREG(metadata.st_mode):
        raise _error("unstaged working-tree entry is not a regular file")


def _read_regular_worktree_snapshot(
    target: os.PathLike[str],
    *,
    core_file_mode: bool,
) -> _WorktreeSnapshot:
    initial_metadata = _inspect_worktree_path(target)
    if initial_metadata is None:
        raise _error("modified working-tree path disappeared")
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
        raise _error("cannot read an unstaged working-tree file") from exc
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

    return _WorktreeSnapshot(
        kind=b"regular",
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
        if _inspect_worktree_path(target) is not None:
            raise _error("deleted working-tree path still exists")
        snapshot = _WorktreeSnapshot(
            kind=b"missing",
            mode=b"",
            content=b"",
        )
    elif entry.status == b"M":
        snapshot = _read_regular_worktree_snapshot(
            target,
            core_file_mode=core_file_mode,
        )
    else:
        raise _error("git returned an unsupported unstaged status")

    return UnstagedRecord(
        path=entry.path,
        status=entry.status,
        index_mode=entry.index_mode,
        index_object=entry.index_object,
        worktree_kind=snapshot.kind,
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
            "diff-files",
            "--raw",
            "-z",
            "--no-renames",
            "--no-ext-diff",
            "--",
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
