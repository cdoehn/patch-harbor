"""Execute setup workflows; do not assert README, help or console wording."""
from __future__ import annotations

import json
from pathlib import Path
import zipfile

import pytest

from patchharbor import api
from patchharbor.user_paths import registration_user_paths
from tests.platform_support import run_cli
from tests.registration_support import (
    create_repository, git, local_exclude_path, set_isolated_user_environment,
)

pytestmark = [pytest.mark.e2e, pytest.mark.acceptance]


@pytest.fixture
def repository(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    set_isolated_user_environment(monkeypatch, tmp_path / "user")
    return create_repository(tmp_path / "repository")


def test_register_configure_bundle_workflow_from_subdirectory(repository, tmp_path):
    registered = run_cli(repository, "register")
    assert registered.returncode == 0, registered.stderr
    context = api.context(repository)
    config = api.configuration(repository)
    assert config.exchange_directory is None
    assert config.path == repository / ".patchharbor" / "config.json"
    assert not (repository / ".gitignore").exists()
    assert git(repository, "check-ignore", ".patchharbor/config.json").returncode == 0
    assert git(repository, "status", "--porcelain").stdout == ""
    assert run_cli(repository, "configure", "show").returncode == 0
    # A valid unset configuration is not sufficient for default publication.
    assert run_cli(repository, "bundle", "--json").returncode != 0
    nested = repository / "nested"
    nested.mkdir()
    exchange = tmp_path / "exchange"
    for arguments in (
        ("bundle-suffix", ".txt"), ("archive-dir", "Archive-A"),
        ("exchange-directory", str(exchange)),
    ):
        changed = run_cli(nested, "configure", *arguments)
        assert changed.returncode == 0, changed.stderr
    result = run_cli(nested, "bundle", "--json")
    assert result.returncode == 0, result.stderr
    bundle = Path(json.loads(result.stdout)["result"]["result_bundle_path"])
    assert bundle.parent == exchange and bundle.name.endswith(".zip.txt")
    with zipfile.ZipFile(bundle) as archive:
        environment = json.loads(archive.read("environment.json"))
        assert environment["repository_context"]["repo_id"] == str(context.repo_id)
        assert environment["exchange_directory"] == str(exchange)
        assert environment["output_directory"] == str(exchange)
        assert not any(".patchharbor" in Path(name).parts for name in archive.namelist())
    assert api.context(repository) == context


@pytest.mark.parametrize("shared", [False, True])
def test_cli_configuration_of_another_repository_is_independent(repository, tmp_path, shared):
    other = create_repository(tmp_path / "other")
    api.register(repository)
    api.register(other)
    first = tmp_path / "exchange-a"
    second = first if shared else tmp_path / "exchange-b"
    for repo, exchange in ((repository, first), (other, second)):
        assert run_cli(repo, "configure", "exchange-directory", str(exchange)).returncode == 0
    before = api.configuration(other).path.read_bytes()
    assert run_cli(repository, "configure", "bundle-suffix", ".A").returncode == 0
    assert run_cli(repository, "configure", "archive-dir", "Archive-A").returncode == 0
    assert api.configuration(other).path.read_bytes() == before
    assert api.configuration(repository).bundle_suffix == ".A"
    assert api.configuration(repository).archive_directory == "Archive-A"
    assert not (registration_user_paths().configuration_directory / "config.json").exists()


@pytest.mark.parametrize("location", ["outside", "unregistered"])
def test_configure_never_initializes_repository_metadata(repository, tmp_path, location):
    cwd = tmp_path if location == "outside" else repository
    target = tmp_path / "must-not-be-created"
    for arguments in (
        ("show",), ("exchange-directory", str(target)),
        ("bundle-suffix", ".txt"), ("archive-dir", "Archive"),
    ):
        assert run_cli(cwd, "configure", *arguments).returncode != 0
    assert not target.exists()
    assert not (cwd / ".patchharbor").exists()


@pytest.mark.parametrize("damage", ["missing", "invalid"])
def test_register_and_configure_do_not_repair_existing_metadata(repository, tmp_path, damage):
    original = api.register(repository)
    paths = registration_user_paths()
    registry_bytes = paths.registry_path.read_bytes()
    config = api.configuration(repository).path
    id_bytes = config.with_name("id").read_bytes()
    exclude_bytes = local_exclude_path(repository).read_bytes()
    if damage == "missing":
        config.unlink()
    else:
        config.write_bytes(b"not-json")
    target = tmp_path / "must-not-be-created"
    for command in (
        ("register",), ("register", "--new-id"),
        ("configure", "show"), ("configure", "exchange-directory", str(target)),
    ):
        assert run_cli(repository, *command).returncode != 0
        assert (not config.exists()) if damage == "missing" else config.read_bytes() == b"not-json"
        assert config.with_name("id").read_bytes() == id_bytes
        assert local_exclude_path(repository).read_bytes() == exclude_bytes
        assert paths.registry_path.read_bytes() == registry_bytes
    assert not target.exists()
    assert str(original.repo_id).encode() in id_bytes


def test_existing_registration_can_be_set_up_manually_without_global_import(repository, tmp_path):
    original = api.register(repository)
    paths = registration_user_paths()
    legacy = paths.configuration_directory / "config.json"
    old = json.dumps({"format_version": 3, "exchange_directory": str(tmp_path / "old"),
                      "bundle_suffix": ".old", "archive_directory": "Old"}).encode()
    legacy.write_bytes(old)
    local = api.configuration(repository).path
    local.unlink()  # simulate an existing registration from the old implementation
    exchange = tmp_path / "new"
    assert run_cli(repository, "configure", "exchange-directory", str(exchange)).returncode != 0
    assert not exchange.exists() and not local.exists()
    # Deliberate file creation represents the user's editor, not application migration.
    local.write_text(json.dumps({"format_version": 1, "exchange_directory": None,
                                "bundle_suffix": "", "archive_directory": "PatchHarbor-Archive"}) + "\n",
                     encoding="utf-8")
    assert run_cli(repository, "configure", "exchange-directory", str(exchange)).returncode == 0
    assert api.configuration(repository).bundle_suffix == ""
    assert api.configuration(repository).archive_directory == "PatchHarbor-Archive"
    assert api.context(repository) == original
    assert legacy.read_bytes() == old
    assert not (tmp_path / "old").exists()


def test_unregister_reregister_and_real_move_keep_local_preferences(repository, tmp_path):
    original = api.register(repository)
    api.configure_exchange_directory(tmp_path / "exchange", repository=repository)
    api.configure_bundle_suffix(".keep", repository=repository)
    local = api.configuration(repository).path
    config_bytes = local.read_bytes()
    id_bytes = local.with_name("id").read_bytes()
    exclude_bytes = local_exclude_path(repository).read_bytes()
    assert run_cli(repository, "unregister", str(original.repo_id)).returncode == 0
    assert api.repositories().repositories == ()
    assert local.read_bytes() == config_bytes
    assert local.with_name("id").read_bytes() == id_bytes
    assert local_exclude_path(repository).read_bytes() == exclude_bytes
    assert run_cli(repository, "register").returncode == 0
    moved = tmp_path / "moved"
    repository.rename(moved)
    assert run_cli(moved, "register").returncode == 0
    assert api.context(moved).repo_id == original.repo_id
    assert api.configuration(moved).path.read_bytes() == config_bytes
    mappings = api.repositories().repositories
    assert len(mappings) == 1 and mappings[0].repository_path.value == moved


def test_git_clone_needs_fresh_identity_and_exchange_setup(repository, tmp_path):
    original = api.register(repository)
    api.configure_exchange_directory(tmp_path / "exchange", repository=repository)
    api.configure_bundle_suffix(".not-inherited", repository=repository)
    clone = tmp_path / "clone"
    git(tmp_path, "clone", "--quiet", str(repository), str(clone))
    assert not (clone / ".patchharbor").exists()
    assert run_cli(clone, "configure", "show").returncode != 0
    assert run_cli(clone, "register").returncode == 0
    assert api.context(clone).repo_id != original.repo_id
    assert api.configuration(clone).exchange_directory is None
    assert api.configuration(clone).bundle_suffix == ""
    assert run_cli(clone, "configure", "exchange-directory", str(tmp_path / "clone-exchange")).returncode == 0
    assert api.configuration(repository).bundle_suffix == ".not-inherited"
