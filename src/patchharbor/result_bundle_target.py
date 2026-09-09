"""Resolve and revalidate the physical target of one Result Bundle."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from patchharbor.bundle_names import append_bundle_suffix
from patchharbor.configuration import (
    UserConfiguration,
    load_configuration_if_present,
    load_configuration,
    revalidate_exchange_directory,
)
from patchharbor.errors import (
    PatchHarborError,
    configuration_error,
    result_bundle_error,
)
from patchharbor.exchange_paths import (
    ExchangePathPolicyError,
    require_exchange_outside_registry,
)
from patchharbor.models import RegistrySnapshot
from patchharbor.platform.filesystem import PathKind, path_kind
from patchharbor.platform.paths import (
    is_physically_within,
    physically_canonicalize,
)
from patchharbor.user_paths import RegistrationUserPaths


@dataclass(frozen=True, slots=True)
class ResultBundleTarget:
    """One physically resolved output directory and final bundle path."""

    directory: Path
    final_path: Path
    uses_exchange_directory: bool
    bundle_suffix: str = ""
    exchange_directory: Path | None = None

    def __post_init__(self) -> None:
        if self.final_path.parent != self.directory:
            raise ValueError(
                "Result Bundle path must be inside its target directory"
            )


def _require_outside_registered_repositories(
    directory: Path,
    snapshot: RegistrySnapshot,
    *,
    directory_must_exist: bool,
) -> None:
    for mapping in snapshot.repositories:
        if is_physically_within(
            directory,
            mapping.repository_path.value,
            candidate_must_exist=directory_must_exist,
            root_must_exist=False,
        ):
            raise result_bundle_error(
                "Result Bundle directory overlaps a registered repository"
            )


def _require_exchange_allowed(
    directory: Path,
    snapshot: RegistrySnapshot,
    *,
    directory_must_exist: bool,
) -> None:
    try:
        require_exchange_outside_registry(
            directory,
            snapshot,
            exchange_must_exist=directory_must_exist,
        )
    except ExchangePathPolicyError as exc:
        raise configuration_error(str(exc)) from exc


def _require_directory(path: Path) -> None:
    if path_kind(path) is not PathKind.DIRECTORY:
        raise result_bundle_error("Result Bundle path is not a directory")


def _explicit_output_configuration(paths: RegistrationUserPaths) -> UserConfiguration | None:
    """Keep explicit output usable without a usable Exchange configuration."""
    try:
        configuration = load_configuration_if_present(paths, validate_directory=False)
    except PatchHarborError:
        # Explicit output has historically remained a recovery path even when
        # config.json is malformed. Never guess or apply an invalid suffix.
        return None
    return configuration


def _requested_result_directory(
    requested_directory: Path | None,
    paths: RegistrationUserPaths,
) -> tuple[Path, bool, str, Path | None]:
    if requested_directory is not None:
        configuration = _explicit_output_configuration(paths)
        return (
            requested_directory, False,
            configuration.bundle_suffix if configuration is not None else "",
            configuration.exchange_directory if configuration is not None else None,
        )

    configuration = revalidate_exchange_directory(load_configuration(paths))
    return configuration.exchange_directory, True, configuration.bundle_suffix, configuration.exchange_directory


def prepare_result_bundle_target(
    requested_directory: Path | None,
    snapshot: RegistrySnapshot,
    paths: RegistrationUserPaths,
    *,
    filename: str,
) -> ResultBundleTarget:
    """Resolve one explicit target or the configured shared Exchange target."""
    directory_request, uses_exchange_directory, bundle_suffix, exchange_directory = _requested_result_directory(
        requested_directory,
        paths,
    )
    try:
        candidate = physically_canonicalize(
            directory_request,
            must_exist=uses_exchange_directory,
        )
        if uses_exchange_directory:
            _require_exchange_allowed(
                candidate,
                snapshot,
                directory_must_exist=True,
            )
        else:
            _require_outside_registered_repositories(
                candidate,
                snapshot,
                directory_must_exist=False,
            )
            candidate.mkdir(parents=True, exist_ok=True)

        directory = physically_canonicalize(candidate, must_exist=True)
        _require_directory(directory)
        if uses_exchange_directory:
            _require_exchange_allowed(
                directory,
                snapshot,
                directory_must_exist=True,
            )
        else:
            _require_outside_registered_repositories(
                directory,
                snapshot,
                directory_must_exist=True,
            )
        return ResultBundleTarget(
            directory=directory,
            final_path=directory / append_bundle_suffix(filename, bundle_suffix),
            uses_exchange_directory=uses_exchange_directory,
            bundle_suffix=bundle_suffix,
            exchange_directory=exchange_directory,
        )
    except PatchHarborError:
        raise
    except (OSError, RuntimeError, ValueError) as exc:
        raise result_bundle_error(
            "cannot create the Result Bundle directory"
        ) from exc


def revalidate_result_bundle_target(
    target: ResultBundleTarget,
    snapshot: RegistrySnapshot,
    paths: RegistrationUserPaths,
) -> None:
    """Reject a target whose physical directory or configuration changed."""
    try:
        current = physically_canonicalize(target.directory, must_exist=True)
        if current != target.directory:
            raise result_bundle_error(
                "Result Bundle directory changed after validation"
            )
        _require_directory(current)

        if target.uses_exchange_directory:
            configuration = revalidate_exchange_directory(
                load_configuration(paths)
            )
            if configuration.exchange_directory != current:
                raise configuration_error(
                    "exchange directory changed during Result Bundle preparation"
                )
            if configuration.bundle_suffix != target.bundle_suffix:
                raise configuration_error(
                    "bundle suffix changed during Result Bundle preparation"
                )
            _require_exchange_allowed(
                current,
                snapshot,
                directory_must_exist=True,
            )
        else:
            configuration = _explicit_output_configuration(paths)
            suffix = configuration.bundle_suffix if configuration is not None else ""
            exchange = configuration.exchange_directory if configuration is not None else None
            if suffix != target.bundle_suffix:
                raise configuration_error(
                    "bundle suffix changed during Result Bundle preparation"
                )
            if exchange != target.exchange_directory:
                raise configuration_error(
                    "exchange directory changed during Result Bundle preparation"
                )
            _require_outside_registered_repositories(
                current,
                snapshot,
                directory_must_exist=True,
            )

        if target.final_path.parent != current:
            raise result_bundle_error("Result Bundle destination changed")
    except PatchHarborError:
        raise
    except (OSError, RuntimeError, ValueError) as exc:
        raise result_bundle_error(
            "cannot revalidate the Result Bundle directory"
        ) from exc
