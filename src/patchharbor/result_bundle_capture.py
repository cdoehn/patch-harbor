"""Capture all bytes of one consistent PatchHarbor Result Bundle."""

from __future__ import annotations

from dataclasses import dataclass

from patchharbor.errors import result_bundle_error
from patchharbor.git_objects import capture_base_bundle_entries
from patchharbor.git_patches import capture_change_patches
from patchharbor.models import (
    RepositoryContext,
    RepositoryId,
    RepositoryPath,
    RepositorySnapshot,
)
from patchharbor.repository_state import (
    capture_consistent_repository_snapshot,
    repository_context_from_snapshot,
)
from patchharbor.result_bundle_snapshot import (
    ResultBundleSnapshot,
    build_result_bundle_snapshot,
)


@dataclass(frozen=True)
class CapturedResultBundle:
    """One context and all bundle bytes from one unchanged repository state."""

    repository_snapshot: RepositorySnapshot
    context: RepositoryContext
    bundle_snapshot: ResultBundleSnapshot


def capture_result_bundle(
    repository: RepositoryPath,
    repo_id: RepositoryId,
) -> CapturedResultBundle:
    """Capture one bundle and reject any before/after state difference."""
    before = capture_consistent_repository_snapshot(repository)
    before_context = repository_context_from_snapshot(
        repository,
        repo_id,
        before,
    )
    base_entries = capture_base_bundle_entries(
        repository,
        before.base_commit,
    )
    change_patches = capture_change_patches(
        repository,
        before.base_commit,
    )
    bundle_snapshot = build_result_bundle_snapshot(
        base_entries=(
            (
                entry.path.original_bytes,
                entry.mode,
                entry.object_id,
                entry.content,
            )
            for entry in base_entries
        ),
        staged_patch=change_patches.staged,
        unstaged_patch=change_patches.unstaged,
        untracked_entries=(
            (record.path, record.mode, record.content)
            for record in before.state.untracked
        ),
    )

    after = capture_consistent_repository_snapshot(repository)
    after_context = repository_context_from_snapshot(
        repository,
        repo_id,
        after,
    )
    if after != before or after_context != before_context:
        raise result_bundle_error(
            "repository changed while the Result Bundle was captured"
        )

    return CapturedResultBundle(
        repository_snapshot=before,
        context=before_context,
        bundle_snapshot=bundle_snapshot,
    )
