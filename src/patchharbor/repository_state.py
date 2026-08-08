"""Capture the reproducible state of one registered Git repository."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
import subprocess

from patchharbor.errors import PatchHarborError, repository_resolution_error
from patchharbor.locks import registry_lock, repository_lock
from patchharbor.models import (
    RegistrySnapshot,
    RepositoryContext,
    RepositoryId,
    RepositoryPath,
)
from patchharbor.registry import load_registry
from patchharbor.repository import inspect_local_registration, inspect_repository
from patchharbor.user_paths import RegistrationUserPaths, registration_user_paths


FINGERPRINT_ALGORITHM = "patchharbor-state-v1"
_FINGERPRINT_HEADER = b"PATCHHARBOR_STATE_FINGERPRINT\0" + b"1\0"


def _error(message: str) -> PatchHarborError:
    return repository_resolution_error(message)


def _run_git(repository: RepositoryPath, *arguments: str) -> bytes:
    environment = os.environ.copy()
    environment.update(
        {
            "GIT_OPTIONAL_LOCKS": "0",
            "GIT_PAGER": "cat",
            "GIT_TERMINAL_PROMPT": "0",
            "LANG": "C",
            "LC_ALL": "C",
        }
    )
    try:
        completed = subprocess.run(
            ["git", "-c", "color.ui=false", *arguments],
            cwd=repository.value,
            env=environment,
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


def _framed_field(name: bytes, payload: bytes) -> bytes:
    return name + b"\0" + len(payload).to_bytes(8, "big") + payload


def _empty_state_stream() -> bytes:
    zero_count = (0).to_bytes(8, "big")
    return b"".join(
        (
            _FINGERPRINT_HEADER,
            _framed_field(b"staged-count", zero_count),
            _framed_field(b"unstaged-count", zero_count),
            _framed_field(b"untracked-count", zero_count),
        )
    )


def _base_commit(repository: RepositoryPath) -> str:
    raw = _run_git(repository, "rev-parse", "HEAD")
    lines = raw.splitlines()
    if len(lines) != 1:
        raise _error("git returned an invalid HEAD object name")
    try:
        value = lines[0].decode("ascii", errors="strict")
    except UnicodeDecodeError as exc:
        raise _error("git returned a non-ASCII HEAD object name") from exc
    if not value or value != value.lower() or any(
        character not in "0123456789abcdef" for character in value
    ):
        raise _error("git returned an invalid HEAD object name")
    return value


def _require_clean(repository: RepositoryPath) -> None:
    status = _run_git(
        repository,
        "status",
        "--porcelain=v1",
        "-z",
        "--untracked-files=all",
    )
    if status:
        raise _error("repository state is not clean")


def _require_clean_for_registration(repository: RepositoryPath) -> None:
    status = _run_git(
        repository,
        "status",
        "--porcelain=v1",
        "-z",
        "--untracked-files=all",
        "--",
        ".",
        ":(exclude).patchharbor",
    )
    if status:
        raise _error("repository state is not clean")


def _require_registered_mapping(
    snapshot: RegistrySnapshot,
    repo_id: RepositoryId,
    repository: RepositoryPath,
) -> None:
    id_matches = tuple(
        mapping
        for mapping in snapshot.repositories
        if mapping.repo_id == repo_id
    )
    path_matches = tuple(
        mapping
        for mapping in snapshot.repositories
        if mapping.repository_path == repository
    )
    if len(id_matches) != 1 or id_matches[0].repository_path != repository:
        raise _error("repository identity is not registered for this path")
    if len(path_matches) != 1 or path_matches[0].repo_id != repo_id:
        raise _error("repository path has conflicting registrations")


def _registered_identity(
    paths: RegistrationUserPaths,
    repository: RepositoryPath,
) -> RepositoryId:
    repo_id, _ = inspect_local_registration(repository)
    if repo_id is None:
        raise _error("repository has no local PatchHarbor identity")
    _require_registered_mapping(load_registry(paths), repo_id, repository)
    return repo_id


def empty_state_fingerprint_digest() -> str:
    """Return the normative SHA-256 digest for zero state records."""
    return hashlib.sha256(_empty_state_stream()).hexdigest()


def require_clean_repository(path: Path) -> RepositoryPath:
    """Resolve one repository and reject mutations before registration."""
    repository = inspect_repository(path)
    _require_clean_for_registration(repository)
    return repository


def _capture_clean_context(
    repository: RepositoryPath,
    repo_id: RepositoryId,
) -> RepositoryContext:
    _require_clean(repository)
    digest = empty_state_fingerprint_digest()
    return RepositoryContext(
        repo_id=repo_id,
        repository_path=repository,
        base_commit=_base_commit(repository),
        dirty=False,
        state_fingerprint=digest[:16],
        fingerprint_algorithm=FINGERPRINT_ALGORITHM,
    )


def capture_repository_context(path: Path) -> RepositoryContext:
    """Capture one clean registered repository while owning its lock."""
    paths = registration_user_paths()
    with registry_lock(paths):
        repository = inspect_repository(path)
        repo_id = _registered_identity(paths, repository)
        with repository_lock(paths, repo_id):
            locked_repository = inspect_repository(repository.value)
            if locked_repository != repository:
                raise _error("repository path changed while acquiring its lock")
            locked_id = _registered_identity(paths, locked_repository)
            if locked_id != repo_id:
                raise _error("repository identity changed while acquiring its lock")
            return _capture_clean_context(locked_repository, locked_id)
