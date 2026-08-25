"""Read and write PatchHarbor's shared user configuration."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path

from patchharbor.errors import PatchHarborError, configuration_error
from patchharbor.json_document import serialize_json_document
from patchharbor.platform.errors import describe_os_error
from patchharbor.platform.filesystem import (
    FileChangedDuringRead,
    FileSystemOperationError,
    PathKind,
    UnsupportedFileTypeError,
    atomic_replace_bytes,
    path_kind,
    read_stable_regular_file,
)
from patchharbor.platform.paths import physically_canonicalize
from patchharbor.user_paths import RegistrationUserPaths


_FORMAT_VERSION = 1
_CONFIGURATION_FIELDS = frozenset(
    {
        "exchange_directory",
        "format_version",
    }
)


@dataclass(frozen=True)
class UserConfiguration:
    """One loaded shared PatchHarbor configuration."""

    exchange_directory: Path


class _DuplicateJsonKey(ValueError):
    pass


def _error(message: str) -> PatchHarborError:
    return configuration_error(message)


def _reject_duplicate_keys(
    pairs: list[tuple[str, object]],
) -> dict[str, object]:
    document: dict[str, object] = {}
    for key, value in pairs:
        if key in document:
            raise _DuplicateJsonKey(key)
        document[key] = value
    return document


def _reject_non_finite_number(value: str) -> object:
    raise ValueError(f"non-finite JSON number: {value}")


def _configuration_file_kind(path: Path) -> PathKind:
    try:
        kind = path_kind(path)
    except FileSystemOperationError as exc:
        raise _error(
            "cannot inspect configuration: "
            f"{describe_os_error(exc.cause)}"
        ) from exc
    if kind not in {PathKind.MISSING, PathKind.REGULAR_FILE}:
        raise _error("configuration must be a regular file")
    return kind


def _absolute_exchange_directory(requested_directory: Path) -> Path:
    if not requested_directory.is_absolute():
        raise _error("exchange directory must be an absolute path")
    return requested_directory


def _canonical_exchange_directory(
    requested_directory: Path,
    *,
    create: bool,
) -> Path:
    directory = _absolute_exchange_directory(requested_directory)
    if create:
        try:
            directory.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise _error(
                "cannot create exchange directory: "
                f"{describe_os_error(exc)}"
            ) from exc

    try:
        canonical = physically_canonicalize(directory, must_exist=True)
    except FileNotFoundError as exc:
        raise _error("exchange directory does not exist") from exc
    except OSError as exc:
        raise _error(
            "cannot resolve exchange directory: "
            f"{describe_os_error(exc)}"
        ) from exc
    except (RuntimeError, ValueError) as exc:
        raise _error("cannot resolve exchange directory") from exc

    try:
        kind = path_kind(canonical)
    except FileSystemOperationError as exc:
        raise _error(
            "cannot inspect exchange directory: "
            f"{describe_os_error(exc.cause)}"
        ) from exc
    if kind is not PathKind.DIRECTORY:
        raise _error("exchange directory is not a directory")
    return canonical


def _parse_configuration(content: bytes) -> UserConfiguration:
    if content.startswith(b"\xef\xbb\xbf"):
        raise _error("configuration must be UTF-8 without a BOM")
    try:
        text = content.decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise _error("configuration is not valid UTF-8") from exc

    try:
        document = json.loads(
            text,
            object_pairs_hook=_reject_duplicate_keys,
            parse_constant=_reject_non_finite_number,
        )
    except (json.JSONDecodeError, _DuplicateJsonKey, ValueError) as exc:
        raise _error("configuration is not one valid JSON object") from exc

    if type(document) is not dict:
        raise _error("configuration must contain one JSON object")
    if set(document) != _CONFIGURATION_FIELDS:
        raise _error(
            "configuration must contain exactly the two format-1 fields"
        )

    format_version = document["format_version"]
    if type(format_version) is not int or format_version != _FORMAT_VERSION:
        raise _error("configuration format_version is invalid")

    exchange_directory = document["exchange_directory"]
    if type(exchange_directory) is not str:
        raise _error("configuration exchange_directory is invalid")

    return UserConfiguration(
        exchange_directory=_canonical_exchange_directory(
            Path(exchange_directory),
            create=False,
        )
    )


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
    """Create, canonicalize, and atomically persist one exchange directory."""
    absolute_directory = _absolute_exchange_directory(requested_directory)
    _configuration_file_kind(paths.configuration_path)
    configuration = UserConfiguration(
        exchange_directory=_canonical_exchange_directory(
            absolute_directory,
            create=True,
        )
    )
    try:
        atomic_replace_bytes(
            paths.configuration_path,
            _encoded_configuration(configuration),
        )
    except FileSystemOperationError as exc:
        raise _error(
            "cannot write configuration: "
            f"{describe_os_error(exc.cause)}"
        ) from exc
    return configuration


def load_configuration(paths: RegistrationUserPaths) -> UserConfiguration:
    """Load one strictly validated and usable format-1 configuration."""
    if _configuration_file_kind(paths.configuration_path) is PathKind.MISSING:
        raise _error("configuration does not exist")

    try:
        content = read_stable_regular_file(paths.configuration_path).content
    except UnsupportedFileTypeError as exc:
        raise _error("configuration must be a regular file") from exc
    except FileChangedDuringRead as exc:
        raise _error("configuration changed while it was being read") from exc
    except FileSystemOperationError as exc:
        raise _error(
            "cannot read configuration: "
            f"{describe_os_error(exc.cause)}"
        ) from exc

    return _parse_configuration(content)
