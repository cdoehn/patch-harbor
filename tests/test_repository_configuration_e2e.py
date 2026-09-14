"""Local configuration ownership, shared Exchange routing and no-migration contracts."""
from __future__ import annotations

import json
import os
from pathlib import Path
import zipfile

import pytest

from patchharbor import api
from patchharbor import application
from patchharbor.user_paths import registration_user_paths
from tests.registration_support import create_repository, git, set_isolated_user_environment
from tests.test_api_e2e import write_package

pytestmark = pytest.mark.e2e


@pytest.fixture
def repos(tmp_path, monkeypatch):
    set_isolated_user_environment(monkeypatch, tmp_path / "user")
    a, b = (create_repository(tmp_path / name) for name in ("repo-a", "repo-b"))
    ca, cb = api.register(a), api.register(b)
    monkeypatch.chdir(a)
    return a, b, ca, cb


def _configured(repos, tmp_path, *, shared=False):
    a, b, ca, cb = repos
    ea = tmp_path / "exchange-a"
    eb = ea if shared else tmp_path / "exchange-b"
    api.configure_exchange_directory(ea, repository=a)
    api.configure_exchange_directory(eb, repository=b)
    return a, b, ca, cb, ea, eb


def _handoff(path):
    with zipfile.ZipFile(path) as archive:
        assert not any(name.startswith("base/.patchharbor/") for name in archive.namelist())
        return json.loads(archive.read("environment.json"))


def test_fresh_registration_creates_local_defaults_not_user_settings(repos):
    a, b, ca, cb = repos
    paths = registration_user_paths()
    assert not (paths.configuration_directory / "config.json").exists()
    for repo, context in ((a, ca), (b, cb)):
        settings = api.configuration(repo)
        assert settings.path == repo / ".patchharbor" / "config.json"
        assert settings.exchange_directory is None
        assert settings.bundle_suffix == ""
        assert settings.archive_directory == "PatchHarbor-Archive"
        assert (repo / ".patchharbor" / "id").read_text().strip() == str(context.repo_id)
        assert git(repo, "status", "--porcelain").stdout == ""
        assert not (repo / ".gitignore").exists()


@pytest.mark.parametrize("shared", [False, True])
def test_all_settings_are_independent_even_with_shared_exchange(repos, tmp_path, shared):
    a, b, _, _, ea, eb = _configured(repos, tmp_path, shared=shared)
    original_b = api.configuration(b).path.read_bytes()
    api.configure_bundle_suffix(".a", repository=a)
    api.configure_archive_directory("Archive-A", repository=a)
    assert api.configuration(b).path.read_bytes() == original_b
    api.configure_bundle_suffix(".b", repository=b)
    api.configure_archive_directory("", repository=b)
    ra, rb = api.bundle(a), api.bundle(b)
    assert ra.path.parent == ea and ra.path.name.endswith(".zip.a")
    assert rb.path.parent == eb and rb.path.name.endswith(".zip.b")
    assert _handoff(ra.path)["exchange_directory"] == str(ea)
    assert _handoff(rb.path)["exchange_directory"] == str(eb)
    assert api.configuration(a).archive_directory == "Archive-A"
    assert api.configuration(b).archive_directory == ""


@pytest.mark.parametrize("shared", [False, True])
def test_automatic_discovery_scans_each_physical_directory_once(repos, tmp_path, monkeypatch, shared):
    a, b, ca, cb, ea, eb = _configured(repos, tmp_path, shared=shared)
    write_package(ea / "a.zip", ca)
    write_package(eb / "b.zip", cb)
    os.utime(ea / "a.zip", ns=(1000000000, 1000000000))
    os.utime(eb / "b.zip", ns=(2000000000, 2000000000))
    scans = []
    scan = application.scan_exchange_directory
    def observed(directory, **kwargs):
        scans.append(directory)
        return scan(directory, **kwargs)
    monkeypatch.setattr(application, "scan_exchange_directory", observed)
    report = api.apply_next(dry_run=True)
    assert report.success, report.primary_result
    assert report.context.repo_id == cb.repo_id
    assert report.result_bundle.path.parent == eb
    assert sorted(scans) == sorted({ea, eb})


def test_physical_aliases_of_shared_exchange_are_deduplicated(repos, tmp_path, monkeypatch):
    from tests.platform_support import create_symlink_or_skip
    a, b, ca, cb = repos
    physical = tmp_path / "physical"
    physical.mkdir()
    alias = tmp_path / "alias"
    create_symlink_or_skip(alias, physical, target_is_directory=True)
    api.configure_exchange_directory(physical, repository=a)
    api.configure_exchange_directory(alias, repository=b)
    assert api.configuration(a).exchange_directory == api.configuration(b).exchange_directory == physical
    write_package(physical / "b.zip", cb)
    scans = []
    scan = application.scan_exchange_directory
    def observed(directory, **kwargs):
        scans.append(directory)
        return scan(directory, **kwargs)
    monkeypatch.setattr(application, "scan_exchange_directory", observed)
    assert api.apply_next(dry_run=True).success
    assert scans == [physical]


def test_automatic_discovery_never_routes_a_patch_from_the_wrong_exchange(repos, tmp_path):
    a, b, ca, cb, ea, eb = _configured(repos, tmp_path)
    wrong = ea / "newest-but-wrong.zip"
    right = eb / "correct.zip"
    write_package(wrong, cb)
    write_package(right, cb)
    os.utime(wrong, ns=(3000000000, 3000000000))
    os.utime(right, ns=(1000000000, 1000000000))
    selected = application.discover_exchange_patch(application._automatic_exchange_discovery_scope(), archive=False)
    assert selected.artifact.path == right
    assert selected.configuration_paths.repository.value == b
    right.unlink()
    report = api.apply_next(dry_run=True)
    assert not report.success
    assert report.primary_tool_error.kind is api.ErrorKind.PATCH_PACKAGE_ERROR
    assert wrong.exists()


@pytest.mark.parametrize("shared", [False, True])
def test_manual_subdirectory_is_local_but_explicit_apply_uses_manifest_target(repos, tmp_path, monkeypatch, shared):
    a, b, ca, cb, ea, eb = _configured(repos, tmp_path, shared=shared)
    api.configure_bundle_suffix(".A", repository=a)
    api.configure_bundle_suffix(".B", repository=b)
    write_package(ea / "a.zip", ca)
    write_package(eb / "b.zip", cb)
    (a / "subdir").mkdir()
    monkeypatch.chdir(a / "subdir")
    local = api.dry_run()
    assert local.success and local.context.repo_id == ca.repo_id
    assert local.result_bundle.path.parent == ea
    assert local.result_bundle.path.name.endswith(".zip.A")
    explicit = api.dry_run(eb / "b.zip")
    assert explicit.success and explicit.context.repo_id == cb.repo_id
    assert explicit.result_bundle.path.parent == eb
    assert explicit.result_bundle.path.name.endswith(".zip.B")
    assert _handoff(explicit.result_bundle.path)["repository_path"] == str(b)


def test_automatic_polls_reload_changed_local_exchange_and_suffix(repos, tmp_path):
    a, b, ca, cb, ea, eb = _configured(repos, tmp_path)
    write_package(ea / "first.zip", ca)
    first = api.apply_next(dry_run=True)
    assert first.success and first.result_bundle.path.parent == ea
    new = tmp_path / "new-exchange"
    api.configure_exchange_directory(new, repository=a)
    api.configure_bundle_suffix(".new", repository=a)
    idle = api.apply_next(dry_run=True)
    assert not idle.success  # old Exchange still contains the former patch
    write_package(new / "second.zip", ca)
    second = api.apply_next(dry_run=True)
    assert second.success and second.result_bundle.path.parent == new
    assert second.result_bundle.path.name.endswith(".zip.new")
    assert (ea / "first.zip").exists()


def test_unconfigured_repositories_do_not_block_configured_watcher_targets(repos, tmp_path):
    a, b, ca, cb = repos
    exchange = tmp_path / "exchange"
    api.configure_exchange_directory(exchange, repository=b)
    write_package(exchange / "b.zip", cb)
    report = api.apply_next(dry_run=True)
    assert report.success and report.context.repo_id == cb.repo_id
    local = api.dry_run(repository=a)
    assert not local.success
    assert api.configuration(a).exchange_directory is None


@pytest.mark.parametrize("damage", ["missing", "invalid"])
def test_corrupt_live_repository_configuration_stops_global_poll_without_repair(repos, tmp_path, damage):
    a, b, ca, cb, ea, eb = _configured(repos, tmp_path)
    write_package(eb / "b.zip", cb)
    config = api.configuration(a).path
    if damage == "missing":
        config.unlink()
    else:
        config.write_bytes(b"invalid")
    report = api.apply_next()
    assert not report.success and not report.execution_present
    assert not tuple(eb.glob("*_Result_*"))
    assert not config.exists() if damage == "missing" else config.read_bytes() == b"invalid"


def test_global_configuration_is_ignored_for_every_local_setting(repos, tmp_path):
    a, b, ca, cb, ea, eb = _configured(repos, tmp_path)
    legacy = registration_user_paths().configuration_directory / "config.json"
    old = json.dumps({"format_version": 3, "exchange_directory": str(tmp_path / "old"),
                      "bundle_suffix": ".legacy", "archive_directory": "Old"}).encode()
    legacy.write_bytes(old)
    api.configure_bundle_suffix(".local", repository=a)
    result = api.bundle(a)
    assert result.path.parent == ea and result.path.name.endswith(".zip.local")
    assert api.configuration(b).bundle_suffix == ""
    assert legacy.read_bytes() == old
    assert not (tmp_path / "old").exists()


def test_unregister_and_reregister_preserve_identity_and_all_local_settings(repos, tmp_path):
    a, b, ca, cb, ea, eb = _configured(repos, tmp_path)
    api.configure_bundle_suffix(".keep", repository=a)
    api.configure_archive_directory("Keep", repository=a)
    cfg = api.configuration(a)
    before = cfg.path.read_bytes()
    api.unregister(ca.repo_id)
    assert cfg.path.read_bytes() == before
    with pytest.raises(api.PatchHarborError):
        api.configure_exchange_directory(tmp_path / "forbidden", repository=a)
    assert not (tmp_path / "forbidden").exists()
    after = api.register(a)
    assert after.repo_id == ca.repo_id
    assert cfg.path.read_bytes() == before
    assert api.configuration(a) == cfg


def test_moving_local_repository_updates_registry_and_preserves_settings(repos, tmp_path):
    a, b, ca, cb, ea, eb = _configured(repos, tmp_path)
    cfg = api.configuration(b)
    original = cfg.path.read_bytes()
    moved = tmp_path / "relocated"
    b.rename(moved)
    registered = api.register(moved)
    assert registered.repo_id == cb.repo_id
    assert api.configuration(moved).path.read_bytes() == original
    assert api.configuration(moved).exchange_directory == eb
    assert api.context(moved).repository_path.value == moved


def test_fresh_clone_has_no_local_config_and_requires_explicit_setup(repos, tmp_path):
    a, b, ca, cb, ea, eb = _configured(repos, tmp_path)
    clone = tmp_path / "clone"
    git(tmp_path, "clone", "--quiet", str(a), str(clone))
    assert not (clone / ".patchharbor").exists()
    context = api.register(clone)
    assert context.repo_id != ca.repo_id
    assert api.configuration(clone).exchange_directory is None
    assert not api.dry_run(repository=clone).success
    api.configure_exchange_directory(ea, repository=clone)
    assert api.configuration(clone).exchange_directory == ea


@pytest.mark.parametrize("damage", ["missing", "invalid"])
def test_reregister_retained_metadata_never_repairs_config(repos, damage):
    a, b, ca, cb = repos
    cfg = api.configuration(b).path
    api.unregister(cb.repo_id)
    if damage == "missing":
        cfg.unlink()
    else:
        cfg.write_bytes(b"invalid")
    with pytest.raises(api.PatchHarborError):
        api.register(b)
    assert not cfg.exists() if damage == "missing" else cfg.read_bytes() == b"invalid"
    assert all(row.repo_id != cb.repo_id for row in api.repositories().repositories)


def test_explicit_output_works_before_exchange_but_not_without_local_config(repos, tmp_path):
    a, b, ca, cb = repos
    api.configure_bundle_suffix(".manual", repository=b)
    output = tmp_path / "output"
    result = api.bundle(b, output_directory=output)
    assert result.path.parent == output and result.path.name.endswith(".zip.manual")
    assert _handoff(result.path)["exchange_directory"] is None
    assert api.configuration(b).exchange_directory is None


def test_user_can_manually_initialize_old_repository_without_migration(repos, tmp_path):
    a, b, ca, cb = repos
    local = api.configuration(b).path
    seed = local.read_bytes()
    local.unlink()
    legacy = registration_user_paths().configuration_directory / "config.json"
    legacy.write_bytes(b"this global file must never be used")
    for call in (lambda: api.register(b), lambda: api.configure_exchange_directory(tmp_path / "exchange", repository=b)):
        with pytest.raises(api.PatchHarborError):
            call()
        assert not local.exists()
    # Explicit user action, not product migration or repair.
    local.write_bytes(seed)
    assert api.register(b).repo_id == cb.repo_id
    api.configure_exchange_directory(tmp_path / "exchange", repository=b)
    assert api.configuration(b).exchange_directory == tmp_path / "exchange"
    assert legacy.read_bytes() == b"this global file must never be used"


@pytest.mark.parametrize("shared", [False, True])
def test_archive_maintenance_uses_each_repositorys_own_child_directory(repos, tmp_path, shared):
    a, b, ca, cb, ea, eb = _configured(repos, tmp_path, shared=shared)
    api.configure_archive_directory("Archive-A", repository=a)
    api.configure_archive_directory("Archive-B", repository=b)
    old_a, old_b = api.bundle(a).path, api.bundle(b).path
    raw_a, raw_b = old_a.read_bytes(), old_b.read_bytes()
    git(a, "commit", "--allow-empty", "-m", "advance-a")
    git(b, "commit", "--allow-empty", "-m", "advance-b")
    report = api.apply_next()
    assert not report.success and not report.execution_present
    assert not old_a.exists() and not old_b.exists()
    assert (ea / "Archive-A" / old_a.name).read_bytes() == raw_a
    assert (eb / "Archive-B" / old_b.name).read_bytes() == raw_b
    assert not (ea / "Archive-A" / old_b.name).exists()
    assert not (eb / "Archive-B" / old_a.name).exists()
