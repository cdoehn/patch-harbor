"""End-to-end ownership across configuration, Apply, worker and archive boundaries."""
from __future__ import annotations

import json
import os
from pathlib import Path
import zipfile

import pytest

from patchharbor import api
from patchharbor.user_paths import registration_user_paths
from patchharbor_watcher.apply_boundary import delegate_to_automatic_apply
from tests.platform_support import native_script, native_value, project_environment
from tests.registration_support import create_repository, git, set_isolated_user_environment
from tests.test_api_e2e import write_package

pytestmark = [pytest.mark.e2e, pytest.mark.acceptance]


@pytest.fixture
def pair(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    set_isolated_user_environment(monkeypatch, tmp_path / "user")
    a = create_repository(tmp_path / "a")
    b = create_repository(tmp_path / "b")
    ca, cb = api.register(a), api.register(b)
    return a, b, ca, cb


def _configure(pair, tmp_path, shared):
    a, b, ca, cb = pair
    ea = tmp_path / "exchange-a"
    eb = ea if shared else tmp_path / "exchange-b"
    for repo, exchange, suffix, archive in ((a, ea, ".A", "Archive-A"), (b, eb, ".B", "Archive-B")):
        api.configure_exchange_directory(exchange, repository=repo)
        api.configure_bundle_suffix(suffix, repository=repo)
        api.configure_archive_directory(archive, repository=repo)
    return a, b, ca, cb, ea, eb


def _environment(path):
    with zipfile.ZipFile(path) as archive:
        return json.loads(archive.read("environment.json"))


def _commit_package(path, context):
    entrypoint = native_value("run.sh", "run.ps1")
    body = native_script(
        "git commit --allow-empty -m config-acceptance",
        "git commit --allow-empty -m config-acceptance; if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }",
    )
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("patch.json", json.dumps({
            "marker": "patch-harbor", "format_version": 1,
            "repo_id": str(context.repo_id), "base_commit": str(context.base_commit),
            "state_fingerprint": context.state_fingerprint,
            "fingerprint_algorithm": context.fingerprint_algorithm, "entrypoint": entrypoint,
        }))
        archive.writestr(entrypoint, body)


@pytest.mark.parametrize("shared", [False, True])
def test_actual_apply_from_nested_cwd_and_explicit_other_target(pair, tmp_path, monkeypatch, shared):
    a, b, ca, cb, ea, eb = _configure(pair, tmp_path, shared)
    write_package(ea / "a.zip", ca)
    external = tmp_path / "external-b.zip"
    write_package(external, cb)
    nested = a / "nested"
    nested.mkdir()
    monkeypatch.chdir(nested)
    first = api.apply()
    assert first.success and first.execution_present
    assert first.context.repo_id == ca.repo_id
    assert first.result_bundle.path.parent == ea
    assert first.result_bundle.path.name.endswith(".zip.A")
    second = api.apply(external)
    assert second.success and second.execution_present
    assert second.context.repo_id == cb.repo_id
    assert second.result_bundle.path.parent == eb
    assert second.result_bundle.path.name.endswith(".zip.B")
    environment = _environment(second.result_bundle.path)
    assert environment["repository_path"] == str(b)
    assert environment["repository_context"]["repo_id"] == str(cb.repo_id)
    assert environment["bundle_suffix"] == ".B"
    assert environment["exchange_directory"] == str(eb)
    assert api.context(a) == ca and api.context(b) == cb


@pytest.mark.parametrize("exchange_state", ["unset", "unavailable"])
def test_explicit_output_uses_valid_target_config_without_exchange(pair, tmp_path, exchange_state):
    a, b, ca, cb = pair
    api.configure_bundle_suffix(".target", repository=b)
    if exchange_state == "unavailable":
        missing = tmp_path / "unavailable-exchange"
        api.configure_exchange_directory(missing, repository=b)
        missing.rmdir()
    config = api.configuration(b)
    # A read is not a physical-directory availability check.
    assert config.exchange_directory is None if exchange_state == "unset" else config.exchange_directory == missing
    with pytest.raises(api.PatchHarborError):
        api.configuration(b, revalidate=True)
    external = tmp_path / "b.zip"
    write_package(external, cb)
    output = tmp_path / "explicit-output"
    report = api.apply(external, output_directory=output)
    assert report.success and report.execution_present
    assert report.context.repo_id == cb.repo_id
    assert report.result_bundle.path.parent == output
    assert report.result_bundle.path.name.endswith(".zip.target")
    environment = _environment(report.result_bundle.path)
    assert environment["output_directory"] == str(output)
    assert environment["exchange_directory"] == (None if exchange_state == "unset" else str(missing))
    assert environment["bundle_suffix"] == ".target"
    assert api.configuration(a).exchange_directory is None


@pytest.mark.parametrize("damage", ["missing", "invalid"])
def test_explicit_output_never_bypasses_damaged_local_config(pair, tmp_path, damage):
    a, b, ca, cb = pair
    config = api.configuration(b).path
    if damage == "missing":
        config.unlink()
    else:
        config.write_bytes(b"not-json")
    package = tmp_path / "b.zip"
    write_package(package, cb)
    output = tmp_path / "not-published"
    report = api.apply(package, output_directory=output)
    assert not report.success and not report.execution_present
    assert report.result_bundle.path is None
    assert git(b, "rev-parse", "HEAD").stdout.strip() == str(cb.base_commit)
    assert not output.exists()
    assert not config.exists() if damage == "missing" else config.read_bytes() == b"not-json"


@pytest.mark.parametrize("shared", [False, True])
def test_real_worker_reloads_target_config_and_ignores_wrong_exchange(pair, tmp_path, monkeypatch, shared):
    a, b, ca, cb, ea, eb = _configure(pair, tmp_path, shared)
    outside = tmp_path / "not-a-repository"
    outside.mkdir()
    monkeypatch.chdir(outside)
    write_package(eb / "first-b.zip", cb)
    first = delegate_to_automatic_apply(environment=project_environment())
    assert first.process_exit_code == 0, first
    result = first.apply_result["result"]
    assert result["repo_id"] == str(cb.repo_id)
    path = Path(result["result_bundle"]["path"])
    assert path.parent == eb and path.name.endswith(".zip.B")
    new_exchange = tmp_path / "new-b-exchange"
    api.configure_exchange_directory(new_exchange, repository=b)
    api.configure_bundle_suffix(".new", repository=b)
    # This fresh, newer package belongs to B but is now in the wrong folder.
    wrong = ea / "wrong-b.zip"
    write_package(wrong, cb)
    correct = new_exchange / "second-b.zip"
    write_package(correct, cb)
    os.utime(correct, ns=(1_000_000_000, 1_000_000_000))
    os.utime(wrong, ns=(9_000_000_000, 9_000_000_000))
    second = delegate_to_automatic_apply(environment=project_environment())
    assert second.process_exit_code == 0, second
    path = Path(second.apply_result["result"]["result_bundle"]["path"])
    assert path.parent == new_exchange and path.name.endswith(".zip.new")
    assert _environment(path)["exchange_directory"] == str(new_exchange)
    assert wrong.exists() and correct.exists()
    assert api.context(a) == ca


@pytest.mark.parametrize("disable_b", [False, True])
def test_shared_exchange_archives_only_the_owning_repositories_bundles(pair, tmp_path, disable_b):
    a, b, ca, cb, exchange, _ = _configure(pair, tmp_path, True)
    if disable_b:
        api.configure_archive_directory("", repository=b)
    old_a, old_b = api.bundle(a).path, api.bundle(b).path
    bytes_a, bytes_b = old_a.read_bytes(), old_b.read_bytes()
    patch_a, patch_b = exchange / "a.zip", exchange / "b.zip"
    _commit_package(patch_a, ca)
    _commit_package(patch_b, cb)
    patch_a_bytes, patch_b_bytes = patch_a.read_bytes(), patch_b.read_bytes()
    assert api.apply(patch_a).success
    assert api.apply(patch_b).success
    # Current Result snapshots remain; old clean ancestor results and proven patches move.
    api.bundle(a)
    assert not old_a.exists() and not patch_a.exists()
    assert (exchange / "Archive-A" / old_a.name).read_bytes() == bytes_a
    assert (exchange / "Archive-A" / patch_a.name).read_bytes() == patch_a_bytes
    assert old_b.read_bytes() == bytes_b and patch_b.read_bytes() == patch_b_bytes
    assert not (exchange / "Archive-A" / old_b.name).exists()
    api.bundle(b)
    if disable_b:
        assert old_b.read_bytes() == bytes_b and patch_b.read_bytes() == patch_b_bytes
        assert not (exchange / "Archive-B").exists()
    else:
        assert not old_b.exists() and not patch_b.exists()
        assert (exchange / "Archive-B" / old_b.name).read_bytes() == bytes_b
        assert (exchange / "Archive-B" / patch_b.name).read_bytes() == patch_b_bytes
    assert api.context(a).base_commit != ca.base_commit
    assert api.context(b).base_commit != cb.base_commit


def test_config_writes_preserve_existing_replay_ledger(pair, tmp_path):
    a, b, ca, cb, ea, eb = _configure(pair, tmp_path, False)
    write_package(ea / "applied.zip", ca)
    report = api.apply(repository=a)
    assert report.success
    ledger = registration_user_paths().exchange_state_path
    before = ledger.read_bytes()
    api.configure_bundle_suffix(".changed", repository=a)
    api.configure_archive_directory("", repository=a)
    api.configure_exchange_directory(tmp_path / "new-exchange", repository=a)
    assert ledger.read_bytes() == before
    assert api.configuration(b).exchange_directory == eb
