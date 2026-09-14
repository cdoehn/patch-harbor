"""Physical separation policy for Exchange directories and repositories."""

from __future__ import annotations

from pathlib import Path

from patchharbor.models import RegistrySnapshot, RepositoryPath
from patchharbor.platform.paths import physical_paths_overlap


class ExchangePathPolicyError(RuntimeError):
    """One exchange/repository relation cannot be resolved or is forbidden."""


def _paths_overlap(
    exchange_directory: Path,
    repository: RepositoryPath,
    *,
    exchange_must_exist: bool,
    repository_must_exist: bool,
) -> bool:
    try:
        return physical_paths_overlap(
            exchange_directory,
            repository.value,
            first_must_exist=exchange_must_exist,
            second_must_exist=repository_must_exist,
        )
    except (OSError, RuntimeError, ValueError) as exc:
        raise ExchangePathPolicyError(
            "cannot compare exchange directory with repository path"
        ) from exc


def require_exchange_outside_registry(
    exchange_directory: Path,
    snapshot: RegistrySnapshot,
    *,
    exchange_must_exist: bool,
) -> None:
    """Reject an exchange directory overlapping any registered repository."""
    for mapping in snapshot.repositories:
        if _paths_overlap(
            exchange_directory,
            mapping.repository_path,
            exchange_must_exist=exchange_must_exist,
            repository_must_exist=False,
        ):
            raise ExchangePathPolicyError(
                "exchange directory overlaps a registered repository"
            )


def require_repository_outside_exchange(
    repository: RepositoryPath,
    exchange_directory: Path,
) -> None:
    """Reject one repository overlapping the configured exchange directory."""
    if _paths_overlap(
        exchange_directory,
        repository,
        exchange_must_exist=False,
        repository_must_exist=True,
    ):
        raise ExchangePathPolicyError(
            "repository overlaps configured exchange directory"
        )
