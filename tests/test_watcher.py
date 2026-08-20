from __future__ import annotations

from io import StringIO
import json
from pathlib import Path
import zipfile

import pytest

from patchharbor_watcher import state as watcher_state
from patchharbor.platform.filesystem import FileSystemOperationError
from patchharbor_watcher.loop import (
    ApplyCompletion,
    observe_input_directory,
    poll_input_directory_once,
)
from patchharbor_watcher.loop_guard import is_result_bundle_for_loop_prevention
from patchharbor_watcher.state import (
    FileIdentity,
    ProcessedFileStore,
    StabilityTracker,
)


def _completion(
    *,
    exit_code: int = 0,
    result: dict[str, object] | None = None,
    invalid_response: str | None = None,
    stderr: str = "",
) -> ApplyCompletion:
    return ApplyCompletion(
        process_exit_code=exit_code,
        apply_result={"success": True} if result is None else result,
        invalid_response_text=invalid_response,
        stderr_text=stderr,
    )


def test_scan_observes_only_top_level_regular_completed_files(
    tmp_path: Path,
) -> None:
    ready = tmp_path / "ready.zip"
    ready.write_bytes(b"ready")
    (tmp_path / "still-downloading.crdownload").write_bytes(b"partial")
    (tmp_path / "other.part").write_bytes(b"partial")
    nested = tmp_path / "nested"
    nested.mkdir()
    (nested / "nested.zip").write_bytes(b"nested")
    (tmp_path / "directory.zip").mkdir()

    observations = observe_input_directory(tmp_path)

    assert [observation.path for observation in observations] == [ready]
    assert observations[0].size == len(b"ready")
    assert observations[0].mtime_ns == ready.stat().st_mtime_ns


def test_file_requires_two_matching_observations_and_changed_file_restabilizes(
    tmp_path: Path,
) -> None:
    watched = tmp_path / "patch.zip"
    watched.write_bytes(b"first")
    stability = StabilityTracker()
    processed = ProcessedFileStore.in_memory(tmp_path.resolve())
    calls: list[Path] = []
    log = StringIO()

    def delegate(path: Path) -> ApplyCompletion:
        calls.append(path)
        return _completion()

    first = poll_input_directory_once(
        tmp_path,
        stability,
        processed,
        delegate=delegate,
        log_stream=log,
        error_stream=StringIO(),
    )
    second = poll_input_directory_once(
        tmp_path,
        stability,
        processed,
        delegate=delegate,
        log_stream=log,
        error_stream=StringIO(),
    )
    unchanged = poll_input_directory_once(
        tmp_path,
        stability,
        processed,
        delegate=delegate,
        log_stream=log,
        error_stream=StringIO(),
    )

    watched.write_bytes(b"second-version")
    changed_first = poll_input_directory_once(
        tmp_path,
        stability,
        processed,
        delegate=delegate,
        log_stream=log,
        error_stream=StringIO(),
    )
    changed_second = poll_input_directory_once(
        tmp_path,
        stability,
        processed,
        delegate=delegate,
        log_stream=log,
        error_stream=StringIO(),
    )

    assert (first, second, unchanged, changed_first, changed_second) == (
        0,
        1,
        0,
        0,
        1,
    )
    assert calls == [watched, watched]


def test_invalid_apply_response_is_recorded_once_without_semantic_retry(
    tmp_path: Path,
) -> None:
    watched = tmp_path / "patch.zip"
    watched.write_bytes(b"stable")
    stability = StabilityTracker()
    processed = ProcessedFileStore.in_memory(tmp_path.resolve())
    calls: list[Path] = []
    log = StringIO()
    errors = StringIO()

    def delegate(path: Path) -> ApplyCompletion:
        calls.append(path)
        return ApplyCompletion(
            process_exit_code=7,
            apply_result=None,
            invalid_response_text="not-json",
            stderr_text="apply stderr",
        )

    poll_input_directory_once(
        tmp_path,
        stability,
        processed,
        delegate=delegate,
        log_stream=log,
        error_stream=errors,
    )
    delegated = poll_input_directory_once(
        tmp_path,
        stability,
        processed,
        delegate=delegate,
        log_stream=log,
        error_stream=errors,
    )
    repeated = poll_input_directory_once(
        tmp_path,
        stability,
        processed,
        delegate=delegate,
        log_stream=log,
        error_stream=errors,
    )

    assert (delegated, repeated) == (1, 0)
    assert calls == [watched]
    records = [json.loads(line) for line in log.getvalue().splitlines()]
    assert len(records) == 1
    record = records[0]
    assert record["process_exit_code"] == 7
    assert record["apply_response_is_json_object"] is False
    assert record["invalid_apply_response"] == "not-json"
    assert errors.getvalue()


def test_poll_stops_before_delegating_additional_stable_files(
    tmp_path: Path,
) -> None:
    first = tmp_path / "a.zip"
    second = tmp_path / "b.zip"
    first.write_bytes(b"a")
    second.write_bytes(b"b")
    stability = StabilityTracker()
    processed = ProcessedFileStore.in_memory(tmp_path.resolve())
    stability.observe(observe_input_directory(tmp_path))
    calls: list[Path] = []
    stopping = False

    def delegate(path: Path) -> ApplyCompletion:
        nonlocal stopping
        calls.append(path)
        stopping = True
        return _completion()

    delegated = poll_input_directory_once(
        tmp_path,
        stability,
        processed,
        delegate=delegate,
        log_stream=StringIO(),
        error_stream=StringIO(),
        stop_requested=lambda: stopping,
    )

    assert delegated == 1
    assert calls == [first]



def test_processed_identity_persists_across_restart_and_changed_content_retries(
    tmp_path: Path,
) -> None:
    watched = tmp_path / "patch.zip"
    watched.write_bytes(b"first-content")
    state_path = tmp_path / "state" / "watcher.json"
    calls: list[bytes] = []

    def delegate(path: Path) -> ApplyCompletion:
        calls.append(path.read_bytes())
        return _completion()

    first_stability = StabilityTracker()
    first_processed = ProcessedFileStore.load(tmp_path.resolve(), state_path)
    for _ in range(3):
        poll_input_directory_once(
            tmp_path.resolve(),
            first_stability,
            first_processed,
            delegate=delegate,
            log_stream=StringIO(),
            error_stream=StringIO(),
        )

    restarted_stability = StabilityTracker()
    restarted_processed = ProcessedFileStore.load(tmp_path.resolve(), state_path)
    for _ in range(2):
        poll_input_directory_once(
            tmp_path.resolve(),
            restarted_stability,
            restarted_processed,
            delegate=delegate,
            log_stream=StringIO(),
            error_stream=StringIO(),
        )

    watched.write_bytes(b"second-content-is-different")
    for _ in range(2):
        poll_input_directory_once(
            tmp_path.resolve(),
            restarted_stability,
            restarted_processed,
            delegate=delegate,
            log_stream=StringIO(),
            error_stream=StringIO(),
        )

    assert calls == [b"first-content", b"second-content-is-different"]
    document = json.loads(state_path.read_text(encoding="utf-8"))
    assert document["input_directory"] == str(tmp_path.resolve())
    assert set(document["processed"]) == {str(watched.resolve())}
    assert len(document["processed"][str(watched.resolve())]) == 64

    watched.unlink()
    poll_input_directory_once(
        tmp_path.resolve(),
        restarted_stability,
        restarted_processed,
        delegate=delegate,
        log_stream=StringIO(),
        error_stream=StringIO(),
    )

    pruned = json.loads(state_path.read_text(encoding="utf-8"))
    assert pruned["processed"] == {}
    assert not tuple(state_path.parent.glob(".patchharbor-watcher-*.tmp"))


def test_result_bundle_marker_is_persistently_skipped_without_apply(
    tmp_path: Path,
) -> None:
    result_bundle = tmp_path / "patchharbor_result.zip"
    with zipfile.ZipFile(result_bundle, mode="w") as archive:
        archive.writestr(
            "manifest.json",
            json.dumps({"marker": "patch-harbor-result-bundle"}),
        )
        archive.writestr("base/tracked.txt", b"content")
    state_path = tmp_path / "state" / "watcher.json"
    calls: list[Path] = []

    def delegate(path: Path) -> ApplyCompletion:
        calls.append(path)
        return _completion()

    stability = StabilityTracker()
    processed = ProcessedFileStore.load(tmp_path.resolve(), state_path)
    for _ in range(3):
        poll_input_directory_once(
            tmp_path.resolve(),
            stability,
            processed,
            delegate=delegate,
            log_stream=StringIO(),
            error_stream=StringIO(),
        )

    restarted_stability = StabilityTracker()
    restarted_processed = ProcessedFileStore.load(tmp_path.resolve(), state_path)
    for _ in range(2):
        poll_input_directory_once(
            tmp_path.resolve(),
            restarted_stability,
            restarted_processed,
            delegate=delegate,
            log_stream=StringIO(),
            error_stream=StringIO(),
        )

    assert calls == []
    document = json.loads(state_path.read_text(encoding="utf-8"))
    assert set(document["processed"]) == {str(result_bundle.resolve())}


def test_processed_status_changes_only_after_atomic_state_publication(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state_path = tmp_path / "state" / "watcher.json"
    store = ProcessedFileStore.load(tmp_path.resolve(), state_path)
    identity = FileIdentity(
        path=(tmp_path / "patch.zip").resolve(),
        content_sha256="a" * 64,
    )

    def fail_atomic_replace(_target: Path, _payload: bytes) -> None:
        raise FileSystemOperationError("cannot replace target", OSError("failed"))

    monkeypatch.setattr(watcher_state, "atomic_replace_bytes", fail_atomic_replace)

    with pytest.raises(RuntimeError):
        store.mark_processed(identity)

    assert not store.was_processed(identity)
    assert not state_path.exists()


def test_result_bundle_loop_guard_uses_only_the_reserved_marker(
    tmp_path: Path,
) -> None:
    result_bundle = tmp_path / "result.zip"
    with zipfile.ZipFile(result_bundle, mode="w") as archive:
        archive.writestr(
            "manifest.json",
            json.dumps(
                {
                    "marker": "patch-harbor-result-bundle",
                    "not_a_result_bundle_schema": True,
                }
            ),
        )

    ordinary_zip = tmp_path / "ordinary.zip"
    with zipfile.ZipFile(ordinary_zip, mode="w") as archive:
        archive.writestr("manifest.json", json.dumps({"marker": "other"}))
        archive.writestr("patch.json", b"not parsed by the loop guard")

    assert is_result_bundle_for_loop_prevention(result_bundle)
    assert not is_result_bundle_for_loop_prevention(ordinary_zip)

def test_watcher_console_entry_point_configures_the_polling_loop(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from patchharbor_watcher import cli as watcher_cli

    observed: dict[str, object] = {}

    def fake_run_watcher(input_directory: Path, **options: object) -> None:
        observed["input_directory"] = input_directory
        observed.update(options)

    state_path = tmp_path / "watcher-state.json"
    monkeypatch.setattr(
        watcher_cli,
        "prepare_watcher_input_directory",
        lambda _path: watcher_cli.PreparedWatcherInput(
            directory=tmp_path.resolve(),
            state_path=state_path,
        ),
    )
    monkeypatch.setattr(watcher_cli, "run_watcher", fake_run_watcher)
    stdout = StringIO()
    stderr = StringIO()

    result = watcher_cli.main(
        [str(tmp_path), "--poll-interval", "0.25"],
        stdout=stdout,
        stderr=stderr,
    )

    assert result == 0
    assert observed["input_directory"] == tmp_path.resolve()
    assert observed["state_path"] == state_path
    assert observed["poll_interval_seconds"] == 0.25
    assert observed["delegate"] is watcher_cli.delegate_to_apply
    assert callable(observed["stop_requested"])
    assert callable(observed["wait_between_polls"])
    assert observed["log_stream"] is stdout
    assert observed["error_stream"] is stderr
