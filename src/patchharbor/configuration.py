"""Read and write PatchHarbor's shared user configuration."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path

from patchharbor.errors import ExitCode, PatchHarborError
from patchharbor.json_document import serialize_json_document
from patchharbor.platform.filesystem import (
    FileSystemOperationError,
    PathKind,
    atomic_replace_bytes,
    path_kind,
)
from patchharbor.platform.paths import physically_canonicalize
from patchharbor.user_paths import RegistrationUserPaths


_FORMAT_VERSION = 1


@dataclass(frozen=True)
class UserConfiguration:
    """One loaded shared PatchHarbor configuration."""

    exchange_directory: Path


def _error(message: str) -> PatchHarborError:
    return PatchHarborError(message, ExitCode.SOURCE_ERROR)


def _canonical_exchange_directory(
    requested_directory: Path,
    *,
    create: bool,
) -> Path:
    try:
        expanded = requested_directory.expanduser()
        if create:
            expanded.mkdir(parents=True, exist_ok=True)
        directory = physically_canonicalize(expanded, must_exist=True)
        if path_kind(directory) is not PathKind.DIRECTORY:
            raise _error("exchange directory is not a directory")
        return directory
    except PatchHarborError:
        raise
    except (FileSystemOperationError, OSError, RuntimeError) as exc:
        raise _error(f"cannot prepare exchange directory: {exc}") from exc


def _encoded_configuration(configuration: UserConfiguration) -> bytes:
    return serialize_json_document(
        {
            "exchange_directory": str(configuration.exchange_directory),
            "format_version": _FORMAT_VERSION,
        }
    ).encode("utf-8")


def write_exchange_directory(
    paths: RegistrationUserPaths,
    requested_directory: Path,
) -> UserConfiguration:
    """Create, canonicalize, and persist one shared exchange directory."""
    configuration = UserConfiguration(
        exchange_directory=_canonical_exchange_directory(
            requested_directory,
            create=True,
        )
    )
    try:
        atomic_replace_bytes(
            paths.configuration_path,
            _encoded_configuration(configuration),
        )
    except FileSystemOperationError as exc:
        raise _error(f"cannot write PatchHarbor configuration: {exc.cause}") from exc
    return configuration


def load_configuration(paths: RegistrationUserPaths) -> UserConfiguration:
    """Load one usable format-1 shared configuration."""
    try:
        kind = path_kind(paths.configuration_path)
    except FileSystemOperationError as exc:
        raise _error(f"cannot inspect PatchHarbor configuration: {exc.cause}") from exc
    if kind is PathKind.MISSING:
        raise _error("PatchHarbor configuration does not exist")
    if kind is not PathKind.REGULAR_FILE:
        raise _error("PatchHarbor configuration is not a regular file")

    try:
        document = json.loads(paths.configuration_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise _error(f"cannot read PatchHarbor configuration: {exc}") from exc

    if (
        not isinstance(document, dict)
        or document.get("format_version") != _FORMAT_VERSION
        or not isinstance(document.get("exchange_directory"), str)
    ):
        raise _error("PatchHarbor configuration has an invalid structure")

    return UserConfiguration(
        exchange_directory=_canonical_exchange_directory(
            Path(document["exchange_directory"]),
            create=False,
        )
    )
