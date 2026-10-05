"""Pinned-runtime Results preserve real state and fail safely at publication."""
from __future__ import annotations

from functools import partial
import json
from zipfile import ZipFile

import pytest

from patchharbor import api
from patchharbor import result_bundle, result_bundle_publication as publication
from patchharbor import result_bundle_writer as writer, result_resources as resources
from patchharbor.errors import result_bundle_error
from patchharbor.resource_policy import ResourcePolicy
from patchharbor.result_reader import read_result_reference
from patchharbor.runtime_artifact import RuntimeProvision
from tests.platform_support import native_script, native_value
from tests.registration_support import git
from tests.test_runtime_artifact import prepared
from tests.test_result_runtime_writer import artifact, repository, package


@pytest.mark.parametrize("route", ["bundle", "apply", "failure"])
@pytest.mark.parametrize("runtime_state", ["embedded", "missing", "budget"])
def test_dirty_snapshot_and_explicit_target_survive_runtime_restrictions(
    repository, artifact, monkeypatch, tmp_path, route, runtime_state,
):
    root, exchange = repository
    (root / "tracked.txt").write_bytes(b"staged\n")
    git(root, "add", "tracked.txt")
    (root / "tracked.txt").write_bytes(b"working tree\n")
    untracked = b"\x00actual untracked bytes\xff\n"
    (root / "untracked.bin").write_bytes(untracked)
    provision = (RuntimeProvision("unavailable", "resources_missing", None)
                 if runtime_state == "missing" else RuntimeProvision("embedded", None, artifact))
    monkeypatch.setattr(resources.RuntimeProvider, "capture", lambda self: provision)
    if runtime_state == "budget":
        monkeypatch.setattr(result_bundle, "runtime_fits", partial(resources.runtime_fits,
                            policy=ResourcePolicy(max_zip_total_bytes=128 * 1024)))
    target = tmp_path / "explicit-results"
    target.mkdir()
    if route == "bundle":
        report = api.bundle(root, output_directory=target).report
    else:
        report = api.apply(package(root, exchange, exit_code=29 if route == "failure" else 0),
                           output_directory=target)
    assert report.process_exit_code == (29 if route == "failure" else 0)
    assert report.result_bundle.path.parent == target
    facts, _ = read_result_reference(report.result_bundle.path)
    assert facts.context.dirty and facts.runtime.status == (
        "embedded" if runtime_state == "embedded" else "unavailable")
    with ZipFile(report.result_bundle.path) as archive:
        assert archive.read("base/tracked.txt") == b"base\n"
        assert b"+staged" in archive.read("changes/staged.patch")
        assert b"+working tree" in archive.read("changes/unstaged.patch")
        assert archive.read("untracked/untracked.bin") == untracked
        assert ("logs/execution.log" in archive.namelist()) == (route != "bundle")
    assert (root / "tracked.txt").read_bytes() == b"working tree\n"
    assert git(root, "show", ":tracked.txt").stdout == "staged\n"


@pytest.mark.parametrize("fault", ["runtime_write", "snapshot_write", "verify", "replace"])
@pytest.mark.parametrize("exit_code", [0, 23])
def test_real_publication_failures_preserve_primary_and_latest_proven_context(
    repository, artifact, monkeypatch, fault, exit_code,
):
    root, exchange = repository
    patch = package(root, exchange)
    # This is an actual fixture commit made by the actual entrypoint.
    body = native_script(
        f"printf 'updated\\n' > tracked.txt\ngit add tracked.txt\ngit commit -m changed\nexit {exit_code}",
        "[System.IO.File]::WriteAllText('tracked.txt', \"updated`n\")\n"
        f"git add tracked.txt\ngit commit -m changed\nexit {exit_code}",
    )
    with ZipFile(patch) as archive:
        manifest = archive.read("patch.json")
    with ZipFile(patch, "w") as archive:
        archive.writestr("patch.json", manifest)
        archive.writestr(native_value("run.sh", "run.ps1"), body)
    monkeypatch.setattr(resources.RuntimeProvider, "capture",
                        lambda self: RuntimeProvision("embedded", None, artifact))
    writes = []
    original = writer._write_entry

    def write(archive, name, raw, **options):
        writes.append(name)
        if ((fault == "runtime_write" and name.endswith(".whl"))
                or (fault == "snapshot_write" and name.startswith("base/"))):
            raise PermissionError("simulated write denied")
        return original(archive, name, raw, **options)

    def fail(*args, **kwargs):
        raise result_bundle_error("simulated publication failure")

    monkeypatch.setattr(writer, "_write_entry", write)
    if fault == "verify": monkeypatch.setattr(publication, "_verify_result_bundle", fail)
    if fault == "replace": monkeypatch.setattr(publication, "replace_path", fail)
    report = api.apply(patch)
    assert report.primary_result.entrypoint_exit_code == exit_code
    assert report.result_bundle.status is api.ResultBundleStatus.FAILED
    current = git(root, "rev-parse", "HEAD").stdout.strip()
    assert str(report.context.base_commit) == current
    rescue = report.result_bundle.emergency_diagnostics_path
    document = json.loads((rescue / "run.json").read_bytes())
    assert document["base_commit"] == current
    assert document["primary_result"]["entrypoint_exit_code"] == exit_code
    assert (rescue / "execution.log").read_bytes()
    assert writes.count("manifest.json") == 1  # no unbounded retry or hidden success
    assert not tuple(exchange.glob("*_Result_*.zip"))
    assert not tuple(exchange.glob(".*.tmp"))


def test_publication_abort_is_not_converted_to_runtime_fallback(repository, artifact, monkeypatch):
    root, exchange = repository
    monkeypatch.setattr(resources.RuntimeProvider, "capture",
                        lambda self: RuntimeProvision("embedded", None, artifact))
    def interrupted(*args, **kwargs):
        raise KeyboardInterrupt
    monkeypatch.setattr(publication, "_verify_result_bundle", interrupted)
    with pytest.raises(KeyboardInterrupt):
        api.bundle(root)
    assert not tuple(exchange.glob("*_Result_*.zip"))
    assert not tuple(exchange.glob(".*.tmp"))
