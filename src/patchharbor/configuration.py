"""Strict repository-local configuration; no global fallback or migration."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path

from patchharbor.archive_policy import DEFAULT_ARCHIVE_DIRECTORY, validate_archive_directory
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
from patchharbor.models import RepositoryId, RepositoryPath
from patchharbor.repository import require_local_repository_identity


_FORMAT_VERSION = 1
_CONFIGURATION_FIELDS = frozenset({
    "format_version", "exchange_directory", "bundle_suffix", "archive_directory",
})


@dataclass(frozen=True)
class RepositoryConfigurationPaths:
    """A local config location bound to one already resolved repository identity."""

    repository: RepositoryPath
    repo_id: RepositoryId

    @property
    def configuration_directory(self) -> Path:
        return self.repository.value / ".patchharbor"

    @property
    def configuration_path(self) -> Path:
        return self.configuration_directory / "config.json"

    def require_identity(self) -> None:
        # Also rejects linked metadata directories and a missing local exclude.
        require_local_repository_identity(self.repository, self.repo_id)


@dataclass(frozen=True)
class RepositoryConfiguration:
    """One repository's settings; Exchange may be unset after registration."""

    exchange_directory: Path | None = None
    bundle_suffix: str = ""
    archive_directory: str = DEFAULT_ARCHIVE_DIRECTORY

    def __post_init__(self) -> None:
        validate_bundle_suffix(self.bundle_suffix)
        validate_archive_directory(self.archive_directory)


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
) -> RepositoryConfiguration:
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
    format_version = document.get("format_version")
    if type(format_version) is not int or format_version != _FORMAT_VERSION:
        raise _error("configuration format_version is invalid")
    if set(document) != _CONFIGURATION_FIELDS:
        raise _error("configuration must contain exactly the four format-1 fields")
    try:
        bundle_suffix = validate_bundle_suffix(document["bundle_suffix"])
        archive_directory = validate_archive_directory(
            document["archive_directory"]
        )
    except ValueError as exc:
        raise _error(str(exc)) from exc

    exchange_directory = document["exchange_directory"]
    if exchange_directory is not None and (type(exchange_directory) is not str or not exchange_directory or "\x00" in exchange_directory):
        raise _error("configuration exchange_directory is invalid")

    return RepositoryConfiguration(
        exchange_directory=(
            None if exchange_directory is None else (
                _canonical_exchange_directory(Path(exchange_directory), create=False)
                if validate_directory
                else _absolute_exchange_directory(Path(exchange_directory))
            )
        ),
        bundle_suffix=bundle_suffix,
        archive_directory=archive_directory,
    )


def load_configuration_if_present(
    paths: RepositoryConfigurationPaths,
    *,
    validate_directory: bool = True,
) -> RepositoryConfiguration | None:
    """Load local settings; never interpret any user-global configuration."""
    paths.require_identity()
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
    configuration: RepositoryConfiguration,
) -> RepositoryConfiguration:
    """Require the persisted physical target to remain the same directory."""
    if configuration.exchange_directory is None:
        raise _error(
            "repository has no exchange directory; run "
            "'patchharbor configure exchange-directory DIRECTORY' in this repository"
        )
    current = _canonical_exchange_directory(
        configuration.exchange_directory,
        create=False,
    )
    if current != configuration.exchange_directory:
        raise _error("exchange directory changed during configuration")
    return configuration


def _encoded_configuration(configuration: RepositoryConfiguration) -> bytes:
    return serialize_json_document(
        {
            "exchange_directory": (str(configuration.exchange_directory)
                                   if configuration.exchange_directory is not None else None),
            "format_version": _FORMAT_VERSION,
            "bundle_suffix": configuration.bundle_suffix,
            "archive_directory": configuration.archive_directory,
        }
    ).encode("utf-8")


def prepare_exchange_directory(
    paths: RepositoryConfigurationPaths,
    requested_directory: Path,
) -> RepositoryConfiguration:
    """Create and physically canonicalize an exchange directory for publication."""
    absolute_directory = _absolute_exchange_directory(requested_directory)
    previous = load_configuration(paths, validate_directory=False)
    return RepositoryConfiguration(
        exchange_directory=_canonical_exchange_directory(
            absolute_directory,
            create=True,
        ),
        bundle_suffix=previous.bundle_suffix,
        archive_directory=previous.archive_directory,
    )


def write_prepared_configuration(
    paths: RepositoryConfigurationPaths,
    configuration: RepositoryConfiguration,
) -> RepositoryConfiguration:
    """Atomically publish one already prepared and revalidated configuration."""
    # Existing valid local settings are mandatory, even for an explicit update.
    load_configuration(paths, validate_directory=False)
    if configuration.exchange_directory is not None:
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
    paths: RepositoryConfigurationPaths,
    requested_directory: Path,
) -> RepositoryConfiguration:
    """Create, canonicalize, and atomically persist one exchange directory."""
    return write_prepared_configuration(
        paths,
        prepare_exchange_directory(paths, requested_directory),
    )


def initialize_configuration(paths: RepositoryConfigurationPaths) -> None:
    """Create defaults only as part of a fresh registration transaction.

    The registration coordinator holds the registry lock and restores its local
    snapshot on failure. This is never called for an existing local identity.
    """
    paths.require_identity()
    if _configuration_file_kind(paths.configuration_path) is not PathKind.MISSING:
        raise _error("configuration already exists; refusing to overwrite it")
    try:
        atomic_replace_bytes(paths.configuration_path, _encoded_configuration(RepositoryConfiguration()))
    except FileSystemOperationError as exc:
        raise _error(f"cannot initialize configuration: {describe_os_error(exc.cause)}") from exc


def load_configuration(
    paths: RepositoryConfigurationPaths, *, validate_directory: bool = True,
) -> RepositoryConfiguration:
    """Require a valid local format-1 document; never create or repair one."""
    configuration = load_configuration_if_present(paths, validate_directory=validate_directory)
    if configuration is None:
        raise _error(
            f"repository configuration does not exist: {paths.configuration_path}; "
            "manual setup is required (no automatic migration or repair)"
        )
    return configuration
