"""Owned publication stabilization, bounded retries and adversarial failures."""
from dataclasses import replace
from io import BytesIO
import json
import os
from pathlib import Path
from zipfile import ZipFile, ZIP_STORED

import pytest

from patchharbor import api
from patchharbor.errors import PatchHarborError, result_bundle_error
from patchharbor import result_bundle_publication as publication
from patchharbor import result_bundle_writer as writer, result_reader as reader
from patchharbor import result_verification as verification
from patchharbor.platform import filesystem
from patchharbor.platform.cifs import cache_wait_budget
from patchharbor.resource_policy import DEFAULT_RESOURCE_POLICY
from tests.test_result_bundle_publication import _publish, prepare_result_bundle_publication, UUID
from tests.test_result_runtime_writer import repository, package


@pytest.fixture
def destination(tmp_path):
    return prepare_result_bundle_publication(tmp_path / "result.zip",
        run_id=UUID("12345678-1234-4234-8234-123456789abc"))


@pytest.fixture
def sleeps(monkeypatch):
    calls = []
    monkeypatch.setattr(verification, "sleep", calls.append)
    monkeypatch.setattr(verification, "publication_wait_budget", lambda path: 300)
    return calls


def unstable(*args, **kwargs):
    raise filesystem.FileChangedDuringRead(category="initial-open-state-mismatch")


def test_real_initial_open_mismatch_is_retried_after_sync(destination, sleeps, monkeypatch):
    events = []
    original_sync = publication.sync_regular_file_best_effort
    original_directory = publication.sync_directory_best_effort
    original_compare = filesystem._same_path_and_open_file_state
    compares = 0
    def compare(*args, **kwargs):
        nonlocal compares
        compares += 1
        events.append("compare")
        return compares != 1 and original_compare(*args, **kwargs)
    def sync(*args, **kwargs):
        events.append("file-sync")
        return original_sync(*args, **kwargs)
    def directory(*args, **kwargs):
        events.append("directory-sync")
        return original_directory(*args, **kwargs)
    monkeypatch.setattr(filesystem, "_same_path_and_open_file_state", compare)
    monkeypatch.setattr(publication, "sync_regular_file_best_effort", sync)
    monkeypatch.setattr(publication, "sync_directory_best_effort", directory)
    _publish(destination)
    assert sleeps == [2]
    assert events[:6] == ["file-sync", "directory-sync", "compare"] * 2
    assert reader.read_result_reference(destination.final_path)[0].primary_result.success
    assert not destination.temporary_path.exists()


def test_all_attempts_exhausted_preserve_safe_diagnostics(destination, sleeps, monkeypatch):
    monkeypatch.setattr(reader, "read_stable_regular_file_with_sha256", unstable)
    with pytest.raises(verification.ResultVerificationError) as caught:
        _publish(destination)
    details = caught.value.diagnostics
    assert sleeps == [2, 3, 5, 10, 20, 20, 30, 30, 60, 60, 60]
    assert details["verification_attempts"] == 12
    assert details["waited_seconds"] == details["retry_budget_seconds"] == 300
    assert details["verification_error_type"] == "FileChangedDuringRead"
    assert details["stable_read_mismatch"] == "initial-open-state-mismatch"
    assert len(details["sync_outcomes"]) == 12
    assert not destination.final_path.exists() and not destination.temporary_path.exists()


@pytest.mark.parametrize("fault", ["nonzip", "crc", "manifest", "inventory", "binding", "handoff", "resource"])
def test_integrity_failures_never_retry(destination, sleeps, monkeypatch, fault):
    original_write = writer.write_result_bundle
    calls = []
    def corrupt(stream, **kwargs):
        buffer = BytesIO()
        original_write(buffer, **kwargs)
        with ZipFile(buffer) as archive:
            members = {name: archive.read(name) for name in archive.namelist()}
        if fault in {"manifest", "inventory", "binding"}:
            document = json.loads(members["manifest.json"])
            if fault == "manifest":
                document["format_version"] = 999
            elif fault == "inventory":
                members["base/unaccounted.txt"] = b"unexpected"
            else:
                document["repo_id"] = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"
            members["manifest.json"] = json.dumps(document).encode()
        if fault == "handoff":
            members.pop("CHAT_INSTRUCTIONS.md")
        output = BytesIO()
        with ZipFile(output, "w", compression=ZIP_STORED) as archive:
            for name, content in members.items():
                archive.writestr(name, content)
        raw = bytearray(output.getvalue())
        if fault == "nonzip":
            raw = b"not a zip"
        elif fault == "crc":
            raw[30 + len("manifest.json")] ^= 1
        stream.write(raw)
    original_read = publication.read_result_reference
    def read(*args, **kwargs):
        calls.append(True)
        if fault == "resource":
            kwargs["resource_policy"] = replace(DEFAULT_RESOURCE_POLICY, warning_bytes=1, max_input_artifact_bytes=1)
        return original_read(*args, **kwargs)
    monkeypatch.setattr(publication, "write_result_bundle", corrupt)
    monkeypatch.setattr(publication, "read_result_reference", read)
    with pytest.raises(PatchHarborError):
        _publish(destination)
    assert calls == [True] and sleeps == []
    assert not destination.final_path.exists() and not destination.temporary_path.exists()


@pytest.mark.parametrize("fault", ["replace", "symlink", "missing"])
def test_ownership_lost_between_attempts_stops_and_preserves_foreign_file(destination, sleeps, monkeypatch, fault):
    displaced = destination.temporary_path.with_name("displaced")
    if fault == "symlink":
        probe = displaced.with_name("probe")
        try:
            probe.symlink_to(displaced)
        except OSError:
            pytest.skip("symlink creation unavailable")
        probe.unlink()
    def change(delay):
        sleeps.append(delay)
        destination.temporary_path.rename(displaced)
        if fault == "replace":
            destination.temporary_path.write_bytes(b"foreign file")
        elif fault == "symlink":
            destination.temporary_path.symlink_to(displaced)
    monkeypatch.setattr(reader, "read_stable_regular_file_with_sha256", unstable)
    monkeypatch.setattr(verification, "sleep", change)
    with pytest.raises(PatchHarborError):
        _publish(destination)
    assert sleeps == [2] and not destination.final_path.exists()
    assert displaced.is_file()
    if fault == "replace":
        assert destination.temporary_path.read_bytes() == b"foreign file"
    elif fault == "symlink":
        assert destination.temporary_path.is_symlink()


def test_same_inode_same_length_restored_mtime_content_change_is_rejected(destination, sleeps):
    def mutate(digest):
        info = destination.temporary_path.stat()
        with destination.temporary_path.open("r+b") as stream:
            first = stream.read(1)
            stream.seek(0)
            stream.write(bytes([first[0] ^ 1]))
        os.utime(destination.temporary_path, ns=(info.st_atime_ns, info.st_mtime_ns))
        assert os.path.samestat(info, destination.temporary_path.stat())
    with pytest.raises(PatchHarborError):
        _publish(destination, before_publish=mutate)
    assert sleeps == [] and not destination.final_path.exists()


def test_receipt_read_shares_retry_budget_without_repeating_receipt(destination, sleeps, monkeypatch):
    original = publication.read_stable_regular_file_with_sha256
    attempts = []
    receipts = []
    def transient(*args, **kwargs):
        attempts.append(True)
        if len(attempts) == 1:
            unstable()
        return original(*args, **kwargs)
    monkeypatch.setattr(publication, "read_stable_regular_file_with_sha256", transient)
    _publish(destination, before_publish=receipts.append)
    assert sleeps == [2] and len(receipts) == 1 and len(attempts) == 2
    assert reader.read_result_reference(destination.final_path)[1] == receipts[0]


def test_final_read_cannot_restart_exhausted_publication_wait_budget(destination, sleeps, monkeypatch):
    original = reader.read_stable_regular_file_with_sha256
    attempts = []
    receipts = []
    def transient(*args, **kwargs):
        attempts.append(True)
        if len(attempts) <= 11:
            unstable()
        return original(*args, **kwargs)
    monkeypatch.setattr(reader, "read_stable_regular_file_with_sha256", transient)
    monkeypatch.setattr(publication, "read_stable_regular_file_with_sha256", unstable)
    with pytest.raises(verification.ResultVerificationError) as caught:
        _publish(destination, before_publish=receipts.append)
    assert len(attempts) == 12 and len(receipts) == 1
    assert sum(sleeps) == 300 and len(sleeps) == 11
    assert caught.value.diagnostics["verification_stage"] == "temporary-result-final-read"
    assert caught.value.diagnostics["verification_attempts"] == 1
    assert not destination.final_path.exists()


def test_unrelated_error_with_implicit_read_failure_context_never_retries(destination, sleeps, monkeypatch):
    def unrelated(*args, **kwargs):
        try:
            unstable()
        except filesystem.FileChangedDuringRead:
            raise result_bundle_error("unrelated failure")
    monkeypatch.setattr(publication, "_verify_result_bundle", unrelated)
    with pytest.raises(PatchHarborError):
        _publish(destination)
    assert sleeps == [] and not destination.final_path.exists()


def test_cancellation_during_retry_cleans_only_owned_temporary_file(destination, sleeps, monkeypatch):
    def stop(delay):
        raise KeyboardInterrupt
    monkeypatch.setattr(reader, "read_stable_regular_file_with_sha256", unstable)
    monkeypatch.setattr(verification, "sleep", stop)
    with pytest.raises(KeyboardInterrupt):
        _publish(destination)
    assert not destination.temporary_path.exists() and not destination.final_path.exists()


@pytest.mark.parametrize("route", ["bundle", "apply", "failed-apply"])
def test_emergency_json_survives_real_request_failure(repository, sleeps, monkeypatch, route):
    root, exchange = repository
    # Inject only publication reads; repository state/entrypoint capture stay real.
    monkeypatch.setattr(publication, "read_result_reference", unstable)
    if route == "bundle":
        with pytest.raises(PatchHarborError) as caught:
            api.bundle(root)
        report = caught.value.run_report
    else:
        report = api.apply(package(root, exchange, exit_code=23 if route == "failed-apply" else 0))
        assert report.primary_result.entrypoint_exit_code == (23 if route == "failed-apply" else 0)
    directory = report.result_bundle.emergency_diagnostics_path
    details = json.loads((directory / "verification.json").read_bytes())
    saved = json.loads((directory / "run.json").read_bytes())
    assert details["verification_attempts"] == 12 and details["waited_seconds"] == 300
    assert saved["result_bundle"]["status"] == "failed"
    assert saved["base_commit"] == str(report.context.base_commit)
    assert not list(exchange.glob("*_Result_*.zip")) and not list(exchange.glob(".*.tmp"))


@pytest.mark.parametrize("options,budget", [("rw", 300), ("actimeo=1,closetimeo=1", 300),
    ("actimeo=300,closetimeo=1", 612), ("actimeo=600,acregmax=1,closetimeo=1", 300),
    ("acregmax=600,closetimeo=60", 1330), ("actimeo=invalid", 300), ("actimeo=-1", 300)])
def test_cifs_budget_uses_effective_regular_file_cache(options, budget):
    info = f"10 1 0:1 / /mnt/exchange rw - cifs //server/share {options}\n"
    assert cache_wait_budget(Path("/mnt/exchange/result.zip"), info) == budget


def test_mount_selection_handles_escaped_paths_and_nested_local_mounts():
    info = ("10 1 0:1 / /mnt/my\\040share rw - cifs //server/share actimeo=600\n"
            "11 10 1:2 / /mnt/my\\040share/local rw - ext4 /dev/disk rw\n")
    assert cache_wait_budget(Path("/mnt/my share/result.zip"), info) == 1212
    assert cache_wait_budget(Path("/mnt/my share/local/result.zip"), info) == 300
    assert cache_wait_budget(Path("/mnt/my share-other/result.zip"), info) == 300


def test_long_explicit_cache_extends_only_the_last_wait(destination, sleeps, monkeypatch):
    monkeypatch.setattr(verification, "publication_wait_budget", lambda path: 612)
    monkeypatch.setattr(reader, "read_stable_regular_file_with_sha256", unstable)
    with pytest.raises(verification.ResultVerificationError) as caught:
        _publish(destination)
    assert sleeps == [2, 3, 5, 10, 20, 20, 30, 30, 60, 60, 60, 312]
    assert caught.value.diagnostics["waited_seconds"] == 612
