from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from tests.platform_support import run_cli
from tests.registration_support import isolated_user_environment


pytestmark = pytest.mark.e2e


def _configuration_path(environment: dict[str, str]) -> Path:
    if os.name == "nt":
        return Path(environment["APPDATA"]) / "PatchHarbor" / "config.json"
    return Path(environment["XDG_CONFIG_HOME"]) / "patchharbor" / "config.json"


def test_configure_exchange_directory_and_show_use_the_same_file(
    tmp_path: Path,
) -> None:
    environment = isolated_user_environment(tmp_path / "user")
    exchange_directory = tmp_path / "downloads" / "exchange"

    configured = run_cli(
        tmp_path,
        "configure",
        "exchange-directory",
        str(exchange_directory),
        environment_overrides=environment,
    )

    configuration_path = _configuration_path(environment).resolve()
    canonical_exchange = exchange_directory.resolve()
    assert configured.returncode == 0
    assert configured.stderr == ""
    assert str(configuration_path) in configured.stdout
    assert str(canonical_exchange) in configured.stdout
    assert exchange_directory.is_dir()
    assert json.loads(configuration_path.read_text(encoding="utf-8")) == {
        "exchange_directory": str(canonical_exchange),
        "format_version": 1,
    }

    shown = run_cli(
        tmp_path,
        "configure",
        "show",
        environment_overrides=environment,
    )

    assert shown.returncode == 0
    assert shown.stderr == ""
    assert str(configuration_path) in shown.stdout
    assert str(canonical_exchange) in shown.stdout
