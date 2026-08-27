from __future__ import annotations

from io import StringIO
from pathlib import Path

import pytest

from tests.registration_support import (
    isolated_user_environment,
    set_isolated_user_environment,
    write_exchange_configuration,
)


def test_cli_runs_only_the_shared_exchange_watcher(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from patchharbor_watcher import cli as watcher_cli

    environment = isolated_user_environment(tmp_path / "user")
    for name, value in environment.items():
        monkeypatch.setenv(name, value)
    exchange = write_exchange_configuration(environment, tmp_path / "exchange")
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
    stdout = StringIO()
    stderr = StringIO()

    assert watcher_cli.main(
        ["--poll-interval", "0.25"],
        stdout=stdout,
        stderr=stderr,
    ) == 0
    assert observed["exchange_directory"] == exchange
    assert observed["poll_interval_seconds"] == 0.25
    assert observed["delegate"] is watcher_cli.delegate_to_automatic_apply
    assert callable(observed["stop_requested"])
    assert callable(observed["wait_between_polls"])
    assert observed["log_stream"] is stdout
    assert observed["error_stream"] is stderr


@pytest.mark.parametrize("configuration_state", ("missing", "invalid"))
def test_cli_rejects_missing_or_invalid_shared_configuration(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    configuration_state: str,
) -> None:
    from patchharbor_watcher import cli as watcher_cli

    set_isolated_user_environment(monkeypatch, tmp_path / "user")
    if configuration_state == "invalid":
        from patchharbor.user_paths import configuration_user_paths

        configuration_user_paths().configuration_path.write_text(
            "{}\n",
            encoding="utf-8",
        )
    stderr = StringIO()

    assert watcher_cli.main([], stdout=StringIO(), stderr=stderr) == 1
    assert "patchharbor-watcher:" in stderr.getvalue()
    assert (
        "configuration does not exist" in stderr.getvalue()
        if configuration_state == "missing"
        else "configuration must contain exactly" in stderr.getvalue()
    )


@pytest.mark.parametrize(
    "legacy_arguments",
    (
        ("/tmp/incoming",),
        ("--configure", "/tmp/incoming"),
    ),
)
def test_cli_rejects_removed_legacy_input_contract(
    legacy_arguments: tuple[str, ...],
) -> None:
    from patchharbor_watcher import cli as watcher_cli

    with pytest.raises(SystemExit) as captured:
        watcher_cli.main(legacy_arguments)

    assert captured.value.code == 2


def test_cli_help_exposes_only_shared_watcher_actions(
    capsys: pytest.CaptureFixture[str],
) -> None:
    from patchharbor_watcher import cli as watcher_cli

    with pytest.raises(SystemExit) as captured:
        watcher_cli.main(["--help"])

    assert captured.value.code == 0
    help_text = capsys.readouterr().out
    assert "--install-systemd-user-unit" in help_text
    assert "--poll-interval" in help_text
    assert "--configure" not in help_text
    assert "INPUT_DIRECTORY" not in help_text
