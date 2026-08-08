"""Byte-exact Git command boundary for repository-state capture."""

from __future__ import annotations

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


def run_git_bytes(repository: RepositoryPath, *arguments: str) -> bytes:
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
    try:
        completed = subprocess.run(
            command,
            cwd=repository.value,
            env=_controlled_git_environment(),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
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


def read_staged_records(
    repository: RepositoryPath,
    base_commit: GitObjectId,
) -> tuple[StagedRecord, ...]:
    """Return canonical base-tree versus index differences in byte order."""
    base_entries: dict[bytes, tuple[bytes, bytes]] = {}
    raw_tree = run_git_bytes(
        repository,
        "ls-tree",
        "-r",
        "-z",
        "--full-tree",
        str(base_commit),
    )
    for raw_record in _nul_records(raw_tree, "base tree"):
        try:
            metadata, path = raw_record.split(b"\t", 1)
            mode, _object_type, object_name = metadata.split(b" ", 2)
        except ValueError as exc:
            raise _error("git returned malformed base tree data") from exc
        if not path or path in base_entries:
            raise _error("git returned ambiguous base tree paths")
        base_entries[path] = (mode, object_name)

    index_entries: dict[bytes, tuple[bytes, bytes]] = {}
    raw_index = run_git_bytes(repository, "ls-files", "--stage", "-z")
    for raw_record in _nul_records(raw_index, "index"):
        try:
            metadata, path = raw_record.split(b"\t", 1)
            mode, object_name, stage = metadata.split(b" ", 2)
        except ValueError as exc:
            raise _error("git returned malformed index data") from exc
        if stage != b"0" or not path or path in index_entries:
            raise _error("git returned an unsupported index state")
        index_entries[path] = (mode, object_name)

    records: list[StagedRecord] = []
    for path in sorted(base_entries.keys() | index_entries.keys()):
        head_mode, head_object = base_entries.get(path, (b"", b""))
        index_mode, index_object = index_entries.get(path, (b"", b""))
        if (head_mode, head_object) == (index_mode, index_object):
            continue
        records.append(
            StagedRecord(
                path=path,
                head_mode=head_mode,
                head_object=head_object,
                index_mode=index_mode,
                index_object=index_object,
            )
        )
    return tuple(records)
