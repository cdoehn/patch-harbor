from __future__ import annotations

from io import StringIO
import json
from pathlib import Path

import pytest

from patchharbor.user_paths import registration_user_paths
from patchharbor.watcher import ApplyCompletion, run_watcher
from patchharbor.watcher_configuration import (
    WatcherConfigurationError,
    configure_watcher_input_directory,
    load_configured_watcher_input_directory,
)
from tests.registration_support import set_isolated_user_environment


def _successful_completion() -> ApplyCompletion:
    return ApplyCompletion(
        process_exit_code=0,
        apply_result={"success": True},
        invalid_response_text=None,
        stderr_text="",
    )


def _run_two_poll_cycles(
    input_directory: Path,
    state_path: Path,
    calls: list[Path],
) -> None:
    stop_requested = False
    completed_cycles = 0

    def delegate(path: Path) -> ApplyCompletion:
        calls.append(path)
        return _successful_completion()

    def complete_cycle(_timeout_seconds: float) -> None:
        nonlocal completed_cycles, stop_requested
        completed_cycles += 1
        stop_requested = completed_cycles == 2

    run_watcher(
        input_directory,
        delegate=delegate,
        state_path=state_path,
        poll_interval_seconds=1.0,
        log_stream=StringIO(),
        error_stream=StringIO(),
        stop_requested=lambda: stop_requested,
        wait_between_polls=complete_cycle,
    )
    assert completed_cycles == 2


def test_configured_input_survives_service_style_restart_without_redelegation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    set_isolated_user_environment(monkeypatch, tmp_path / "user")
    incoming = tmp_path / "incoming"
    incoming.mkdir()
    patch = incoming / "patch.zip"
    patch.write_bytes(b"stable-package")

    configured = configure_watcher_input_directory(incoming)
    configuration_path = registration_user_paths().watcher_configuration_path
    document = json.loads(configuration_path.read_text(encoding="utf-8"))
    assert document == {
        "format_version": 1,
        "input_directory": str(incoming.resolve()),
    }

    calls: list[Path] = []
    _run_two_poll_cycles(configured.directory, configured.state_path, calls)

    restarted = load_configured_watcher_input_directory()
    _run_two_poll_cycles(restarted.directory, restarted.state_path, calls)

    assert calls == [patch.resolve()]
    assert restarted == configured


def test_missing_or_nonregular_watcher_configuration_is_rejected(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    set_isolated_user_environment(monkeypatch, tmp_path / "user")
    configuration_path = registration_user_paths().watcher_configuration_path

    with pytest.raises(WatcherConfigurationError):
        load_configured_watcher_input_directory()

    configuration_path.mkdir()
    with pytest.raises(WatcherConfigurationError):
        load_configured_watcher_input_directory()


def test_cli_configures_then_runs_the_persisted_input_without_a_positional_path(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from patchharbor import watcher_cli

    set_isolated_user_environment(monkeypatch, tmp_path / "user")
    incoming = tmp_path / "incoming"
    incoming.mkdir()
    assert watcher_cli.main(
        ["--configure", str(incoming)],
        stdout=StringIO(),
        stderr=StringIO(),
    ) == 0

    observed: dict[str, object] = {}

    def fake_run_watcher(input_directory: Path, **options: object) -> None:
        observed["input_directory"] = input_directory
        observed.update(options)

    monkeypatch.setattr(watcher_cli, "run_watcher", fake_run_watcher)

    assert watcher_cli.main(
        ["--poll-interval", "0.25"],
        stdout=StringIO(),
        stderr=StringIO(),
    ) == 0
    assert observed["input_directory"] == incoming.resolve()
    assert observed["state_path"] == (
        configure_watcher_input_directory(incoming).state_path
    )
    assert observed["poll_interval_seconds"] == 0.25
