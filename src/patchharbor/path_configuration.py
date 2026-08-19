"""Persist and enforce configured repository-adjacent path boundaries."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
import os
from pathlib import Path

from patchharbor.locks import registry_lock
from patchharbor.models import RegistrySnapshot, RepositoryPath
from patchharbor.physical_paths import (
    is_physically_within,
    physical_paths_overlap,
    physically_canonicalize,
)
from patchharbor.platform.filesystem import (
    FileSystemOperationError,
    PathKind,
    atomic_replace_bytes,
    path_kind,
)
from patchharbor.registry import load_registry
from patchharbor.user_paths import RegistrationUserPaths, registration_user_paths


_FORMAT_VERSION = 1


class PathConfigurationError(RuntimeError):
    """One configured directory cannot be read, persisted, or permitted."""


@dataclass(frozen=True)
class ConfiguredPaths:
    """Physically canonical watcher and Result Bundle directories."""

    watcher_input_directories: tuple[Path, ...] = ()
    result_directories: tuple[Path, ...] = ()


@dataclass(frozen=True)
class PreparedWatcherInput:
    """One permitted physical watcher input and its persistent state file."""

    directory: Path
    state_path: Path


def _path_sort_key(path: Path) -> bytes:
    return os.fsencode(os.fspath(path))


def _sorted_unique(paths: tuple[Path, ...] | list[Path]) -> tuple[Path, ...]:
    return tuple(sorted(set(paths), key=_path_sort_key))


def _path_text(path: Path) -> str:
    return os.fspath(path)


def _decode_path_list(value: object, *, field: str) -> tuple[Path, ...]:
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise PathConfigurationError(f"{field} must be a list of paths")
    decoded: list[Path] = []
    for item in value:
        path = Path(item)
        if not path.is_absolute():
            raise PathConfigurationError(f"{field} contains a non-absolute path")
        try:
            decoded.append(
                physically_canonicalize(path, must_exist=False)
            )
        except (OSError, RuntimeError) as exc:
            raise PathConfigurationError(
                f"{field} contains an invalid path"
            ) from exc
    return _sorted_unique(decoded)


def load_configured_paths(paths: RegistrationUserPaths) -> ConfiguredPaths:
    """Load configured paths together with the canonical default result path."""
    path = paths.path_configuration_path
    try:
        default_result = physically_canonicalize(
            paths.result_directory,
            must_exist=False,
        )
        kind = path_kind(path)
    except (FileSystemOperationError, OSError, RuntimeError) as exc:
        raise PathConfigurationError("cannot inspect configured paths") from exc
    if kind is PathKind.MISSING:
        return ConfiguredPaths(result_directories=(default_result,))
    if kind is not PathKind.REGULAR_FILE:
        raise PathConfigurationError("configured path state is not a regular file")
    try:
        raw = path.read_bytes()
        document = json.loads(raw.decode("utf-8"))
    except (OSError, UnicodeDecodeError, ValueError) as exc:
        raise PathConfigurationError("cannot read configured path state") from exc
    if not isinstance(document, dict) or set(document) != {
        "format_version",
        "result_directories",
        "watcher_input_directories",
    }:
        raise PathConfigurationError("configured path state has an invalid schema")
    if document["format_version"] != _FORMAT_VERSION:
        raise PathConfigurationError("configured path state has an unsupported version")
    return ConfiguredPaths(
        watcher_input_directories=_decode_path_list(
            document["watcher_input_directories"],
            field="watcher_input_directories",
        ),
        result_directories=_sorted_unique(
            [
                default_result,
                *_decode_path_list(
                    document["result_directories"],
                    field="result_directories",
                ),
            ]
        ),
    )


def write_configured_paths(
    paths: RegistrationUserPaths,
    configured: ConfiguredPaths,
) -> None:
    """Atomically publish one complete configured-path snapshot."""
    document = {
        "format_version": _FORMAT_VERSION,
        "watcher_input_directories": [
            _path_text(path)
            for path in _sorted_unique(list(configured.watcher_input_directories))
        ],
        "result_directories": [
            _path_text(path)
            for path in _sorted_unique(list(configured.result_directories))
        ],
    }
    payload = (
        json.dumps(
            document,
            ensure_ascii=True,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    ).encode("utf-8")
    try:
        atomic_replace_bytes(paths.path_configuration_path, payload)
    except FileSystemOperationError as exc:
        raise PathConfigurationError("cannot persist configured path state") from exc



def _require_directory(path: Path, *, description: str) -> None:
    try:
        kind = path_kind(path)
    except FileSystemOperationError as exc:
        raise PathConfigurationError(f"cannot inspect {description}") from exc
    if kind is not PathKind.DIRECTORY:
        raise PathConfigurationError(f"{description} is not a directory")


def require_watcher_input_allowed(
    directory: Path,
    registry_snapshot: RegistrySnapshot,
    configured: ConfiguredPaths,
) -> None:
    """Reject one watcher input overlapping repositories or Result directories."""
    for mapping in registry_snapshot.repositories:
        if is_physically_within(
            directory,
            mapping.repository_path.value,
            candidate_must_exist=True,
            root_must_exist=False,
        ):
            raise PathConfigurationError(
                "watcher input is inside a registered repository"
            )
    for result_directory in configured.result_directories:
        if physical_paths_overlap(
            directory,
            result_directory,
            first_must_exist=True,
            second_must_exist=False,
        ):
            raise PathConfigurationError(
                "watcher input overlaps a Result Bundle directory"
            )


def require_result_directory_allowed(
    directory: Path,
    configured: ConfiguredPaths,
    *,
    directory_must_exist: bool,
) -> None:
    """Reject Result and watcher directories overlapping in either direction."""
    for watcher_directory in configured.watcher_input_directories:
        if physical_paths_overlap(
            directory,
            watcher_directory,
            first_must_exist=directory_must_exist,
            second_must_exist=False,
        ):
            raise PathConfigurationError(
                "Result Bundle directory overlaps a watcher input"
            )


def require_repository_registration_allowed(
    repository: RepositoryPath,
    configured: ConfiguredPaths,
) -> None:
    """Reject a repository that would invalidate configured path boundaries."""
    root = repository.value
    for watcher_directory in configured.watcher_input_directories:
        if is_physically_within(
            watcher_directory,
            root,
            candidate_must_exist=False,
            root_must_exist=True,
        ):
            raise PathConfigurationError(
                "repository contains a configured watcher input"
            )
    for result_directory in configured.result_directories:
        if is_physically_within(
            result_directory,
            root,
            candidate_must_exist=False,
            root_must_exist=True,
        ):
            raise PathConfigurationError(
                "repository contains a configured Result Bundle directory"
            )


def remember_result_directory(
    configured: ConfiguredPaths,
    directory: Path,
) -> ConfiguredPaths:
    """Return a snapshot that records one physically canonical Result directory."""
    return ConfiguredPaths(
        watcher_input_directories=configured.watcher_input_directories,
        result_directories=_sorted_unique(
            [*configured.result_directories, directory]
        ),
    )


def _remember_watcher_input(
    configured: ConfiguredPaths,
    directory: Path,
) -> ConfiguredPaths:
    return ConfiguredPaths(
        watcher_input_directories=_sorted_unique(
            [*configured.watcher_input_directories, directory]
        ),
        result_directories=configured.result_directories,
    )


def prepare_watcher_input_directory(
    requested_directory: Path,
) -> PreparedWatcherInput:
    """Validate, record, and return one watcher input and state location."""
    paths = registration_user_paths()
    try:
        directory = physically_canonicalize(
            requested_directory,
            must_exist=True,
        )
        _require_directory(directory, description="watcher input")
        paths.watcher_state_directory.mkdir(parents=True, exist_ok=True)
        state_directory = physically_canonicalize(
            paths.watcher_state_directory,
            must_exist=True,
        )
        _require_directory(state_directory, description="watcher state directory")
        with registry_lock(paths):
            registry_snapshot = load_registry(paths)
            configured = load_configured_paths(paths)
            require_watcher_input_allowed(
                directory,
                registry_snapshot,
                configured,
            )
            write_configured_paths(
                paths,
                _remember_watcher_input(configured, directory),
            )
        state_name = sha256(_path_sort_key(directory)).hexdigest() + ".json"
        return PreparedWatcherInput(
            directory=directory,
            state_path=state_directory / state_name,
        )
    except PathConfigurationError:
        raise
    except Exception as exc:
        raise PathConfigurationError(
            "cannot prepare watcher input directory"
        ) from exc
