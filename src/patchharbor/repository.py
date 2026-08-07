"""Inspection and local identity files of one Git repository instance."""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import subprocess

from patchharbor.errors import PatchHarborError, repository_resolution_error
from patchharbor.models import (
    RegistryStatus,
    RepositoryId,
    RepositoryPath,
)
from patchharbor.physical_paths import physically_canonicalize
from patchharbor.platform.filesystem import (
    FileSystemOperationError,
    PathKind,
    atomic_replace_bytes,
    path_kind,
)


_INTERNAL_DIRECTORY = ".patchharbor"
_ID_FILE = "id"
_EXCLUDE_ENTRY = b".patchharbor/"


@dataclass(frozen=True)
class LocalRegistrationState:
    """Original local files needed to restore a failed registration."""

    internal_directory: Path
    internal_directory_existed: bool
    id_path: Path
    id_content: bytes | None
    exclude_path: Path
    exclude_content: bytes | None


def _error(message: str) -> PatchHarborError:
    return repository_resolution_error(message)


def _run_git(
    *arguments: str,
    cwd: Path | None = None,
) -> bytes:
    environment = os.environ.copy()
    environment.update(
        {
            "GIT_PAGER": "cat",
            "GIT_TERMINAL_PROMPT": "0",
            "LC_ALL": "C",
        }
    )
    try:
        completed = subprocess.run(
            ["git", *arguments],
            cwd=cwd,
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
        raise _error(f"git repository check failed{suffix}")
    return completed.stdout


def _tracked_paths(repository: RepositoryPath, *arguments: str) -> tuple[str, ...]:
    raw = _run_git(*arguments, cwd=repository.value)
    paths: list[str] = []
    for value in raw.split(b"\0"):
        if not value:
            continue
        try:
            paths.append(value.decode("utf-8", errors="strict"))
        except UnicodeDecodeError as exc:
            raise _error("tracked repository path is not valid UTF-8") from exc
    return tuple(paths)


def _has_reserved_segment(path: str) -> bool:
    return any(
        segment.casefold() == _INTERNAL_DIRECTORY
        for segment in path.split("/")
    )


def canonicalize_repository_reference(requested_path: Path) -> RepositoryPath:
    """Resolve a repository path reference even when its target is missing."""
    try:
        return RepositoryPath(
            physically_canonicalize(requested_path, must_exist=False)
        )
    except (OSError, RuntimeError, ValueError) as exc:
        raise _error(f"cannot resolve repository path: {exc}") from exc


def inspect_repository(requested_path: Path) -> RepositoryPath:
    """Resolve and verify the immutable repository boundary for registration."""
    output = _run_git(
        "-C",
        str(requested_path.expanduser()),
        "rev-parse",
        "--show-toplevel",
    )
    try:
        root_text = output.decode("utf-8", errors="strict").strip()
    except UnicodeDecodeError as exc:
        raise _error("repository path is not valid UTF-8") from exc
    if not root_text:
        raise _error("git did not return a repository root")

    try:
        root = physically_canonicalize(Path(root_text), must_exist=True)
        repository = RepositoryPath(root)
    except (OSError, RuntimeError, ValueError) as exc:
        raise _error(f"cannot resolve repository path: {exc}") from exc

    _run_git(
        "rev-parse",
        "--verify",
        "--quiet",
        "HEAD^{commit}",
        cwd=repository.value,
    )
    base_paths = _tracked_paths(
        repository,
        "ls-tree",
        "-r",
        "-z",
        "--name-only",
        "HEAD",
    )
    index_paths = _tracked_paths(
        repository,
        "ls-files",
        "-z",
        "--cached",
        "--",
    )
    if any(_has_reserved_segment(path) for path in (*base_paths, *index_paths)):
        raise _error("repository tracks the reserved .patchharbor path")
    return repository


def _require_internal_directory_state(path: Path) -> bool:
    try:
        kind = path_kind(path)
    except FileSystemOperationError as exc:
        raise _error(f"cannot inspect .patchharbor: {exc.cause}") from exc
    if kind is PathKind.MISSING:
        return False
    if kind is not PathKind.DIRECTORY:
        raise _error(
            ".patchharbor must be a real directory, not a link, junction, or file"
        )
    return True


def _read_optional_regular_file(path: Path, *, description: str) -> bytes | None:
    try:
        kind = path_kind(path)
    except FileSystemOperationError as exc:
        raise _error(f"cannot inspect {description}: {exc.cause}") from exc
    if kind is PathKind.MISSING:
        return None
    if kind is not PathKind.REGULAR_FILE:
        raise _error(f"{description} must be a regular file")
    try:
        return path.read_bytes()
    except OSError as exc:
        raise _error(f"cannot read {description}: {exc}") from exc


def registered_repository_status(
    repository: RepositoryPath,
    expected_id: RepositoryId,
) -> RegistryStatus:
    """Observe whether one central mapping still identifies its local instance."""
    try:
        root_kind = path_kind(repository.value)
    except FileSystemOperationError:
        return RegistryStatus.CONFLICT
    if root_kind is PathKind.MISSING:
        return RegistryStatus.MISSING
    if root_kind is not PathKind.DIRECTORY:
        return RegistryStatus.CONFLICT

    internal = repository.value / _INTERNAL_DIRECTORY
    id_path = internal / _ID_FILE
    try:
        if path_kind(internal) is not PathKind.DIRECTORY:
            return RegistryStatus.CONFLICT
        if path_kind(id_path) is not PathKind.REGULAR_FILE:
            return RegistryStatus.CONFLICT
        content = id_path.read_bytes()
    except (OSError, FileSystemOperationError):
        return RegistryStatus.CONFLICT

    try:
        text = content.decode("ascii")
        observed_id = RepositoryId(text[:-1])
    except (UnicodeDecodeError, ValueError):
        return RegistryStatus.CONFLICT
    if not text.endswith("\n") or text.count("\n") != 1:
        return RegistryStatus.CONFLICT
    if observed_id != expected_id:
        return RegistryStatus.CONFLICT
    return RegistryStatus.OK


def _exclude_path(repository: RepositoryPath) -> Path:
    output = _run_git(
        "rev-parse",
        "--git-path",
        "info/exclude",
        cwd=repository.value,
    )
    try:
        value = output.decode("utf-8", errors="strict").strip()
    except UnicodeDecodeError as exc:
        raise _error("Git exclude path is not valid UTF-8") from exc
    path = Path(value)
    if not path.is_absolute():
        path = repository.value / path
    try:
        return physically_canonicalize(path, must_exist=False)
    except (OSError, RuntimeError) as exc:
        raise _error(f"cannot resolve local Git exclude path: {exc}") from exc


def inspect_local_registration(
    repository: RepositoryPath,
) -> tuple[RepositoryId | None, LocalRegistrationState]:
    """Read local registration state without changing the repository."""
    internal = repository.value / _INTERNAL_DIRECTORY
    internal_existed = _require_internal_directory_state(internal)
    id_path = internal / _ID_FILE
    id_content = (
        _read_optional_regular_file(
            id_path,
            description=".patchharbor/id",
        )
        if internal_existed
        else None
    )
    exclude_path = _exclude_path(repository)
    exclude_content = _read_optional_regular_file(
        exclude_path,
        description="local Git exclude file",
    )

    repo_id: RepositoryId | None = None
    if id_content is not None:
        try:
            text = id_content.decode("ascii")
        except UnicodeDecodeError as exc:
            raise _error("repository ID file has invalid content") from exc
        if not text.endswith("\n") or text.count("\n") != 1:
            raise _error("repository ID file has invalid content")
        try:
            repo_id = RepositoryId(text[:-1])
        except ValueError as exc:
            raise _error(str(exc)) from exc

    return repo_id, LocalRegistrationState(
        internal_directory=internal,
        internal_directory_existed=internal_existed,
        id_path=id_path,
        id_content=id_content,
        exclude_path=exclude_path,
        exclude_content=exclude_content,
    )


def _atomic_write(path: Path, content: bytes, *, description: str) -> None:
    try:
        atomic_replace_bytes(path, content)
    except FileSystemOperationError as exc:
        raise _error(f"cannot update {description}: {exc.cause}") from exc


def apply_local_registration(
    state: LocalRegistrationState,
    repo_id: RepositoryId,
) -> None:
    """Atomically write the local exclude entry and repository identity."""
    try:
        canonical_id = RepositoryId(str(repo_id))
    except ValueError as exc:
        raise _error("repository ID is not a canonical UUID v4") from exc
    if canonical_id != repo_id:
        raise _error("repository ID is not a canonical UUID v4")

    if not state.internal_directory_existed:
        try:
            state.internal_directory.mkdir(mode=0o700)
        except OSError as exc:
            raise _error(f"cannot create {state.internal_directory}: {exc}") from exc
    _require_internal_directory_state(state.internal_directory)

    existing_exclude = state.exclude_content or b""
    if _EXCLUDE_ENTRY not in existing_exclude.splitlines():
        separator = (
            b""
            if not existing_exclude or existing_exclude.endswith(b"\n")
            else b"\n"
        )
        _atomic_write(
            state.exclude_path,
            existing_exclude + separator + _EXCLUDE_ENTRY + b"\n",
            description="local Git exclude file",
        )

    try:
        current_id_kind = path_kind(state.id_path)
    except FileSystemOperationError as exc:
        raise _error(f"cannot inspect .patchharbor/id: {exc.cause}") from exc
    if current_id_kind not in {PathKind.MISSING, PathKind.REGULAR_FILE}:
        raise _error(".patchharbor/id must be a regular file")
    _atomic_write(
        state.id_path,
        f"{canonical_id}\n".encode("ascii"),
        description="repository ID",
    )


def _restore_file(path: Path, content: bytes | None) -> None:
    if content is None:
        path.unlink(missing_ok=True)
    else:
        atomic_replace_bytes(path, content)


def restore_local_registration(state: LocalRegistrationState) -> None:
    """Best-effort restore of every local file changed during registration."""
    failures: list[BaseException] = []
    for path, content in (
        (state.id_path, state.id_content),
        (state.exclude_path, state.exclude_content),
    ):
        try:
            _restore_file(path, content)
        except (OSError, FileSystemOperationError) as exc:
            failures.append(exc)

    if not state.internal_directory_existed:
        try:
            state.internal_directory.rmdir()
        except FileNotFoundError:
            pass
        except OSError as exc:
            failures.append(exc)

    if failures:
        raise _error("cannot restore local registration state") from failures[0]
