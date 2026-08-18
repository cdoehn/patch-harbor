from __future__ import annotations

from io import StringIO
from pathlib import Path

import pytest

from patchharbor.watcher import (
    ApplyCompletion,
    WatcherState,
    observe_input_directory,
    poll_input_directory_once,
)


def _successful_completion(_path: Path) -> ApplyCompletion:
    return ApplyCompletion(
        process_exit_code=0,
        apply_result={"success": True},
        response_is_json_object=True,
        stderr_text="",
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
        return _successful_completion(path)

    first = poll_input_directory_once(
        tmp_path,
        state,
        log_stream=log,
        error_stream=StringIO(),
        delegate=delegate,
    )
    second = poll_input_directory_once(
        tmp_path,
        state,
        log_stream=log,
        error_stream=StringIO(),
        delegate=delegate,
    )
    unchanged = poll_input_directory_once(
        tmp_path,
        state,
        log_stream=log,
        error_stream=StringIO(),
        delegate=delegate,
    )

    watched.write_bytes(b"second-version")
    changed_first = poll_input_directory_once(
        tmp_path,
        state,
        log_stream=log,
        error_stream=StringIO(),
        delegate=delegate,
    )
    changed_second = poll_input_directory_once(
        tmp_path,
        state,
        log_stream=log,
        error_stream=StringIO(),
        delegate=delegate,
    )

    assert (first, second, unchanged, changed_first, changed_second) == (
        0,
        1,
        0,
        0,
        1,
    )
    assert calls == [watched, watched]


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
    assert observed["log_stream"] is stdout
    assert observed["error_stream"] is stderr
