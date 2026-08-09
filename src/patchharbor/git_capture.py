"""Byte-exact Git command boundary for repository-state capture."""

from __future__ import annotations

from dataclasses import dataclass
import os
import subprocess

from patchharbor.errors import PatchHarborError, repository_resolution_error
from patchharbor.models import (
    GitObjectFormat,
    GitObjectId,
    RepositoryPath,
    StagedRecord,
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


_SUPPORTED_FILE_MODES = frozenset((b"100644", b"100755"))


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
    try:
        value = raw.decode("ascii", errors="strict")
        GitObjectId(value=value, object_format=object_format)
    except (UnicodeDecodeError, ValueError) as exc:
        raise _error(f"git returned an invalid {description} object name") from exc
    return raw


def _validated_mode(raw: bytes, description: str) -> bytes:
    if raw not in _SUPPORTED_FILE_MODES:
        raise _error(f"git returned an unsupported {description} mode")
    return raw


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
                mode=_validated_mode(mode, "base tree"),
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
                mode=_validated_mode(mode, "index"),
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
