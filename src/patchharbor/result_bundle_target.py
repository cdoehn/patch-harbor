"""Resolve and revalidate the physical target of one Result Bundle."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from patchharbor.errors import PatchHarborError, result_bundle_error
from patchharbor.models import RegistrySnapshot
from patchharbor.path_configuration import (
    PathConfigurationError,
    load_configured_paths,
    remember_result_directory,
    require_result_directory_allowed,
    write_configured_paths,
)
from patchharbor.platform.paths import (
    is_physically_within,
    physically_canonicalize,
)
from patchharbor.platform.filesystem import PathKind, path_kind
from patchharbor.user_paths import RegistrationUserPaths


@dataclass(frozen=True)
class ResultBundleTarget:
    """One physically resolved output directory and final bundle path."""

    directory: Path
    final_path: Path


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


def _require_directory(path: Path) -> None:
    if path_kind(path) is not PathKind.DIRECTORY:
        raise result_bundle_error("Result Bundle path is not a directory")


def prepare_result_bundle_target(
    requested_directory: Path,
    snapshot: RegistrySnapshot,
    paths: RegistrationUserPaths,
    *,
    filename: str,
) -> ResultBundleTarget:
    """Create and physically resolve a permitted Result Bundle directory."""
    try:
        configured = load_configured_paths(paths)
        candidate = physically_canonicalize(
            requested_directory,
            must_exist=False,
        )
        _require_outside_registered_repositories(
            candidate,
            snapshot,
            directory_must_exist=False,
        )
        require_result_directory_allowed(
            candidate,
            configured,
            directory_must_exist=False,
        )
        candidate.mkdir(parents=True, exist_ok=True)
        directory = physically_canonicalize(candidate, must_exist=True)
        _require_directory(directory)
        _require_outside_registered_repositories(
            directory,
            snapshot,
            directory_must_exist=True,
        )
        require_result_directory_allowed(
            directory,
            configured,
            directory_must_exist=True,
        )
        write_configured_paths(
            paths,
            remember_result_directory(configured, directory),
        )
        return ResultBundleTarget(
            directory=directory,
            final_path=directory / filename,
        )
    except PatchHarborError:
        raise
    except PathConfigurationError as exc:
        raise result_bundle_error(str(exc)) from exc
    except (OSError, RuntimeError) as exc:
        raise result_bundle_error(
            "cannot create the Result Bundle directory"
        ) from exc


def revalidate_result_bundle_target(
    target: ResultBundleTarget,
    snapshot: RegistrySnapshot,
    paths: RegistrationUserPaths,
) -> None:
    """Reject a target whose physical directory or registry boundary changed."""
    try:
        current = physically_canonicalize(target.directory, must_exist=True)
        if current != target.directory:
            raise result_bundle_error(
                "Result Bundle directory changed after validation"
            )
        _require_directory(current)
        _require_outside_registered_repositories(
            current,
            snapshot,
            directory_must_exist=True,
        )
        require_result_directory_allowed(
            current,
            load_configured_paths(paths),
            directory_must_exist=True,
        )
        if target.final_path.parent != current:
            raise result_bundle_error("Result Bundle destination changed")
    except PatchHarborError:
        raise
    except PathConfigurationError as exc:
        raise result_bundle_error(str(exc)) from exc
    except (OSError, RuntimeError) as exc:
        raise result_bundle_error(
            "cannot revalidate the Result Bundle directory"
        ) from exc
