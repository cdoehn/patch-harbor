from __future__ import annotations

from pathlib import Path

from patchharbor.context_output import context_json_result
from patchharbor.models import (
    GitObjectFormat,
    GitObjectId,
    RepositoryContext,
    RepositoryId,
    RepositoryPath,
)


def _context(tmp_path: Path) -> RepositoryContext:
    return RepositoryContext(
        repo_id=RepositoryId("a3f9c2e1-7b4d-4a91-9d2e-5c6f8a1b2c3d"),
        repository_path=RepositoryPath(tmp_path.resolve()),
        base_commit=GitObjectId(
            value="f" * 40,
            object_format=GitObjectFormat.SHA1,
        ),
        dirty=False,
        state_fingerprint="7c9d2a24e397e0e5",
        fingerprint_algorithm="patchharbor-state-v1",
    )


def test_context_json_preserves_complete_values(
    tmp_path: Path,
) -> None:
    context = _context(tmp_path)
    document = context_json_result(context)

    assert document == {
        "repo_id": str(context.repo_id),
        "repository_path": str(context.repository_path),
        "base_commit": str(context.base_commit),
        "dirty": False,
        "state_fingerprint": context.state_fingerprint,
        "fingerprint_algorithm": context.fingerprint_algorithm,
    }
