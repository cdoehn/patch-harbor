"""Resolve repository-local configuration using one captured global registry."""

from __future__ import annotations

from pathlib import Path

from patchharbor.configuration import RepositoryConfigurationPaths
from patchharbor.errors import repository_resolution_error
from patchharbor.models import RegistrySnapshot, RepositoryId
from patchharbor.repository import inspect_repository, require_local_repository_identity


def configuration_paths_for_repository(
    path: Path, snapshot: RegistrySnapshot,
) -> RepositoryConfigurationPaths:
    repository = inspect_repository(path)
    matches = tuple(m for m in snapshot.repositories if m.repository_path == repository)
    if len(matches) != 1:
        raise repository_resolution_error("repository is not uniquely registered")
    return configuration_paths_for_id(matches[0].repo_id, snapshot)


def configuration_paths_for_id(
    repo_id: RepositoryId, snapshot: RegistrySnapshot,
) -> RepositoryConfigurationPaths:
    matches = tuple(m for m in snapshot.repositories if m.repo_id == repo_id)
    if len(matches) != 1:
        raise repository_resolution_error("repository ID is not uniquely registered")
    mapping = matches[0]
    if sum(m.repository_path == mapping.repository_path for m in snapshot.repositories) != 1:
        raise repository_resolution_error("repository path has conflicting registrations")
    repository = inspect_repository(mapping.repository_path.value)
    if repository != mapping.repository_path:
        raise repository_resolution_error("registered repository path changed")
    require_local_repository_identity(repository, repo_id)
    return RepositoryConfigurationPaths(repository, repo_id)
