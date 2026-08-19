from __future__ import annotations

import configparser
from io import StringIO
import os
from pathlib import Path
import sys

import pytest

from patchharbor import watcher_cli
from patchharbor.watcher_systemd import SYSTEMD_USER_UNIT_NAME
from tests.registration_support import set_isolated_user_environment


pytestmark = pytest.mark.skipif(
    os.name != "posix" or not sys.platform.startswith("linux"),
    reason="systemd user units are Linux-specific",
)


def _read_unit(path: Path) -> configparser.ConfigParser:
    parser = configparser.ConfigParser(interpolation=None)
    parser.optionxform = str
    parser.read_string(path.read_text(encoding="utf-8"))
    return parser


def test_cli_installs_disabled_journald_service_only_after_configuration(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
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

    incoming = tmp_path / "incoming"
    incoming.mkdir()
    assert watcher_cli.main(
        ["--configure", str(incoming)],
        stdout=StringIO(),
        stderr=StringIO(),
    ) == 0
    assert watcher_cli.main(
        ["--install-systemd-user-unit"],
        stdout=StringIO(),
        stderr=StringIO(),
    ) == 0

    unit = _read_unit(unit_path)
    assert unit["Service"]["Type"] == "simple"
    assert os.path.abspath(sys.executable) in unit["Service"]["ExecStart"]
    assert "-m patchharbor.watcher_cli" in unit["Service"]["ExecStart"]
    assert unit["Service"]["Restart"] == "on-failure"
    assert unit["Service"]["StandardOutput"] == "journal"
    assert unit["Service"]["StandardError"] == "journal"
    assert unit["Install"]["WantedBy"] == "default.target"
    assert not (
        unit_path.parent / "default.target.wants" / SYSTEMD_USER_UNIT_NAME
    ).exists()
    assert not tuple(unit_path.parent.glob("*.log"))
