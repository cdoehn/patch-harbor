"""Functional isolation checks; no assertions about progress/output styling."""
from __future__ import annotations

import os
from pathlib import Path
import random
import signal
import sys
import tempfile
import types

import pytest

from patchharbor.user_paths import registration_user_paths
from tests.conftest import ProcessStateLeak, assert_process_state_restored
from tests.registration_support import create_repository, git


def test_environment_does_not_prepopulate_workspace(tmp_path: Path, isolated_test_environment: Path) -> None:
    assert list(tmp_path.iterdir()) == []
    assert not isolated_test_environment.is_relative_to(tmp_path)


def test_default_runtime_paths_are_test_local(tmp_path: Path, isolated_test_environment: Path) -> None:
    paths = registration_user_paths()
    assert paths.configuration_directory.is_relative_to(isolated_test_environment)
    assert paths.lock_directory.is_relative_to(isolated_test_environment)
    assert Path(tempfile.gettempdir()).is_relative_to(isolated_test_environment)
    assert Path.home().is_relative_to(isolated_test_environment)
    with tempfile.TemporaryDirectory() as temporary:
        assert Path(temporary).is_relative_to(isolated_test_environment)


@pytest.mark.parametrize("component", ["cwd", "environment", "sys.path", "random", "signal"])
def test_process_guard_detects_and_restores_leaks(tmp_path: Path, component: str) -> None:
    cwd = Path.cwd()
    environment = dict(os.environ)
    path = sys.path[:]
    random_state = random.getstate()
    handler = signal.getsignal(signal.SIGTERM)
    with pytest.raises(ProcessStateLeak):
        with assert_process_state_restored():
            if component == "cwd":
                os.chdir(tmp_path)
            elif component == "environment":
                os.environ["PATCHHARBOR_TEST_LEAK"] = "unexpected"
            elif component == "sys.path":
                sys.path.append(str(tmp_path))
            elif component == "random":
                random.seed(987654321)
            else:
                signal.signal(signal.SIGTERM, lambda *args: None)
    assert Path.cwd() == cwd
    assert dict(os.environ) == environment
    assert sys.path == path
    assert random.getstate() == random_state
    assert signal.getsignal(signal.SIGTERM) == handler


def test_monkeypatch_module_removal_restores_original_identity() -> None:
    name = "patchharbor_test_module_identity"
    original = types.ModuleType(name)
    with pytest.MonkeyPatch.context() as setup:
        setup.setitem(sys.modules, name, original)
        with pytest.MonkeyPatch.context() as patch:
            patch.delitem(sys.modules, name)
            assert name not in sys.modules
        assert sys.modules[name] is original
    assert name not in sys.modules


def test_git_helpers_only_mutate_their_private_repository(tmp_path: Path) -> None:
    first = create_repository(tmp_path / "first")
    second = create_repository(tmp_path / "second")
    before = git(second, "rev-parse", "HEAD").stdout
    (first / "change.txt").write_text("private", encoding="utf-8")
    git(first, "add", "change.txt")
    git(first, "commit", "--quiet", "-m", "private commit")
    assert not (second / "change.txt").exists()
    assert git(second, "rev-parse", "HEAD").stdout == before


@pytest.mark.skipif(os.name == "nt", reason="Windows does not allow removing the process CWD")
def test_process_guard_recovers_a_deleted_working_directory(tmp_path: Path) -> None:
    before = Path.cwd()
    directory = tmp_path / "removed-cwd"
    directory.mkdir()
    with pytest.raises(ProcessStateLeak):
        with assert_process_state_restored():
            os.chdir(directory)
            directory.rmdir()
    assert Path.cwd() == before


def test_dynamic_environment_checker_import_does_not_leak_process_state() -> None:
    from tests.test_docker_integration_runner import _environment_check_module
    name = "patchharbor_docker_environment_check"
    sentinel = object()
    before = sys.modules.get(name, sentinel)
    with assert_process_state_restored():
        module = _environment_check_module()
        assert callable(module.main)
    assert sys.modules.get(name, sentinel) is before
