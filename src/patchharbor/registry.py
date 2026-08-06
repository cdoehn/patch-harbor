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


def registry_entries(snapshot: RegistrySnapshot) -> RegistryEntries:
    """Create a mutable working copy of one immutable registry snapshot."""
    return {
        mapping.repo_id: mapping.repository_path
        for mapping in snapshot.repositories
    }


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


def load_registry(paths: RegistrationUserPaths) -> RegistrySnapshot:
    """Read and validate one complete central registry snapshot."""
    path = paths.registry_path
    try:
        kind = path_kind(path)
    except FileSystemOperationError as exc:
        raise _error(f"cannot inspect repository registry: {exc.cause}") from exc
    if kind is PathKind.MISSING:
        return registry_snapshot({})
    if kind is not PathKind.REGULAR_FILE:
        raise _error("repository registry must be a regular file")

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
    try:
        kind = path_kind(paths.registry_path)
    except FileSystemOperationError as exc:
        raise _error(f"cannot inspect repository registry: {exc.cause}") from exc
    if kind not in {PathKind.MISSING, PathKind.REGULAR_FILE}:
        raise _error("repository registry must be a regular file")
    try:
        atomic_replace_bytes(paths.registry_path, encoded)
    except FileSystemOperationError as exc:
        raise _error(f"cannot update repository registry: {exc.cause}") from exc
