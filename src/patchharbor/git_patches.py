"""Byte-exact reconstruction patch capture for Result Bundles."""

from __future__ import annotations

from dataclasses import dataclass

from patchharbor.errors import PatchHarborError, result_bundle_error
from patchharbor.git_commands import CANONICAL_DIFF_ARGUMENTS, run_git_bytes
from patchharbor.models import GitObjectId, RepositoryPath


@dataclass(frozen=True)
class GitChangePatches:
    """Raw staged and unstaged reconstruction patches for one repository."""

    staged: bytes
    unstaged: bytes


def _capture_patch(
    repository: RepositoryPath,
    *arguments: str,
) -> bytes:
    try:
        return run_git_bytes(
            "diff",
            *arguments,
            cwd=repository.value,
        )
    except PatchHarborError as exc:
        raise result_bundle_error(
            "cannot capture repository change patches"
        ) from exc


def capture_change_patches(
    repository: RepositoryPath,
    base_commit: GitObjectId,
) -> GitChangePatches:
    """Capture staged and unstaged patches as unchanged Git stdout bytes."""
    reconstruction_arguments = (
        "--binary",
        "--full-index",
        *CANONICAL_DIFF_ARGUMENTS,
    )
    staged = _capture_patch(
        repository,
        "--cached",
        *reconstruction_arguments,
        str(base_commit),
        "--",
    )
    unstaged = _capture_patch(
        repository,
        *reconstruction_arguments,
        "--",
    )
    return GitChangePatches(staged=staged, unstaged=unstaged)
