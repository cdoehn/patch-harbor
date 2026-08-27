from __future__ import annotations

import configparser
from io import StringIO
import os
from pathlib import Path
import sys

import pytest

from patchharbor_watcher import cli as watcher_cli
from tests.registration_support import (
    isolated_user_environment,
    set_isolated_user_environment,
    write_exchange_configuration,
)


IS_LINUX = os.name == "posix" and sys.platform.startswith("linux")


def _read_unit(path: Path) -> configparser.ConfigParser:
    parser = configparser.ConfigParser(interpolation=None)
    parser.optionxform = str
    parser.read_string(path.read_text(encoding="utf-8"))
    return parser


def test_non_linux_action_rejects_systemd_without_loading_linux_module(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    environment = isolated_user_environment(tmp_path / "user")
    for name, value in environment.items():
        monkeypatch.setenv(name, value)
    write_exchange_configuration(environment, tmp_path / "exchange")

    sys.modules.pop("patchharbor_watcher.systemd_linux", None)
    monkeypatch.setattr(watcher_cli.sys, "platform", "win32")

    assert watcher_cli.main(
        ["--install-systemd-user-unit"],
        stdout=StringIO(),
        stderr=StringIO(),
    ) == 1
    assert "patchharbor_watcher.systemd_linux" not in sys.modules


@pytest.mark.skipif(not IS_LINUX, reason="systemd user units are Linux-specific")
def test_cli_installs_disabled_journald_service_only_after_configuration(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from patchharbor_watcher.systemd_linux import SYSTEMD_USER_UNIT_NAME

    set_isolated_user_environment(monkeypatch, tmp_path / "user")
    unit_path = (
        Path(os.environ["XDG_CONFIG_HOME"])
        / "systemd"
        / "user"
        / SYSTEMD_USER_UNIT_NAME
    ).resolve()

    assert watcher_cli.main(
        ["--install-systemd-user-unit"],
        stdout=StringIO(),
        stderr=StringIO(),
    ) == 1
    assert not unit_path.exists()

    environment = isolated_user_environment(tmp_path / "user")
    write_exchange_configuration(environment, tmp_path / "exchange")
    assert watcher_cli.main(
        ["--install-systemd-user-unit"],
        stdout=StringIO(),
        stderr=StringIO(),
    ) == 0

    unit = _read_unit(unit_path)
    assert unit["Service"]["Type"] == "simple"
    assert os.path.abspath(sys.executable) in unit["Service"]["ExecStart"]
    exec_start = unit["Service"]["ExecStart"]
    assert "-m patchharbor_watcher.cli" in exec_start
    assert "--configure" not in exec_start
    assert "INPUT_DIRECTORY" not in exec_start
    assert unit["Service"]["Restart"] == "on-failure"
    assert unit["Service"]["StandardOutput"] == "journal"
    assert unit["Service"]["StandardError"] == "journal"
    assert unit["Install"]["WantedBy"] == "default.target"
    assert not (
        unit_path.parent / "default.target.wants" / SYSTEMD_USER_UNIT_NAME
    ).exists()
    assert not tuple(unit_path.parent.glob("*.log"))
