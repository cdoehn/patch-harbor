"""Real configuration, scoped discovery, replay and technical lock contracts."""
from __future__ import annotations

from dataclasses import FrozenInstanceError, replace
from contextlib import contextmanager
import json
import os
from pathlib import Path
import shutil

import pytest

from patchharbor import api, application
from patchharbor import exchange_state
from patchharbor.errors import configuration_error, patch_package_error
from patchharbor.locks import registry_lock, repository_lock
from patchharbor.user_paths import registration_user_paths
from tests.platform_support import create_symlink_or_skip, project_environment
from tests.registration_support import (
    create_repository, set_isolated_user_environment,
    start_repository_lock_holder, release_repository_lock_holder, stop_repository_lock_holder,
)
from tests.test_api_e2e import write_package

pytestmark = pytest.mark.e2e


@pytest.fixture
def pair(tmp_path, monkeypatch):
    set_isolated_user_environment(monkeypatch, tmp_path / "user")
    roots = tuple(create_repository(tmp_path / name) for name in ("repo-a", "repo-b"))
    contexts = tuple(api.register(root) for root in roots)
    exchanges = tuple(tmp_path / name for name in ("exchange-a", "exchange-b"))
    for root, exchange in zip(roots, exchanges):
        api.configure_exchange_directory(exchange, repository=root)
    return roots, contexts, exchanges


def forbid_bundle_work(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("watch/readiness query performed bundle or repository-state work")
    for name in ("scan_exchange_directory", "materialize_exchange_patch",
                 "recover_exchange_artifacts", "archive_exchange_artifacts",
                 "capture_repository_context_for_id", "capture_consistent_repository_snapshot"):
        monkeypatch.setattr(application, name, forbidden)
    monkeypatch.setattr(exchange_state, "load_exchange_state", forbidden)


def test_targets_are_immutable_and_queries_do_not_scan_or_hash(pair, monkeypatch):
    roots, contexts, exchanges = pair
    for exchange in exchanges:
        (exchange / "incomplete.zip").write_bytes(b"PK still downloading")
    forbid_bundle_work(monkeypatch)
    targets = api.watch_targets()
    assert targets.registry_path == registration_user_paths().registry_path
    assert targets.configuration_paths == tuple(root / ".patchharbor/config.json" for root in roots)
    assert tuple(target.directory for target in targets.exchanges) == exchanges
    for target, context in zip(targets.exchanges, contexts):
        assert target.repository_ids == (context.repo_id,)
        assert (target.device, target.inode) == (target.directory.stat().st_dev, target.directory.stat().st_ino)
        with pytest.raises(FrozenInstanceError):
            target.inode = 1
    controls = api.watch_control_paths()
    assert controls.configuration_paths == targets.configuration_paths


def test_unset_and_missing_repositories_retain_control_paths(pair):
    roots, _, exchanges = pair
    local = roots[0] / ".patchharbor/config.json"
    configuration = json.loads(local.read_text())
    configuration["exchange_directory"] = None
    local.write_text(json.dumps(configuration))
    roots[1].rename(roots[1].with_name("temporarily-missing"))
    targets = api.watch_targets()
    assert targets.exchanges == ()
    assert targets.configuration_paths == tuple(root / ".patchharbor/config.json" for root in roots)
    assert all(exchange.is_dir() for exchange in exchanges)


def test_physical_aliases_are_one_target_with_all_owners(pair, tmp_path):
    roots, contexts, exchanges = pair
    alias = tmp_path / "alias"
    create_symlink_or_skip(alias, exchanges[0], target_is_directory=True)
    api.configure_exchange_directory(alias, repository=roots[1])
    targets = api.watch_targets().exchanges
    assert len(targets) == 1
    assert targets[0].directory == exchanges[0]
    assert targets[0].repository_ids == tuple(sorted(context.repo_id for context in contexts))


@pytest.mark.parametrize("damage", ["config", "missing_config", "identity", "missing_exchange"])
def test_invalid_live_configuration_fails_closed_but_controls_remain_readable(pair, damage):
    roots, _, exchanges = pair
    if damage == "config":
        (roots[1] / ".patchharbor/config.json").write_text("invalid")
    elif damage == "missing_config":
        (roots[1] / ".patchharbor/config.json").unlink()
    elif damage == "identity":
        (roots[1] / ".patchharbor/id").write_text(str(api.RepositoryId.new()) + "\n")
    else:
        exchanges[1].rmdir()
    with pytest.raises(api.PatchHarborError):
        api.watch_targets()
    assert roots[1] / ".patchharbor/config.json" in api.watch_control_paths().configuration_paths


def test_scoped_apply_never_scans_hashes_or_maintains_other_exchange(pair, monkeypatch):
    _, contexts, exchanges = pair
    write_package(exchanges[0] / "ready.zip", contexts[0])
    downloading = exchanges[1] / "download.zip"
    downloading.write_bytes(b"partial")
    original = downloading.read_bytes()
    target = api.watch_targets().exchanges[0]
    scanned, maintained = [], []
    scan = application.scan_exchange_directory
    archive = application.archive_exchange_artifacts
    recover = application.recover_exchange_artifacts

    def scan_a(directory, **kwargs):
        assert directory == exchanges[0]
        scanned.append(directory)
        return scan(directory, **kwargs)

    def maintain_a(function, artifacts, **kwargs):
        assert kwargs["configuration"].exchange_directory == exchanges[0]
        assert kwargs["repository_id"] == contexts[0].repo_id
        maintained.append(kwargs["repository_id"])
        return function(artifacts, **kwargs)

    monkeypatch.setattr(application, "scan_exchange_directory", scan_a)
    monkeypatch.setattr(application, "archive_exchange_artifacts", lambda a, **kw: maintain_a(archive, a, **kw))
    monkeypatch.setattr(application, "recover_exchange_artifacts", lambda a, **kw: maintain_a(recover, a, **kw))
    report = api.apply_next(exchanges=(target,))
    assert report.success
    assert report.automatic.status is api.AutomaticApplyStatus.ATTEMPTED
    assert scanned == [exchanges[0]] and maintained == [contexts[0].repo_id] * 2
    assert downloading.read_bytes() == original
    assert set(exchanges[1].iterdir()) == {downloading}


def test_empty_scope_never_becomes_global(pair, monkeypatch):
    _, contexts, exchanges = pair
    write_package(exchanges[0] / "ready.zip", contexts[0])
    forbid_bundle_work(monkeypatch)
    report = api.apply_next(exchanges=())
    assert not report.success
    assert report.automatic.status is api.AutomaticApplyStatus.NO_CANDIDATE


@pytest.mark.parametrize("change", ["foreign", "inode", "owner", "reconfigured", "replaced", "removed"])
def test_stale_or_foreign_target_fails_before_any_scan(pair, tmp_path, monkeypatch, change):
    roots, _, exchanges = pair
    target = api.watch_targets().exchanges[0]
    if change == "foreign":
        foreign = tmp_path / "foreign"
        foreign.mkdir()
        target = replace(target, directory=foreign)
    elif change == "inode":
        target = replace(target, inode=target.inode + 1)
    elif change == "owner":
        target = replace(target, repository_ids=(api.RepositoryId.new(),))
    elif change == "reconfigured":
        api.configure_exchange_directory(tmp_path / "new", repository=roots[0])
    else:
        exchanges[0].rename(tmp_path / "old-root")
        if change == "replaced":
            exchanges[0].mkdir()
    forbid_bundle_work(monkeypatch)
    report = api.apply_next(exchanges=(target,))
    assert not report.success
    assert report.automatic.status is api.AutomaticApplyStatus.ERROR
    assert report.primary_tool_error.kind is api.ErrorKind.CONFIGURATION_ERROR


def test_new_shared_owner_invalidates_previous_scope(pair, monkeypatch):
    roots, _, exchanges = pair
    target = api.watch_targets().exchanges[0]
    api.configure_exchange_directory(exchanges[0], repository=roots[1])
    forbid_bundle_work(monkeypatch)
    assert api.apply_next(exchanges=(target,)).automatic.status is api.AutomaticApplyStatus.ERROR


@pytest.mark.parametrize("boundary", ["before_replay", "during_identity_read"])
def test_root_replacement_between_selection_and_mutation_is_rejected(pair, tmp_path, monkeypatch, boundary):
    _, contexts, exchanges = pair
    target = api.watch_targets().exchanges[0]
    write_package(exchanges[0] / "ready.zip", contexts[0])
    apply_package = application.apply_patch_package

    def replace_root():
        moved = tmp_path / "old-root"
        exchanges[0].rename(moved)
        shutil.copytree(moved, exchanges[0])

    if boundary == "before_replay":
        def compete(package, **kwargs):
            replace_root()
            return apply_package(package, **kwargs)
        monkeypatch.setattr(application, "apply_patch_package", compete)
    else:
        read_identity = application.require_exchange_identity_unchanged
        def compete(identity, **kwargs):
            read_identity(identity, **kwargs)
            replace_root()
        monkeypatch.setattr(application, "require_exchange_identity_unchanged", compete)
    report = api.apply_next(exchanges=(target,))
    assert not report.success and not report.execution_present
    assert report.automatic.status is api.AutomaticApplyStatus.ERROR
    records = exchange_state.load_exchange_state(registration_user_paths()).records
    assert records and all(record.apply_status is None and record.attempt_run_id is None for record in records)


def test_default_global_selection_and_scoped_dry_run_keep_existing_contract(pair):
    _, contexts, exchanges = pair
    for index, (exchange, context) in enumerate(zip(exchanges, contexts)):
        path = exchange / "ready.zip"
        write_package(path, context)
        os.utime(path, ns=((index + 1) * 1000000000,) * 2)
    global_report = api.apply_next(dry_run=True)
    assert global_report.success and global_report.repo_id == contexts[1].repo_id
    assert global_report.automatic.status is api.AutomaticApplyStatus.DRY_RUN
    target = api.watch_targets().exchanges[0]
    scoped = api.apply_next(dry_run=True, exchanges=(target, target))
    assert scoped.success and scoped.repo_id == contexts[0].repo_id
    assert scoped.automatic.status is api.AutomaticApplyStatus.DRY_RUN
    records = exchange_state.load_exchange_state(registration_user_paths()).records
    assert records and all(record.apply_status is None and record.attempt_run_id is None for record in records)
    assert "automatic" not in scoped.apply_json_envelope()


@pytest.mark.parametrize("exit_code", [0, 7])
def test_actual_attempt_progress_does_not_allow_automatic_retry(pair, exit_code):
    _, contexts, exchanges = pair
    target = api.watch_targets().exchanges[0]
    path = exchanges[0] / "candidate.zip"
    write_package(path, contexts[0], exit_code=exit_code)
    first = api.apply_next(exchanges=(target,))
    assert first.automatic.status is api.AutomaticApplyStatus.ATTEMPTED
    assert first.success is (exit_code == 0)
    second = api.apply_next(exchanges=(target,))
    assert second.automatic.status is api.AutomaticApplyStatus.NO_CANDIDATE
    assert not second.execution_present
    if exit_code:
        manual = api.apply(path)
        assert manual.execution_present and manual.automatic is None


@pytest.mark.parametrize("factory", [configuration_error, patch_package_error])
def test_error_text_cannot_impersonate_empty_discovery(pair, monkeypatch, factory):
    def fail(*args, **kwargs):
        raise factory("no state-bound patch package matches a registered repository")
    monkeypatch.setattr(application, "discover_exchange_patch", fail)
    assert api.apply_next().automatic.status is api.AutomaticApplyStatus.ERROR


@pytest.mark.parametrize("kind", list(api.ApplyLockKind))
def test_lock_readiness_has_no_bundle_work_and_releases_every_lock(pair, monkeypatch, kind):
    _, contexts, _ = pair
    paths = registration_user_paths()
    lock = api.ApplyLock(kind, contexts[0].repo_id if kind is api.ApplyLockKind.REPOSITORY else None)
    acquire = {
        api.ApplyLockKind.REGISTRY: lambda: registry_lock(paths),
        api.ApplyLockKind.REPOSITORY: lambda: repository_lock(paths, contexts[0].repo_id),
        api.ApplyLockKind.EXCHANGE_STATE: lambda: exchange_state._state_lock(paths),
    }[kind]
    forbid_bundle_work(monkeypatch)
    with acquire():
        assert api.apply_readiness(lock) == api.ApplyReadiness(blocked_on=lock)
    assert api.apply_readiness(lock).ready
    with acquire():
        pass  # Readiness returned no reservation, including its registry probe.
    with registry_lock(paths):
        pass


def test_repository_lock_retry_uses_real_other_process_and_scoped_apply(pair):
    _, contexts, exchanges = pair
    target = api.watch_targets().exchanges[0]
    write_package(exchanges[0] / "ready.zip", contexts[0])
    holder = start_repository_lock_holder(str(contexts[0].repo_id), environment=project_environment())
    try:
        locked = api.apply_next(exchanges=(target,))
        assert locked.automatic.status is api.AutomaticApplyStatus.LOCKED
        lock = locked.automatic.blocked_on
        assert lock == api.ApplyLock(api.ApplyLockKind.REPOSITORY, contexts[0].repo_id)
        assert not api.apply_readiness(lock).ready
    finally:
        try:
            assert release_repository_lock_holder(holder) == 0
        finally:
            stop_repository_lock_holder(holder)
    assert api.apply_readiness(lock).ready
    assert api.apply_next(exchanges=(target,)).success


@pytest.mark.parametrize("kind", [api.ApplyLockKind.REGISTRY, api.ApplyLockKind.EXCHANGE_STATE])
def test_automatic_global_lock_conflicts_are_structured(pair, kind):
    paths = registration_user_paths()
    acquire = registry_lock if kind is api.ApplyLockKind.REGISTRY else exchange_state._state_lock
    with acquire(paths):
        report = api.apply_next()
    assert report.automatic == api.AutomaticApplyResult(
        api.AutomaticApplyStatus.LOCKED, api.ApplyLock(kind),
    )


def test_readiness_rejects_unregistered_repository(pair):
    with pytest.raises(api.PatchHarborError) as caught:
        api.apply_readiness(api.ApplyLock(api.ApplyLockKind.REPOSITORY, api.RepositoryId.new()))
    assert caught.value.error_kind is api.ErrorKind.REPOSITORY_RESOLUTION_ERROR
    with registry_lock(registration_user_paths()):
        pass


def test_lock_operation_failure_is_not_busy(pair, monkeypatch):
    from patchharbor.platform.locking import LockOperationError
    import patchharbor.locks as locks
    @contextmanager
    def fail(*args, **kwargs):
        raise LockOperationError("open", PermissionError("denied"))
        yield  # pragma: no cover - context manager fails while entering
    monkeypatch.setattr(locks, "exclusive_file_lock", fail)
    with pytest.raises(api.PatchHarborError) as caught:
        api.apply_readiness(api.ApplyLock(api.ApplyLockKind.REGISTRY))
    assert caught.value.error_kind is api.ErrorKind.REGISTRY_ERROR
    assert api.apply_next().automatic.status is api.AutomaticApplyStatus.ERROR


def test_lock_conflict_at_replay_boundary_survives_result_error_wrapping(pair, monkeypatch):
    _, contexts, exchanges = pair
    target = api.watch_targets().exchanges[0]
    write_package(exchanges[0] / "ready.zip", contexts[0])
    original = application.apply_patch_package
    def compete(package, **kwargs):
        with exchange_state._state_lock(registration_user_paths()):
            return original(package, **kwargs)
    monkeypatch.setattr(application, "apply_patch_package", compete)
    report = api.apply_next(exchanges=(target,))
    assert not report.execution_present
    assert report.automatic == api.AutomaticApplyResult(
        api.AutomaticApplyStatus.LOCKED, api.ApplyLock(api.ApplyLockKind.EXCHANGE_STATE),
    )
    records = exchange_state.load_exchange_state(registration_user_paths()).records
    assert all(record.apply_status is None for record in records)
    monkeypatch.setattr(application, "apply_patch_package", original)
    assert api.apply_next(exchanges=(target,)).success


@pytest.mark.parametrize("invalid", [[], "exchange", (Path("/tmp"),)])
def test_scope_argument_type_errors_precede_core_work(monkeypatch, invalid):
    forbid_bundle_work(monkeypatch)
    with pytest.raises(TypeError):
        api.apply_next(exchanges=invalid)
