"""Minimal registration of one local Git repository instance."""

from __future__ import annotations

from contextlib import contextmanager
import json
import os
from pathlib import Path
import subprocess
from typing import Iterator
from uuid import UUID, uuid4

from patchharbor.errors import ExitCode, PatchHarborError


_INTERNAL_DIRECTORY = ".patchharbor"
_ID_FILE = "id"
_REGISTRY_FILE = "registry.json"
_REGISTRY_LOCK = "registry.lock"
_EXCLUDE_ENTRY = ".patchharbor/"


def _error(message: str) -> PatchHarborError:
    return PatchHarborError(message, ExitCode.REPOSITORY_ERROR)


def _canonical_path(path: Path, *, must_exist: bool) -> Path:
    try:
        return path.expanduser().resolve(strict=must_exist)
    except OSError as exc:
        raise _error(f"cannot resolve path {path}: {exc}") from exc


def _user_paths() -> tuple[Path, Path]:
    if os.name == "nt":
        app_data = os.environ.get("APPDATA")
        local_app_data = os.environ.get("LOCALAPPDATA")
        if not app_data or not local_app_data:
            raise _error(
                "APPDATA and LOCALAPPDATA are required for registration"
            )
        configuration = Path(app_data) / "PatchHarbor"
        locks = Path(local_app_data) / "PatchHarbor" / "locks"
    else:
        home_value = os.environ.get("HOME")
        if not home_value:
            raise _error("HOME is required for registration")
        home = Path(home_value)
        configuration = Path(
            os.environ.get("XDG_CONFIG_HOME", str(home / ".config"))
        ) / "patchharbor"
        state = Path(
            os.environ.get(
                "XDG_STATE_HOME",
                str(home / ".local" / "state"),
            )
        ) / "patchharbor"
        locks = state / "locks"

    try:
        configuration.mkdir(parents=True, exist_ok=True)
        locks.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise _error(f"cannot create PatchHarbor user directory: {exc}") from exc
    return (
        _canonical_path(configuration, must_exist=True),
        _canonical_path(locks, must_exist=True),
    )


@contextmanager
def _registry_lock(lock_directory: Path) -> Iterator[None]:
    lock_path = lock_directory / _REGISTRY_LOCK
    try:
        descriptor = os.open(
            lock_path,
            os.O_CREAT | os.O_EXCL | os.O_WRONLY,
            0o600,
        )
    except FileExistsError as exc:
        raise _error("repository registry is busy") from exc
    except OSError as exc:
        raise _error(f"cannot acquire repository registry lock: {exc}") from exc

    try:
        os.write(descriptor, f"{os.getpid()}\n".encode("ascii"))
        os.close(descriptor)
        descriptor = -1
        yield
    finally:
        if descriptor >= 0:
            os.close(descriptor)
        try:
            lock_path.unlink(missing_ok=True)
        except OSError:
            pass


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


def _repository_root(requested_path: Path) -> Path:
    output = _run_git(
        "-C",
        str(requested_path.expanduser()),
        "rev-parse",
        "--show-toplevel",
    )
    try:
        root = output.decode("utf-8", errors="strict").strip()
    except UnicodeDecodeError as exc:
        raise _error("repository path is not valid UTF-8") from exc
    if not root:
        raise _error("git did not return a repository root")
    return _canonical_path(Path(root), must_exist=True)


def _verify_head(repository: Path) -> None:
    _run_git(
        "rev-parse",
        "--verify",
        "--quiet",
        "HEAD^{commit}",
        cwd=repository,
    )


def _tracked_paths(repository: Path, *arguments: str) -> tuple[str, ...]:
    raw = _run_git(*arguments, cwd=repository)
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


def _verify_reserved_path_is_untracked(repository: Path) -> None:
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


def _canonical_uuid(value: str) -> str:
    try:
        parsed = UUID(value)
    except ValueError as exc:
        raise _error("repository ID is not a valid UUID") from exc
    if parsed.version != 4 or str(parsed) != value:
        raise _error("repository ID is not a canonical UUID v4")
    return value


def _repository_id(repository: Path) -> str:
    internal = repository / _INTERNAL_DIRECTORY
    try:
        internal.mkdir(mode=0o700, exist_ok=True)
    except OSError as exc:
        raise _error(f"cannot create {internal}: {exc}") from exc
    if not internal.is_dir() or internal.is_symlink():
        raise _error(".patchharbor must be a real directory")

    id_path = internal / _ID_FILE
    if id_path.exists():
        if not id_path.is_file() or id_path.is_symlink():
            raise _error(".patchharbor/id must be a regular file")
        try:
            content = id_path.read_text(encoding="ascii")
        except (OSError, UnicodeError) as exc:
            raise _error(f"cannot read repository ID: {exc}") from exc
        if not content.endswith("\n") or content.count("\n") != 1:
            raise _error("repository ID file has invalid content")
        return _canonical_uuid(content[:-1])

    repo_id = str(uuid4())
    try:
        id_path.write_text(f"{repo_id}\n", encoding="ascii", newline="\n")
    except OSError as exc:
        raise _error(f"cannot write repository ID: {exc}") from exc
    return repo_id


def _exclude_path(repository: Path) -> Path:
    output = _run_git(
        "rev-parse",
        "--git-path",
        "info/exclude",
        cwd=repository,
    )
    try:
        value = output.decode("utf-8", errors="strict").strip()
    except UnicodeDecodeError as exc:
        raise _error("Git exclude path is not valid UTF-8") from exc
    path = Path(value)
    if not path.is_absolute():
        path = repository / path
    return _canonical_path(path, must_exist=False)


def _exclude_internal_directory(repository: Path) -> None:
    exclude_path = _exclude_path(repository)
    try:
        exclude_path.parent.mkdir(parents=True, exist_ok=True)
        existing = (
            exclude_path.read_text(encoding="utf-8")
            if exclude_path.exists()
            else ""
        )
        if _EXCLUDE_ENTRY in existing.splitlines():
            return
        separator = "" if not existing or existing.endswith("\n") else "\n"
        exclude_path.write_text(
            f"{existing}{separator}{_EXCLUDE_ENTRY}\n",
            encoding="utf-8",
            newline="\n",
        )
    except (OSError, UnicodeError) as exc:
        raise _error(f"cannot update local Git exclude file: {exc}") from exc


def _load_registry(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
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
    repositories = document["repositories"]
    if not all(
        isinstance(repo_id, str) and isinstance(path_value, str)
        for repo_id, path_value in repositories.items()
    ):
        raise _error("repository registry entry is invalid")
    return dict(repositories)


def _write_registry(path: Path, repositories: dict[str, str]) -> None:
    document = {
        "format_version": 1,
        "repositories": dict(sorted(repositories.items())),
    }
    try:
        path.write_text(
            json.dumps(document, ensure_ascii=False, indent=2, sort_keys=True)
            + "\n",
            encoding="utf-8",
            newline="\n",
        )
    except OSError as exc:
        raise _error(f"cannot update repository registry: {exc}") from exc


def register_local_repository(path: Path) -> tuple[str, Path]:
    """Register one local Git repository and return ID and canonical path."""
    configuration, locks = _user_paths()
    with _registry_lock(locks):
        repository = _repository_root(path)
        _verify_head(repository)
        _verify_reserved_path_is_untracked(repository)
        _exclude_internal_directory(repository)
        repo_id = _repository_id(repository)
        registry_path = configuration / _REGISTRY_FILE
        repositories = _load_registry(registry_path)
        repositories[repo_id] = str(repository)
        _write_registry(registry_path, repositories)
    return repo_id, repository
