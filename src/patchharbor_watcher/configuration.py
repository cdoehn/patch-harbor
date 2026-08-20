"""User-specific operating configuration for the separate watcher."""

from __future__ import annotations

import json
import os
from pathlib import Path

from patchharbor.path_configuration import (
    PreparedWatcherInput,
    prepare_watcher_input_directory,
)
from patchharbor.platform.filesystem import (
    FileSystemOperationError,
    PathKind,
    atomic_replace_bytes,
    path_kind,
)
from patchharbor.user_paths import registration_user_paths


_WATCHER_CONFIGURATION_VERSION = 1


class WatcherConfigurationError(RuntimeError):
    """The user-specific watcher configuration is missing or invalid."""


def _configuration_payload(directory: Path) -> bytes:
    document = {
        "format_version": _WATCHER_CONFIGURATION_VERSION,
        "input_directory": os.fspath(directory),
    }
    return (
        json.dumps(
            document,
            ensure_ascii=True,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    ).encode("utf-8")


def _require_configuration_target(path: Path) -> None:
    try:
        kind = path_kind(path)
    except FileSystemOperationError as exc:
        raise WatcherConfigurationError(
            "cannot inspect watcher configuration"
        ) from exc
    if kind not in {PathKind.MISSING, PathKind.REGULAR_FILE}:
        raise WatcherConfigurationError(
            "watcher configuration is not a regular file"
        )


def configure_watcher_input_directory(
    requested_directory: Path,
) -> PreparedWatcherInput:
    """Validate and atomically persist one default watcher input directory."""
    paths = registration_user_paths()
    configuration_path = paths.watcher_configuration_path
    _require_configuration_target(configuration_path)
    prepared = prepare_watcher_input_directory(requested_directory)
    try:
        atomic_replace_bytes(
            configuration_path,
            _configuration_payload(prepared.directory),
        )
    except FileSystemOperationError as exc:
        raise WatcherConfigurationError(
            "cannot persist watcher configuration"
        ) from exc
    return prepared


def load_configured_watcher_input_directory() -> PreparedWatcherInput:
    """Load and revalidate the configured default watcher input directory."""
    paths = registration_user_paths()
    configuration_path = paths.watcher_configuration_path
    try:
        kind = path_kind(configuration_path)
    except FileSystemOperationError as exc:
        raise WatcherConfigurationError(
            "cannot inspect watcher configuration"
        ) from exc
    if kind is PathKind.MISSING:
        raise WatcherConfigurationError("watcher input is not configured")
    if kind is not PathKind.REGULAR_FILE:
        raise WatcherConfigurationError(
            "watcher configuration is not a regular file"
        )
    try:
        document = json.loads(configuration_path.read_bytes().decode("utf-8"))
    except (OSError, UnicodeDecodeError, ValueError) as exc:
        raise WatcherConfigurationError(
            "cannot read watcher configuration"
        ) from exc
    if not isinstance(document, dict) or set(document) != {
        "format_version",
        "input_directory",
    }:
        raise WatcherConfigurationError(
            "watcher configuration has an invalid schema"
        )
    if document["format_version"] != _WATCHER_CONFIGURATION_VERSION:
        raise WatcherConfigurationError(
            "watcher configuration has an unsupported version"
        )
    input_directory = document["input_directory"]
    if not isinstance(input_directory, str):
        raise WatcherConfigurationError(
            "watcher configuration input directory is invalid"
        )
    path = Path(input_directory)
    if not path.is_absolute():
        raise WatcherConfigurationError(
            "watcher configuration input directory is not absolute"
        )
    try:
        return prepare_watcher_input_directory(path)
    except (OSError, RuntimeError, ValueError) as exc:
        raise WatcherConfigurationError(
            "configured watcher input is unavailable"
        ) from exc
