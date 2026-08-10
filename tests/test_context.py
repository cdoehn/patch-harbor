from __future__ import annotations

from pathlib import Path

import pytest

from patchharbor import repository_state
from patchharbor.application import register_repository, repository_context
from patchharbor.locks import registry_lock, repository_lock
from patchharbor.user_paths import registration_user_paths
from tests.registration_support import (
    create_repository,
    set_isolated_user_environment,
)


def test_registration_returns_the_same_context_service_result(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = create_repository(tmp_path / "repository")
    set_isolated_user_environment(monkeypatch, tmp_path / "user")

    registered_context = register_repository(repository)
    current_context = repository_context(repository)

    assert registered_context == current_context


def test_context_releases_registry_before_capture_and_repository_before_projection(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = create_repository(tmp_path / "repository")
    set_isolated_user_environment(monkeypatch, tmp_path / "user")
    registered = register_repository(repository)
    paths = registration_user_paths()

    original_capture = repository_state.capture_consistent_repository_snapshot
    original_projection = repository_state.repository_context_from_snapshot

    def capture_after_registry_release(repository_path):
        with registry_lock(paths):
            pass
        return original_capture(repository_path)

    def project_after_repository_release(repository_path, repo_id, snapshot):
        with repository_lock(paths, repo_id):
            pass
        return original_projection(repository_path, repo_id, snapshot)

    monkeypatch.setattr(
        repository_state,
        "capture_consistent_repository_snapshot",
        capture_after_registry_release,
    )
    monkeypatch.setattr(
        repository_state,
        "repository_context_from_snapshot",
        project_after_repository_release,
    )

    assert repository_context(repository) == registered
