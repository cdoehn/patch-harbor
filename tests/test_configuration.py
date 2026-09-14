"""Repository-local persistence and safety contracts (no presentation tests)."""
from __future__ import annotations

import errno
import json
from pathlib import Path

import pytest

from patchharbor import api
from patchharbor.configuration import (
    RepositoryConfiguration, RepositoryConfigurationPaths, load_configuration,
    write_exchange_directory,
)
from patchharbor.errors import ErrorKind, PatchHarborError
from patchharbor.registry import load_registry
from patchharbor.user_paths import registration_user_paths
from tests.platform_support import project_environment
from tests.registration_support import (
    create_repository, probe_registry_lock, probe_repository_lock,
    set_isolated_user_environment,
)


@pytest.fixture
def local(tmp_path, monkeypatch):
    set_isolated_user_environment(monkeypatch, tmp_path / "user")
    repo = create_repository(tmp_path / "repo")
    context = api.register(repo)
    monkeypatch.chdir(repo)
    return RepositoryConfigurationPaths(context.repository_path, context.repo_id)


def document(exchange=None, **changes):
    return {"format_version": 1, "exchange_directory": exchange,
            "bundle_suffix": "", "archive_directory": "PatchHarbor-Archive", **changes}


def test_registration_initializes_local_defaults_without_exchange(local):
    assert load_configuration(local) == RepositoryConfiguration()
    assert json.loads(local.configuration_path.read_bytes()) == document()
    assert not (registration_user_paths().configuration_directory / "config.json").exists()


def test_settings_round_trip_with_exact_new_schema(local, tmp_path):
    first = tmp_path / "first" / "exchange"
    assert write_exchange_directory(local, first) == RepositoryConfiguration(first.resolve())
    persisted = local.configuration_path.read_bytes()
    assert json.loads(persisted) == document(str(first.resolve()))
    assert persisted.endswith(b"\n")
    second = tmp_path / "second"
    second.mkdir()
    local.configuration_path.write_text(json.dumps(document(str(second))))
    assert load_configuration(local).exchange_directory == second.resolve()
    assert not list(local.configuration_directory.glob(".patchharbor-*.tmp"))


def test_physical_exchange_alias_is_canonicalized(local, tmp_path):
    physical = tmp_path / "physical"
    physical.mkdir()
    alias = tmp_path / "alias"
    try:
        alias.symlink_to(physical, target_is_directory=True)
    except OSError as exc:
        pytest.skip(f"symlinks unavailable: {exc}")
    assert write_exchange_directory(local, alias).exchange_directory == physical.resolve()
    local.configuration_path.write_text(json.dumps(document(str(alias))))
    assert load_configuration(local).exchange_directory == physical.resolve()


@pytest.mark.parametrize("value", [
    {}, {"format_version": 1}, {"format_version": 1, "exchange_directory": "/old"},
    document(future=True), document(format_version=True), document(format_version=1.0),
    document(format_version=2), document(format_version=3), document(exchange_directory=7),
    document(exchange_directory=""), document(exchange_directory="relative"),
    document(exchange_directory="/bad\x00path"), document(bundle_suffix="../x"),
    document(archive_directory="../archive"), document(archive_directory=None),
])
def test_invalid_schema_is_never_rewritten(local, tmp_path, value):
    original = json.dumps(value).encode()
    local.configuration_path.write_bytes(original)
    candidate = tmp_path / "not-created"
    for operation in (lambda: load_configuration(local),
                      lambda: api.configure_exchange_directory(candidate),
                      lambda: api.register(local.repository.value)):
        with pytest.raises(PatchHarborError):
            operation()
        assert local.configuration_path.read_bytes() == original
    assert not candidate.exists()


@pytest.mark.parametrize("content", [
    b"\xef\xbb\xbf{}", b"\xff", b"[]", b'{"format_version":1,"format_version":1}',
    b'{"format_version":NaN}', b'{"format_version":1}{}', b"{broken",
])
def test_ambiguous_json_is_rejected_without_repair(local, content):
    local.configuration_path.write_bytes(content)
    with pytest.raises(PatchHarborError) as caught:
        load_configuration(local)
    assert caught.value.error_kind is ErrorKind.CONFIGURATION_ERROR
    assert local.configuration_path.read_bytes() == content


def test_direct_exchange_requires_existing_directory(local, tmp_path):
    missing = tmp_path / "missing"
    local.configuration_path.write_text(json.dumps(document(str(missing))))
    with pytest.raises(PatchHarborError):
        load_configuration(local)
    assert not missing.exists()
    missing.write_text("file")
    with pytest.raises(PatchHarborError):
        load_configuration(local)
    assert missing.read_text() == "file"


def test_relative_update_preserves_config_and_does_not_create_directory(local):
    before = local.configuration_path.read_bytes()
    with pytest.raises(PatchHarborError):
        write_exchange_directory(local, Path("relative"))
    assert local.configuration_path.read_bytes() == before
    assert not Path("relative").exists()


def test_missing_config_is_not_recreated_by_any_update(local, tmp_path):
    local.configuration_path.unlink()
    for operation in (lambda: api.configure_exchange_directory(tmp_path / "exchange"),
                      lambda: api.configure_bundle_suffix(".txt"),
                      lambda: api.configure_archive_directory("Archive"),
                      lambda: api.configuration(), lambda: api.register(local.repository.value)):
        with pytest.raises(PatchHarborError):
            operation()
        assert not local.configuration_path.exists()
    assert not (tmp_path / "exchange").exists()


def test_nonregular_config_rejected_before_exchange_creation(local, tmp_path):
    local.configuration_path.unlink()
    local.configuration_path.mkdir()
    with pytest.raises(PatchHarborError):
        write_exchange_directory(local, tmp_path / "not-created")
    assert not (tmp_path / "not-created").exists()


def test_atomic_replace_failure_preserves_previous_bytes(local, tmp_path, monkeypatch):
    import patchharbor.platform.filesystem as filesystem
    write_exchange_directory(local, tmp_path / "first")
    before = local.configuration_path.read_bytes()
    def reject(*args):
        raise OSError(errno.EACCES, "native wording")
    monkeypatch.setattr(filesystem.os, "replace", reject)
    with pytest.raises(PatchHarborError) as caught:
        write_exchange_directory(local, tmp_path / "second")
    assert caught.value.error_kind is ErrorKind.CONFIGURATION_ERROR
    assert local.configuration_path.read_bytes() == before
    assert not list(local.configuration_directory.glob(".patchharbor-*.tmp"))


def test_configure_holds_both_locks_through_publication(local, tmp_path, monkeypatch):
    import patchharbor.application as application
    original = application.write_prepared_configuration
    calls = []
    def publish(paths, settings):
        env = project_environment()
        assert probe_registry_lock(env) != 0
        assert probe_repository_lock(str(local.repo_id), env) != 0
        calls.append(paths)
        return original(paths, settings)
    monkeypatch.setattr(application, "write_prepared_configuration", publish)
    api.configure_exchange_directory(tmp_path / "exchange")
    assert calls == [local]


def test_registry_change_during_update_is_rejected(local, tmp_path, monkeypatch):
    import patchharbor.application as application
    from patchharbor.registry import registry_snapshot
    original = application.load_registry
    count = 0
    def changing(paths):
        nonlocal count
        count += 1
        return original(paths) if count == 1 else registry_snapshot({})
    before = local.configuration_path.read_bytes()
    monkeypatch.setattr(application, "load_registry", changing)
    with pytest.raises(PatchHarborError) as caught:
        api.configure_exchange_directory(tmp_path / "exchange")
    assert caught.value.error_kind is ErrorKind.REGISTRY_ERROR
    assert local.configuration_path.read_bytes() == before


def test_global_config_path_is_not_exposed_by_user_paths(local):
    assert not hasattr(registration_user_paths(), "configuration_path")
