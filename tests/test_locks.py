from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest

from tests.platform_support import project_environment
from tests.registration_support import (
    isolated_user_environment,
    probe_repository_lock,
    release_repository_lock_holder,
    start_repository_lock_holder,
    stop_repository_lock_holder,
)


pytestmark = pytest.mark.e2e


def _lock_environment(tmp_path: Path) -> dict[str, str]:
    return project_environment(
        isolated_user_environment(tmp_path / "user")
    )


def test_repository_lock_is_exclusive_and_reusable_after_normal_exit(
    tmp_path: Path,
) -> None:
    repo_id = str(uuid4())
    environment = _lock_environment(tmp_path)
    holder = start_repository_lock_holder(repo_id, environment=environment)
    try:
        assert probe_repository_lock(repo_id, environment) == 12
        assert release_repository_lock_holder(holder) == 0
        assert probe_repository_lock(repo_id, environment) == 0
    finally:
        stop_repository_lock_holder(holder)


def test_repository_lock_is_reusable_after_an_error(tmp_path: Path) -> None:
    repo_id = str(uuid4())
    environment = _lock_environment(tmp_path)
    holder = start_repository_lock_holder(
        repo_id,
        environment=environment,
        mode="error",
    )
    try:
        assert release_repository_lock_holder(holder) != 0
        assert probe_repository_lock(repo_id, environment) == 0
    finally:
        stop_repository_lock_holder(holder)


def test_repository_lock_is_reusable_after_process_termination(
    tmp_path: Path,
) -> None:
    repo_id = str(uuid4())
    environment = _lock_environment(tmp_path)
    holder = start_repository_lock_holder(repo_id, environment=environment)
    try:
        holder.terminate()
        holder.wait(timeout=10)
        assert probe_repository_lock(repo_id, environment) == 0
    finally:
        stop_repository_lock_holder(holder)
