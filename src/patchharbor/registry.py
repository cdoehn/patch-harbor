"""Locked and atomic persistence of the central repository registry."""

from __future__ import annotations

from collections.abc import Mapping
from contextlib import contextmanager
from dataclasses import dataclass
import json
import os
from pathlib import Path
from typing import Iterator

from patchharbor.errors import PatchHarborError, registry_error
from patchharbor.models import (
    RegistryMapping,
    RegistrySnapshot,
    RepositoryId,
    RepositoryPath,
)
from patchharbor.platform.filesystem import (
    FileSystemOperationError,
    PathKind,
    atomic_replace_bytes,
    path_kind,
)
from patchharbor.user_paths import RegistrationUserPaths


RegistryEntries = dict[RepositoryId, RepositoryPath]


@dataclass(frozen=True)
class RegistryFileState:
    """Validated snapshot plus exact bytes present before a mutation."""

    snapshot: RegistrySnapshot
    content: bytes | None


def _error(message: str) -> PatchHarborError:
    return registry_error(message)


def _canonical_repository_id(value: object) -> RepositoryId:
    if not isinstance(value, RepositoryId):
        raise _error("repository registry entry has a non-canonical ID")
    try:
        canonical = RepositoryId(str(value))
    except ValueError as exc:
        raise _error("repository registry entry has a non-canonical ID") from exc
    if canonical != value:
        raise _error("repository registry entry has a non-canonical ID")
    return canonical


def _canonical_repository_path(value: object) -> RepositoryPath:
    if not isinstance(value, RepositoryPath):
        raise _error("repository registry entry has an invalid path")
    try:
        canonical = RepositoryPath(Path(str(value)))
    except ValueError as exc:
        raise _error("repository registry entry has an invalid path") from exc
    if canonical != value:
        raise _error("repository registry entry has an invalid path")
    return canonical


def registry_snapshot(
    repositories: Mapping[RepositoryId, RepositoryPath],
) -> RegistrySnapshot:
    """Freeze one mapping set in canonical repository-ID order."""
    canonical_entries: RegistryEntries = {}
    for raw_id, raw_path in repositories.items():
        repo_id = _canonical_repository_id(raw_id)
        repository_path = _canonical_repository_path(raw_path)
        canonical_entries[repo_id] = repository_path
    return RegistrySnapshot(
        repositories=tuple(
            RegistryMapping(repo_id=repo_id, repository_path=repository_path)
            for repo_id, repository_path in sorted(
                canonical_entries.items(),
                key=lambda item: str(item[0]).encode("ascii"),
            )
        )
    )


def _registry_entries(snapshot: RegistrySnapshot) -> RegistryEntries:
    entries: RegistryEntries = {}
    for mapping in snapshot.repositories:
        if not isinstance(mapping, RegistryMapping):
            raise _error("repository registry snapshot is invalid")
        repo_id = _canonical_repository_id(mapping.repo_id)
        repository_path = _canonical_repository_path(mapping.repository_path)
        if repo_id in entries:
            raise _error("repository registry contains a duplicate ID")
        entries[repo_id] = repository_path
    return entries


def set_registry_mapping(
    snapshot: RegistrySnapshot,
    repo_id: RepositoryId,
    repository_path: RepositoryPath,
) -> RegistrySnapshot:
    """Return a canonical snapshot containing the supplied mapping."""
    repositories = _registry_entries(snapshot)
    repositories[_canonical_repository_id(repo_id)] = _canonical_repository_path(
        repository_path
    )
    return registry_snapshot(repositories)


def remove_registry_mapping(
    snapshot: RegistrySnapshot,
    repo_id: RepositoryId,
) -> RegistrySnapshot:
    """Return a canonical snapshot without the supplied repository ID."""
    repositories = _registry_entries(snapshot)
    repositories.pop(_canonical_repository_id(repo_id), None)
    return registry_snapshot(repositories)


def remove_registry_path_mappings(
    snapshot: RegistrySnapshot,
    repository_path: RepositoryPath,
) -> RegistrySnapshot:
    """Return a snapshot without mappings for one exact canonical path."""
    selected_path = _canonical_repository_path(repository_path)
    return registry_snapshot(
        {
            repo_id: mapped_path
            for repo_id, mapped_path in _registry_entries(snapshot).items()
            if mapped_path != selected_path
        }
    )


@contextmanager
def registry_lock(paths: RegistrationUserPaths) -> Iterator[None]:
    """Hold the single global registry mutation lock."""
    lock_path = paths.registry_lock_path
    descriptor = -1
    acquired = False
    try:
        try:
            descriptor = os.open(
                lock_path,
                os.O_CREAT | os.O_EXCL | os.O_WRONLY,
                0o600,
            )
            acquired = True
            os.write(descriptor, f"{os.getpid()}\n".encode("ascii"))
            os.close(descriptor)
            descriptor = -1
        except FileExistsError as exc:
            raise _error("repository registry is busy") from exc
        except OSError as exc:
            raise _error(
                f"cannot acquire repository registry lock: {exc}"
            ) from exc

        yield
    finally:
        if descriptor >= 0:
            os.close(descriptor)
        if acquired:
            try:
                lock_path.unlink(missing_ok=True)
            except OSError:
                pass


def _registry_file_kind(path: Path) -> PathKind:
    try:
        kind = path_kind(path)
    except FileSystemOperationError as exc:
        raise _error(f"cannot inspect repository registry: {exc.cause}") from exc
    if kind not in {PathKind.MISSING, PathKind.REGULAR_FILE}:
        raise _error("repository registry must be a regular file")
    return kind


class _DuplicateJsonKey(ValueError):
    pass


def _reject_duplicate_keys(
    pairs: list[tuple[str, object]],
) -> dict[str, object]:
    document: dict[str, object] = {}
    for key, value in pairs:
        if key in document:
            raise _DuplicateJsonKey(key)
        document[key] = value
    return document


def _parse_registry(content: bytes) -> RegistrySnapshot:
    try:
        text = content.decode("utf-8", errors="strict")
        document = json.loads(text, object_pairs_hook=_reject_duplicate_keys)
    except (UnicodeError, json.JSONDecodeError, _DuplicateJsonKey) as exc:
        raise _error(f"cannot read repository registry: {exc}") from exc
    if (
        not isinstance(document, dict)
        or document.get("format_version") != 1
        or not isinstance(document.get("repositories"), dict)
        or set(document) != {"format_version", "repositories"}
    ):
        raise _error("repository registry has an invalid structure")

    entries: RegistryEntries = {}
    for raw_id, raw_path in document["repositories"].items():
        if not isinstance(raw_id, str) or not isinstance(raw_path, str):
            raise _error("repository registry entry is invalid")
        try:
            repo_id = RepositoryId(raw_id)
            repository_path = RepositoryPath(Path(raw_path))
        except ValueError as exc:
            raise _error(f"repository registry entry is invalid: {exc}") from exc
        entries[repo_id] = repository_path
    return registry_snapshot(entries)


def load_registry_state(paths: RegistrationUserPaths) -> RegistryFileState:
    """Read one validated registry snapshot and retain its exact prior bytes."""
    path = paths.registry_path
    if _registry_file_kind(path) is PathKind.MISSING:
        return RegistryFileState(snapshot=registry_snapshot({}), content=None)
    try:
        content = path.read_bytes()
    except OSError as exc:
        raise _error(f"cannot read repository registry: {exc}") from exc
    return RegistryFileState(snapshot=_parse_registry(content), content=content)


def load_registry(paths: RegistrationUserPaths) -> RegistrySnapshot:
    """Read and validate one complete central registry snapshot."""
    return load_registry_state(paths).snapshot


def _encoded_registry(snapshot: RegistrySnapshot) -> bytes:
    canonical = registry_snapshot(_registry_entries(snapshot))
    document = {
        "format_version": 1,
        "repositories": {
            str(mapping.repo_id): str(mapping.repository_path)
            for mapping in canonical.repositories
        },
    }
    return (
        json.dumps(document, ensure_ascii=False, indent=2, sort_keys=True)
        + "\n"
    ).encode("utf-8")


def write_registry(
    paths: RegistrationUserPaths,
    snapshot: RegistrySnapshot,
) -> None:
    """Publish one complete immutable snapshot through atomic replacement."""
    encoded = _encoded_registry(snapshot)
    _registry_file_kind(paths.registry_path)
    try:
        atomic_replace_bytes(paths.registry_path, encoded)
    except FileSystemOperationError as exc:
        raise _error(f"cannot update repository registry: {exc.cause}") from exc


def restore_registry_state(
    paths: RegistrationUserPaths,
    state: RegistryFileState,
) -> None:
    """Restore the exact registry bytes or absence captured before mutation."""
    kind = _registry_file_kind(paths.registry_path)
    if state.content is None:
        if kind is PathKind.REGULAR_FILE:
            try:
                paths.registry_path.unlink()
            except OSError as exc:
                raise _error(f"cannot restore repository registry: {exc}") from exc
        return
    try:
        atomic_replace_bytes(paths.registry_path, state.content)
    except FileSystemOperationError as exc:
        raise _error(f"cannot restore repository registry: {exc.cause}") from exc
