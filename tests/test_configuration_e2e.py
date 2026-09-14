"""Real CLI setup is repository-local, including calls from subdirectories."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from tests.platform_support import run_cli
from tests.registration_support import (
    create_repository, git, isolated_user_environment, legacy_user_configuration_path,
)

pytestmark = pytest.mark.e2e


def setup(tmp_path):
    environment = isolated_user_environment(tmp_path / "user")
    repository = create_repository(tmp_path / "repo")
    registered = run_cli(repository, "register", environment_overrides=environment)
    assert registered.returncode == 0, registered.stderr
    return repository, environment


def test_configure_and_show_use_current_repository_from_subdirectory(tmp_path):
    repo, env = setup(tmp_path)
    before_status = git(repo, "status", "--porcelain").stdout
    child = repo / "child"
    child.mkdir()
    exchange = tmp_path / "downloads" / "exchange"
    configured = run_cli(child, "configure", "exchange-directory", str(exchange), environment_overrides=env)
    assert configured.returncode == 0, configured.stderr
    config = json.loads((repo / ".patchharbor/config.json").read_bytes())
    assert config == {"format_version": 1, "exchange_directory": str(exchange.resolve()),
                      "bundle_suffix": "", "archive_directory": "PatchHarbor-Archive"}
    assert run_cli(child, "configure", "show", environment_overrides=env).returncode == 0
    assert git(repo, "status", "--porcelain").stdout == before_status == ""
    assert not (repo / ".gitignore").exists()
    assert not legacy_user_configuration_path(env).exists()


@pytest.mark.parametrize("command", [
    ("configure", "show"), ("configure", "bundle-suffix", ".txt"),
    ("configure", "archive-dir", "Archive"),
])
def test_commands_reject_unregistered_and_nonrepository_cwd(tmp_path, command):
    env = isolated_user_environment(tmp_path / "user")
    unregistered = create_repository(tmp_path / "unregistered")
    for cwd in (tmp_path, unregistered):
        result = run_cli(cwd, *command, environment_overrides=env)
        assert result.returncode != 0
    assert not (unregistered / ".patchharbor").exists()


def test_relative_exchange_is_rejected_without_side_effects(tmp_path):
    repo, env = setup(tmp_path)
    config = repo / ".patchharbor/config.json"
    before = config.read_bytes()
    result = run_cli(repo, "configure", "exchange-directory", "relative", environment_overrides=env)
    assert result.returncode == 4
    assert config.read_bytes() == before
    assert not (repo / "relative").exists()


def test_invalid_local_config_has_no_global_fallback(tmp_path):
    repo, env = setup(tmp_path)
    old = legacy_user_configuration_path(env)
    old.write_text(json.dumps({"format_version": 3, "exchange_directory": str(tmp_path / "old")}))
    old_bytes = old.read_bytes()
    local = repo / ".patchharbor/config.json"
    local.write_bytes(b"{}\n")
    for arguments in (("configure", "show"), ("configure", "exchange-directory", str(tmp_path / "new"))):
        assert run_cli(repo, *arguments, environment_overrides=env).returncode == 4
        assert local.read_bytes() == b"{}\n"
    assert old.read_bytes() == old_bytes
    assert not (tmp_path / "new").exists()


def test_exchange_cannot_overlap_any_registered_repository(tmp_path):
    repo, env = setup(tmp_path)
    other = create_repository(tmp_path / "other")
    assert run_cli(other, "register", environment_overrides=env).returncode == 0
    before = (repo / ".patchharbor/config.json").read_bytes()
    for forbidden in (repo / "inside", repo, repo.parent, other / "inside"):
        result = run_cli(repo, "configure", "exchange-directory", str(forbidden), environment_overrides=env)
        assert result.returncode == 4
    assert (repo / ".patchharbor/config.json").read_bytes() == before
    assert not (repo / "inside").exists()
    assert not (other / "inside").exists()


def test_register_rejects_overlap_with_another_repositorys_exchange(tmp_path):
    repo, env = setup(tmp_path)
    exchange = tmp_path / "exchange"
    assert run_cli(repo, "configure", "exchange-directory", str(exchange), environment_overrides=env).returncode == 0
    nested = create_repository(exchange / "nested")
    assert run_cli(nested, "register", environment_overrides=env).returncode == 8
    assert not (nested / ".patchharbor").exists()
