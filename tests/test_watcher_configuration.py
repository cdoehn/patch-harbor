from __future__ import annotations

from io import StringIO
import json
from pathlib import Path

import pytest

from patchharbor.user_paths import registration_user_paths
from patchharbor_watcher.loop import ApplyCompletion, run_watcher
from patchharbor_watcher.configuration import (
    WatcherConfigurationError,
    configure_watcher_input_directory,
    load_configured_watcher_input_directory,
    load_shared_exchange_directory,
)
from tests.registration_support import (
    isolated_user_environment,
    set_isolated_user_environment,
    write_exchange_configuration,
)


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


def test_cli_without_positional_path_uses_only_the_shared_exchange_config(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from patchharbor_watcher import cli as watcher_cli

    environment = isolated_user_environment(tmp_path / "user")
    for name, value in environment.items():
        monkeypatch.setenv(name, value)
    exchange = write_exchange_configuration(
        environment,
        tmp_path / "exchange",
    )

    legacy = tmp_path / "legacy-input"
    legacy.mkdir()
    configure_watcher_input_directory(legacy)

    observed: dict[str, object] = {}

    def fake_run_shared_exchange_watcher(
        exchange_directory: Path,
        **options: object,
    ) -> None:
        observed["exchange_directory"] = exchange_directory
        observed.update(options)

    monkeypatch.setattr(
        watcher_cli,
        "run_shared_exchange_watcher",
        fake_run_shared_exchange_watcher,
    )

    assert watcher_cli.main(
        ["--poll-interval", "0.25"],
        stdout=StringIO(),
        stderr=StringIO(),
    ) == 0
    assert load_shared_exchange_directory() == exchange
    assert observed["exchange_directory"] == exchange
    assert observed["poll_interval_seconds"] == 0.25
    assert observed["delegate"] is watcher_cli.delegate_to_automatic_apply
    assert "state_path" not in observed


def test_cli_shared_mode_rejects_missing_config_even_if_legacy_config_exists(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from patchharbor_watcher import cli as watcher_cli

    set_isolated_user_environment(monkeypatch, tmp_path / "user")
    legacy = tmp_path / "legacy-input"
    legacy.mkdir()
    configure_watcher_input_directory(legacy)
    stderr = StringIO()

    assert watcher_cli.main([], stdout=StringIO(), stderr=stderr) == 1
    assert "configuration does not exist" in stderr.getvalue()
