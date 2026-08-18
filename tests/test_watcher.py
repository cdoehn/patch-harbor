from __future__ import annotations

from io import StringIO
import json
from pathlib import Path

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
    record = json.loads(log.getvalue())
    assert record["process_exit_code"] == 7
    assert record["apply_response_is_json_object"] is False
    assert record["apply_result"] is None
    assert record["invalid_apply_response"] == "not-json"
    assert errors.getvalue().splitlines() == ["apply stderr"]


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


def test_watcher_console_entry_point_configures_the_polling_loop(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from patchharbor import watcher_cli

    observed: dict[str, object] = {}

    def fake_run_watcher(input_directory: Path, **options: object) -> None:
        observed["input_directory"] = input_directory
        observed.update(options)

    monkeypatch.setattr(watcher_cli, "run_watcher", fake_run_watcher)
    stdout = StringIO()
    stderr = StringIO()

    result = watcher_cli.main(
        [str(tmp_path), "--poll-interval", "0.25"],
        stdout=stdout,
        stderr=stderr,
    )

    assert result == 0
    assert observed["input_directory"] == tmp_path
    assert observed["poll_interval_seconds"] == 0.25
    assert observed["delegate"] is watcher_cli.delegate_to_apply
    assert callable(observed["stop_requested"])
    assert callable(observed["wait_for_stop"])
    assert observed["log_stream"] is stdout
    assert observed["error_stream"] is stderr
