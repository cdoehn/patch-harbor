from __future__ import annotations

from pathlib import Path

import pytest

from patchharbor.application import register_repository, repository_context
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
