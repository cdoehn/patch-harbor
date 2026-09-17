"""Real CLI setup is repository-local, including calls from subdirectories."""
from __future__ import annotations

import json
from pathlib import Path
import zipfile

import pytest

from tests.platform_support import normalized_path, run_cli
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


@pytest.mark.parametrize(
    "legacy_content",
    [None, b"obsolete global settings must not be parsed or replaced\n"],
    ids=["no-global-config", "legacy-config-untouched"],
)
def test_cli_settings_stay_local_through_bundle_with_unicode_paths(
    tmp_path: Path,
    legacy_content: bytes | None,
) -> None:
    """Exercise the Windows CI storage contract on every supported platform."""
    environment = isolated_user_environment(tmp_path / "benutzer-ä")
    repository = create_repository(tmp_path / "repository-ä")
    legacy = legacy_user_configuration_path(environment)
    if legacy_content is not None:
        legacy.parent.mkdir(parents=True, exist_ok=True)
        legacy.write_bytes(legacy_content)

    registered = run_cli(repository, "register", environment_overrides=environment)
    assert registered.returncode == 0, registered.stderr
    local = repository / ".patchharbor" / "config.json"
    expected = {
        "format_version": 1,
        "exchange_directory": None,
        "bundle_suffix": "",
        "archive_directory": "PatchHarbor-Archive",
    }
    assert json.loads(local.read_text(encoding="utf-8")) == expected
    registry = legacy.with_name("registry.json")
    registry_bytes = registry.read_bytes()
    repo_id = (repository / ".patchharbor" / "id").read_text(encoding="utf-8").strip()
    registered_paths = json.loads(registry_bytes)["repositories"]
    assert set(registered_paths) == {repo_id}
    assert normalized_path(registered_paths[repo_id]) == normalized_path(repository)

    child = repository / "unterverzeichnis-ä"
    child.mkdir()
    exchange = tmp_path / "downloads-ä" / "exchange"
    for option, value, field, stored in (
        ("exchange-directory", str(exchange), "exchange_directory", str(exchange.resolve())),
        ("bundle-suffix", ".txt", "bundle_suffix", ".txt"),
        ("archive-dir", "Archive-Test", "archive_directory", "Archive-Test"),
    ):
        result = run_cli(
            child, "configure", option, value, environment_overrides=environment,
        )
        assert result.returncode == 0, result.stderr
        expected[field] = stored
        assert json.loads(local.read_text(encoding="utf-8")) == expected
        assert registry.read_bytes() == registry_bytes
        if legacy_content is None:
            assert not legacy.exists()
        else:
            assert legacy.read_bytes() == legacy_content

    context_result = run_cli(child, "context", "--json", environment_overrides=environment)
    assert context_result.returncode == 0, context_result.stderr
    context = json.loads(context_result.stdout)["result"]
    assert context["repo_id"] == repo_id
    assert normalized_path(context["repository_path"]) == normalized_path(repository)
    assert context["dirty"] is False

    bundled = run_cli(child, "bundle", "--json", environment_overrides=environment)
    assert bundled.returncode == 0, bundled.stderr
    bundle_path = Path(json.loads(bundled.stdout)["result"]["result_bundle_path"])
    assert normalized_path(bundle_path.parent) == normalized_path(exchange)
    assert bundle_path.name.endswith(".zip.txt")
    with zipfile.ZipFile(bundle_path) as archive:
        handoff = json.loads(archive.read("environment.json"))
        assert normalized_path(handoff["exchange_directory"]) == normalized_path(exchange)
        assert handoff["bundle_suffix"] == ".txt"
        assert handoff["repository_context"]["repo_id"] == repo_id
        assert not any(name.startswith("base/.patchharbor/") for name in archive.namelist())
    assert json.loads(local.read_text(encoding="utf-8")) == expected
    assert registry.read_bytes() == registry_bytes
    assert git(repository, "status", "--porcelain").stdout == ""
    assert not (repository / ".gitignore").exists()
    if legacy_content is None:
        assert not legacy.exists()
    else:
        assert legacy.read_bytes() == legacy_content
