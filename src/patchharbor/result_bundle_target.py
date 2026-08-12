"""Resolve and revalidate the physical target of one Result Bundle."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from patchharbor.errors import PatchHarborError, result_bundle_error
from patchharbor.models import RegistrySnapshot
from patchharbor.physical_paths import (
    is_physically_within,
    physically_canonicalize,
)
from patchharbor.platform.filesystem import PathKind, path_kind


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
    *,
    filename: str,
) -> ResultBundleTarget:
    """Create and physically resolve a permitted Result Bundle directory."""
    try:
        candidate = physically_canonicalize(
            requested_directory,
            must_exist=False,
        )
        _require_outside_registered_repositories(
            candidate,
            snapshot,
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
        return ResultBundleTarget(
            directory=directory,
            final_path=directory / filename,
        )
    except PatchHarborError:
        raise
    except (OSError, RuntimeError) as exc:
        raise result_bundle_error(
            "cannot create the Result Bundle directory"
        ) from exc


def revalidate_result_bundle_target(
    target: ResultBundleTarget,
    snapshot: RegistrySnapshot,
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
        if target.final_path.parent != current:
            raise result_bundle_error("Result Bundle destination changed")
    except PatchHarborError:
        raise
    except (OSError, RuntimeError) as exc:
        raise result_bundle_error(
            "cannot revalidate the Result Bundle directory"
        ) from exc
