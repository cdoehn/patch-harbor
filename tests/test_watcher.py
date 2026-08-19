from __future__ import annotations

from io import StringIO
import json
from pathlib import Path
import zipfile

import pytest

from patchharbor.watcher import (
    ApplyCompletion,
    WatcherState,
    observe_input_directory,
    poll_input_directory_once,
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
    state = WatcherState()
    calls: list[Path] = []
    log = StringIO()

    def delegate(path: Path) -> ApplyCompletion:
        calls.append(path)
        return _completion()

    first = poll_input_directory_once(
        tmp_path,
        state,
        delegate=delegate,
        log_stream=log,
        error_stream=StringIO(),
    )
    second = poll_input_directory_once(
        tmp_path,
        state,
        delegate=delegate,
        log_stream=log,
        error_stream=StringIO(),
    )
    unchanged = poll_input_directory_once(
        tmp_path,
        state,
        delegate=delegate,
        log_stream=log,
        error_stream=StringIO(),
    )

    watched.write_bytes(b"second-version")
    changed_first = poll_input_directory_once(
        tmp_path,
        state,
        delegate=delegate,
        log_stream=log,
        error_stream=StringIO(),
    )
    changed_second = poll_input_directory_once(
        tmp_path,
        state,
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
    state = WatcherState()
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
        state,
        delegate=delegate,
        log_stream=log,
        error_stream=errors,
    )
    delegated = poll_input_directory_once(
        tmp_path,
        state,
        delegate=delegate,
        log_stream=log,
        error_stream=errors,
    )
    repeated = poll_input_directory_once(
        tmp_path,
        state,
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
    state = WatcherState()
    state.observe(observe_input_directory(tmp_path))
    calls: list[Path] = []
    stopping = False

    def delegate(path: Path) -> ApplyCompletion:
        nonlocal stopping
        calls.append(path)
        stopping = True
        return _completion()

    delegated = poll_input_directory_once(
        tmp_path,
        state,
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

    first_state = WatcherState.load(tmp_path.resolve(), state_path)
    for _ in range(3):
        poll_input_directory_once(
            tmp_path.resolve(),
            first_state,
            delegate=delegate,
            log_stream=StringIO(),
            error_stream=StringIO(),
        )

    restarted_state = WatcherState.load(tmp_path.resolve(), state_path)
    for _ in range(2):
        poll_input_directory_once(
            tmp_path.resolve(),
            restarted_state,
            delegate=delegate,
            log_stream=StringIO(),
            error_stream=StringIO(),
        )

    watched.write_bytes(b"second-content-is-different")
    for _ in range(2):
        poll_input_directory_once(
            tmp_path.resolve(),
            restarted_state,
            delegate=delegate,
            log_stream=StringIO(),
            error_stream=StringIO(),
        )

    assert calls == [b"first-content", b"second-content-is-different"]
    document = json.loads(state_path.read_text(encoding="utf-8"))
    assert document["input_directory"] == str(tmp_path.resolve())
    assert set(document["processed"]) == {str(watched.resolve())}
    assert len(document["processed"][str(watched.resolve())]) == 64
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

    state = WatcherState.load(tmp_path.resolve(), state_path)
    for _ in range(3):
        poll_input_directory_once(
            tmp_path.resolve(),
            state,
            delegate=delegate,
            log_stream=StringIO(),
            error_stream=StringIO(),
        )

    restarted = WatcherState.load(tmp_path.resolve(), state_path)
    for _ in range(2):
        poll_input_directory_once(
            tmp_path.resolve(),
            restarted,
            delegate=delegate,
            log_stream=StringIO(),
            error_stream=StringIO(),
        )

    assert calls == []
    document = json.loads(state_path.read_text(encoding="utf-8"))
    assert set(document["processed"]) == {str(result_bundle.resolve())}

def test_watcher_console_entry_point_configures_the_polling_loop(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from patchharbor import watcher_cli

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
