from __future__ import annotations

from io import StringIO
from pathlib import Path

import pytest

from tests.registration_support import (
    isolated_user_environment,
    set_isolated_user_environment,
    legacy_user_configuration_path,
)


def test_cli_runs_the_global_repository_watcher(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from patchharbor_watcher import cli as watcher_cli

    environment = isolated_user_environment(tmp_path / "user")
    for name, value in environment.items():
        monkeypatch.setenv(name, value)
    observed: dict[str, object] = {}

    def fake_run_repository_watcher(
        **options: object,
    ) -> None:
        observed.update(options)

    monkeypatch.setattr(
        watcher_cli,
        "run_repository_watcher",
        fake_run_repository_watcher,
    )
    stdout = StringIO()
    stderr = StringIO()

    assert watcher_cli.main(
        ["--poll-interval", "0.25"],
        stdout=stdout,
        stderr=stderr,
    ) == 0
    assert observed["poll_interval_seconds"] == 0.25
    assert observed["delegate"] is watcher_cli.delegate_to_automatic_apply
    assert callable(observed["stop_requested"])
    assert callable(observed["wait_between_polls"])
    assert observed["log_stream"] is stdout
    assert observed["error_stream"] is stderr


@pytest.mark.parametrize("legacy_state", ("missing", "invalid"))
def test_watcher_ignores_legacy_global_configuration(tmp_path, monkeypatch, legacy_state):
    from patchharbor_watcher import cli as watcher_cli
    env = set_isolated_user_environment(monkeypatch, tmp_path / "user")
    env = isolated_user_environment(tmp_path / "user")
    old = legacy_user_configuration_path(env)
    if legacy_state == "invalid":
        old.parent.mkdir(parents=True, exist_ok=True)
        old.write_bytes(b"not-json")
    calls = []
    monkeypatch.setattr(watcher_cli, "run_repository_watcher", lambda **kwargs: calls.append(kwargs))
    assert watcher_cli.main([], stdout=StringIO(), stderr=StringIO()) == 0
    assert len(calls) == 1
    assert "exchange_directory" not in calls[0]
    assert old.read_bytes() == b"not-json" if legacy_state == "invalid" else not old.exists()


def test_watcher_rejects_invalid_registry_without_starting_loop(tmp_path, monkeypatch):
    from patchharbor_watcher import cli as watcher_cli
    from patchharbor.user_paths import registration_user_paths
    set_isolated_user_environment(monkeypatch, tmp_path / "user")
    paths = registration_user_paths()
    paths.registry_path.write_bytes(b"invalid")
    monkeypatch.setattr(watcher_cli, "run_repository_watcher", lambda **kw: pytest.fail("loop started"))
    assert watcher_cli.main([], stdout=StringIO(), stderr=StringIO()) == 1


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
