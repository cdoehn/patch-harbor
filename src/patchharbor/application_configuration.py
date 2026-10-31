"""Registered repository configuration and identity workflows.

Registry/repository lock ordering and pre-publication revalidation live here.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
from pathlib import Path

from patchharbor.archive_policy import validate_archive_directory
from patchharbor.bundle_names import validate_bundle_suffix
from patchharbor.configuration import (
    RepositoryConfiguration,
    RepositoryConfigurationPaths,
    load_configuration,
    prepare_exchange_directory,
    resolve_exchange_directory_candidate,
    revalidate_exchange_directory,
    write_prepared_configuration,
)
from patchharbor.configuration_context import configuration_paths_for_repository
from patchharbor.errors import (
    configuration_error,
    registry_error,
    repository_resolution_error,
)
from patchharbor.exchange_paths import (
    ExchangePathPolicyError,
    require_exchange_outside_registry,
)
from patchharbor.locks import registry_lock, repository_lock
from patchharbor.models import (
    RegistryListResult,
    RegistrySnapshot,
    RepositoryContext,
    RepositoryId,
    RepositoryPath,
)
from patchharbor.registration import (
    list_registered_repositories,
    register_local_repository,
    unregister_local_repository,
)
from patchharbor.registry import load_registry
from patchharbor.repository_state import (
    capture_repository_context,
    require_clean_repository,
)
from patchharbor.user_paths import configuration_user_paths


def _require_exchange_configuration_allowed(
    exchange_directory: Path,
    registry_snapshot: RegistrySnapshot,
    *,
    exchange_must_exist: bool,
) -> None:
    try:
        require_exchange_outside_registry(
            exchange_directory,
            registry_snapshot,
            exchange_must_exist=exchange_must_exist,
        )
    except ExchangePathPolicyError as exc:
        raise configuration_error(str(exc)) from exc


def _change_repository_configuration(
    repository: Path,
    change: Callable[[RepositoryConfigurationPaths, RepositoryConfiguration, RegistrySnapshot], RepositoryConfiguration],
) -> tuple[Path, RepositoryConfiguration]:
    """Serialize local setting updates with registration and running Apply."""
    paths = configuration_user_paths()
    with registry_lock(paths):
        expected_registry = load_registry(paths)
        local = configuration_paths_for_repository(repository, expected_registry)
        with repository_lock(paths, local.repo_id):
            previous = load_configuration(local, validate_directory=False)
            updated = change(local, previous, expected_registry)
            if load_registry(paths) != expected_registry:
                raise registry_error("repository registry changed while configuring exchange directory")
            if configuration_paths_for_repository(repository, expected_registry) != local:
                raise repository_resolution_error("repository identity changed while configuring")
            if load_configuration(local, validate_directory=False) != previous:
                raise configuration_error("repository configuration changed while configuring")
            if updated.exchange_directory is not None:
                revalidate_exchange_directory(updated)
                _require_exchange_configuration_allowed(
                    updated.exchange_directory, expected_registry, exchange_must_exist=True,
                )
            return local.configuration_path, write_prepared_configuration(local, updated)


def configure_exchange_directory(
    path: Path, *, repository: Path = Path("."),
) -> tuple[Path, RepositoryConfiguration]:
    """Persist the current (or explicitly selected API) repository's Exchange."""
    def change(local, previous, registry):
        candidate = resolve_exchange_directory_candidate(path)
        _require_exchange_configuration_allowed(candidate, registry, exchange_must_exist=False)
        return prepare_exchange_directory(local, path)
    return _change_repository_configuration(repository, change)


def configure_bundle_suffix(
    suffix: str, *, repository: Path = Path("."),
) -> tuple[Path, RepositoryConfiguration]:
    """Change this repository's suffix, including before Exchange is configured."""
    try:
        suffix = validate_bundle_suffix(suffix)
    except ValueError as exc:
        raise configuration_error(str(exc)) from exc
    return _change_repository_configuration(
        repository, lambda local, previous, registry: replace(previous, bundle_suffix=suffix),
    )


def configure_archive_directory(
    name: str, *, repository: Path = Path("."),
) -> tuple[Path, RepositoryConfiguration]:
    """Change this repository's archive child name; empty means disabled."""
    try:
        name = validate_archive_directory(name)
    except ValueError as exc:
        raise configuration_error(str(exc)) from exc
    return _change_repository_configuration(
        repository, lambda local, previous, registry: replace(previous, archive_directory=name),
    )


def repository_configuration(
    repository: Path = Path("."), *, revalidate: bool = False,
) -> tuple[Path, RepositoryConfiguration]:
    """Read only the selected registered repository's valid local settings."""
    paths = configuration_user_paths()
    with registry_lock(paths):
        registry = load_registry(paths)
        local = configuration_paths_for_repository(repository, registry)
        configuration = load_configuration(local, validate_directory=False)
        if revalidate:
            revalidate_exchange_directory(configuration)
            _require_exchange_configuration_allowed(
                configuration.exchange_directory, registry, exchange_must_exist=True,
            )
        return local.configuration_path, configuration


def register_repository(
    path: Path,
    *,
    new_id: bool = False,
) -> RepositoryContext:
    """Register one local Git repository and return its current context."""
    repository = require_clean_repository(path)
    _repo_id, repository_path = register_local_repository(
        repository.value,
        new_id=new_id,
    )
    return capture_repository_context(repository_path.value)


def repository_context(path: Path) -> RepositoryContext:
    """Return the current reproducible context of one registered repository."""
    context = capture_repository_context(path)
    load_configuration(RepositoryConfigurationPaths(context.repository_path, context.repo_id), validate_directory=False)
    return context


def registered_repositories() -> RegistryListResult:
    """Return one structured view of all registered local instances."""
    return list_registered_repositories()


def unregister_repository(
    selector: str,
    *,
    cwd: Path,
) -> tuple[RepositoryId, RepositoryPath]:
    """Remove one central repository mapping."""
    return unregister_local_repository(selector, cwd=cwd)
