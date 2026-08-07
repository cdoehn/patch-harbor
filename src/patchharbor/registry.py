"""Locked and atomic persistence of the central repository registry."""

from __future__ import annotations

from collections.abc import Mapping
from contextlib import contextmanager
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


def _error(message: str) -> PatchHarborError:
    return registry_error(message)


def registry_snapshot(
    repositories: Mapping[RepositoryId, RepositoryPath],
) -> RegistrySnapshot:
    """Freeze one mapping set in canonical repository-ID order."""
    return RegistrySnapshot(
        repositories=tuple(
            RegistryMapping(repo_id=repo_id, repository_path=repository_path)
            for repo_id, repository_path in sorted(
                repositories.items(),
                key=lambda item: str(item[0]).encode("ascii"),
            )
        )
    )


def _registry_entries(snapshot: RegistrySnapshot) -> RegistryEntries:
    return {
        mapping.repo_id: mapping.repository_path
        for mapping in snapshot.repositories
    }


def set_registry_mapping(
    snapshot: RegistrySnapshot,
    repo_id: RepositoryId,
    repository_path: RepositoryPath,
) -> RegistrySnapshot:
    """Return a canonical snapshot containing the supplied mapping."""
    repositories = _registry_entries(snapshot)
    repositories[repo_id] = repository_path
    return registry_snapshot(repositories)


def remove_registry_mapping(
    snapshot: RegistrySnapshot,
    repo_id: RepositoryId,
) -> RegistrySnapshot:
    """Return a canonical snapshot without the supplied repository ID."""
    repositories = _registry_entries(snapshot)
    repositories.pop(repo_id, None)
    return registry_snapshot(repositories)


def remove_registry_path_mappings(
    snapshot: RegistrySnapshot,
    repository_path: RepositoryPath,
) -> RegistrySnapshot:
    """Return a snapshot without mappings for one exact canonical path."""
    return registry_snapshot(
        {
            repo_id: mapped_path
            for repo_id, mapped_path in _registry_entries(snapshot).items()
            if mapped_path != repository_path
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


def load_registry(paths: RegistrationUserPaths) -> RegistrySnapshot:
    """Read and validate one complete central registry snapshot."""
    path = paths.registry_path
    if _registry_file_kind(path) is PathKind.MISSING:
        return registry_snapshot({})

    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise _error(f"cannot read repository registry: {exc}") from exc
    if (
        not isinstance(document, dict)
        or document.get("format_version") != 1
        or not isinstance(document.get("repositories"), dict)
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


def write_registry(
    paths: RegistrationUserPaths,
    snapshot: RegistrySnapshot,
) -> None:
    """Publish one complete immutable snapshot through atomic replacement."""
    document = {
        "format_version": 1,
        "repositories": {
            str(mapping.repo_id): str(mapping.repository_path)
            for mapping in snapshot.repositories
        },
    }
    encoded = (
        json.dumps(document, ensure_ascii=False, indent=2, sort_keys=True)
        + "\n"
    ).encode("utf-8")
    _registry_file_kind(paths.registry_path)
    try:
        atomic_replace_bytes(paths.registry_path, encoded)
    except FileSystemOperationError as exc:
        raise _error(f"cannot update repository registry: {exc.cause}") from exc
