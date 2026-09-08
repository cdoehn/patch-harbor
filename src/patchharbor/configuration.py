"""Read and write PatchHarbor's shared user configuration."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path

from patchharbor.bundle_names import validate_bundle_suffix
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


_FORMAT_VERSION = 2
_LEGACY_CONFIGURATION_FIELDS = frozenset(
    {
        "exchange_directory",
        "format_version",
    }
)

_CONFIGURATION_FIELDS = _LEGACY_CONFIGURATION_FIELDS | {"bundle_suffix"}


@dataclass(frozen=True)
class UserConfiguration:
    """One loaded shared PatchHarbor configuration."""

    exchange_directory: Path
    bundle_suffix: str = ""

    def __post_init__(self) -> None:
        validate_bundle_suffix(self.bundle_suffix)


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


def resolve_exchange_directory_candidate(requested_directory: Path) -> Path:
    """Resolve an absolute candidate physically without creating its leaf."""
    directory = _absolute_exchange_directory(requested_directory)
    try:
        return physically_canonicalize(directory, must_exist=False)
    except OSError as exc:
        raise _error(
            "cannot resolve exchange directory: "
            f"{describe_os_error(exc)}"
        ) from exc
    except (RuntimeError, ValueError) as exc:
        raise _error("cannot resolve exchange directory") from exc


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


def _parse_configuration(
    content: bytes, *, validate_directory: bool = True,
) -> UserConfiguration:
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
    # Diagnose a missing version using the legacy closed-field contract.
    # The exact field-set check below still rejects a missing version.
    format_version = document.get("format_version", 1)
    if type(format_version) is not int or format_version not in {1, _FORMAT_VERSION}:
        raise _error("configuration format_version is invalid")
    expected_fields = (
        _LEGACY_CONFIGURATION_FIELDS if format_version == 1 else _CONFIGURATION_FIELDS
    )
    if set(document) != expected_fields:
        fields_description = "two format-1" if format_version == 1 else "three format-2"
        raise _error(
            f"configuration must contain exactly the {fields_description} fields"
        )
    try:
        bundle_suffix = validate_bundle_suffix(document.get("bundle_suffix", ""))
    except ValueError as exc:
        raise _error(str(exc)) from exc

    exchange_directory = document["exchange_directory"]
    if type(exchange_directory) is not str:
        raise _error("configuration exchange_directory is invalid")

    return UserConfiguration(
        exchange_directory=(
            _canonical_exchange_directory(Path(exchange_directory), create=False)
            if validate_directory
            else _absolute_exchange_directory(Path(exchange_directory))
        ),
        bundle_suffix=bundle_suffix,
    )


def load_configuration_if_present(
    paths: RegistrationUserPaths,
    *,
    validate_directory: bool = True,
) -> UserConfiguration | None:
    """Load config; directory validation may be deferred for explicit output/repair."""
    if _configuration_file_kind(paths.configuration_path) is PathKind.MISSING:
        return None

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

    return _parse_configuration(content, validate_directory=validate_directory)


def revalidate_exchange_directory(
    configuration: UserConfiguration,
) -> UserConfiguration:
    """Require the persisted physical target to remain the same directory."""
    current = _canonical_exchange_directory(
        configuration.exchange_directory,
        create=False,
    )
    if current != configuration.exchange_directory:
        raise _error("exchange directory changed during configuration")
    return configuration


def _encoded_configuration(configuration: UserConfiguration) -> bytes:
    return serialize_json_document(
        {
            "exchange_directory": str(configuration.exchange_directory),
            "format_version": _FORMAT_VERSION,
            "bundle_suffix": configuration.bundle_suffix,
        }
    ).encode("utf-8")


def prepare_exchange_directory(
    paths: RegistrationUserPaths,
    requested_directory: Path,
) -> UserConfiguration:
    """Create and physically canonicalize an exchange directory for publication."""
    absolute_directory = _absolute_exchange_directory(requested_directory)
    previous = load_configuration_if_present(paths, validate_directory=False)
    return UserConfiguration(
        exchange_directory=_canonical_exchange_directory(
            absolute_directory,
            create=True,
        ),
        bundle_suffix=previous.bundle_suffix if previous is not None else "",
    )


def write_prepared_configuration(
    paths: RegistrationUserPaths,
    configuration: UserConfiguration,
) -> UserConfiguration:
    """Atomically publish one already prepared and revalidated configuration."""
    _configuration_file_kind(paths.configuration_path)
    revalidate_exchange_directory(configuration)
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


def write_exchange_directory(
    paths: RegistrationUserPaths,
    requested_directory: Path,
) -> UserConfiguration:
    """Create, canonicalize, and atomically persist one exchange directory."""
    return write_prepared_configuration(
        paths,
        prepare_exchange_directory(paths, requested_directory),
    )


def load_configuration(paths: RegistrationUserPaths) -> UserConfiguration:
    """Load one strictly validated and usable format-1 or format-2 configuration."""
    configuration = load_configuration_if_present(paths)
    if configuration is None:
        raise _error("configuration does not exist")
    return configuration
