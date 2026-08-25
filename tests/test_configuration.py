from __future__ import annotations

import json
from pathlib import Path

import pytest

from patchharbor.configuration import (
    load_configuration,
    write_exchange_directory,
)
from patchharbor.user_paths import registration_user_paths
from tests.registration_support import set_isolated_user_environment


def test_shared_configuration_round_trips_direct_file_edits(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    set_isolated_user_environment(monkeypatch, tmp_path / "user")
    paths = registration_user_paths()
    first_exchange = tmp_path / "first" / "exchange"

    written = write_exchange_directory(paths, first_exchange)

    assert written.exchange_directory == first_exchange.resolve()
    assert first_exchange.is_dir()
    assert json.loads(paths.configuration_path.read_text(encoding="utf-8")) == {
        "exchange_directory": str(first_exchange.resolve()),
        "format_version": 1,
    }

    second_exchange = tmp_path / "second-exchange"
    second_exchange.mkdir()
    paths.configuration_path.write_text(
        json.dumps(
            {
                "exchange_directory": str(second_exchange.resolve()),
                "format_version": 1,
            }
        )
        + "\n",
        encoding="utf-8",
    )

    loaded = load_configuration(paths)

    assert loaded.exchange_directory == second_exchange.resolve()
