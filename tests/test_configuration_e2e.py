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


def test_configure_rejects_relative_exchange_directory(
    tmp_path: Path,
) -> None:
    environment = isolated_user_environment(tmp_path / "user")

    configured = run_cli(
        tmp_path,
        "configure",
        "exchange-directory",
        "relative-exchange",
        environment_overrides=environment,
    )

    assert configured.returncode == 4
    assert configured.stdout == ""
    assert configured.stderr == (
        "patchharbor: exchange directory must be an absolute path\n"
    )
    assert not _configuration_path(environment).exists()
    assert not (tmp_path / "relative-exchange").exists()


def test_configure_show_rejects_invalid_direct_file_edit(
    tmp_path: Path,
) -> None:
    environment = isolated_user_environment(tmp_path / "user")
    exchange_directory = tmp_path / "exchange"
    configured = run_cli(
        tmp_path,
        "configure",
        "exchange-directory",
        str(exchange_directory),
        environment_overrides=environment,
    )
    assert configured.returncode == 0
    configuration_path = _configuration_path(environment)
    invalid_content = {
        "exchange_directory": str(exchange_directory.resolve()),
        "format_version": 1,
        "future_field": "not format 1",
    }
    configuration_path.write_text(
        json.dumps(invalid_content) + "\n",
        encoding="utf-8",
    )

    shown = run_cli(
        tmp_path,
        "configure",
        "show",
        environment_overrides=environment,
    )

    assert shown.returncode == 4
    assert shown.stdout == ""
    assert shown.stderr == (
        "patchharbor: configuration must contain exactly the two "
        "format-1 fields\n"
    )
    assert json.loads(configuration_path.read_text(encoding="utf-8")) == (
        invalid_content
    )


def test_configure_rejects_exchange_inside_or_above_registered_repository(
    tmp_path: Path,
) -> None:
    from tests.registration_support import create_repository

    environment = isolated_user_environment(tmp_path / "user")
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    repository = create_repository(workspace / "repository")
    registered = run_cli(
        tmp_path,
        "register",
        str(repository),
        environment_overrides=environment,
    )
    assert registered.returncode == 0

    inside = repository / "exchange"
    inside_result = run_cli(
        tmp_path,
        "configure",
        "exchange-directory",
        str(inside),
        environment_overrides=environment,
    )
    assert inside_result.returncode == 4
    assert inside_result.stdout == ""
    assert inside_result.stderr == (
        "patchharbor: exchange directory overlaps a registered repository\n"
    )
    assert not inside.exists()
    assert not _configuration_path(environment).exists()

    parent = repository.parent
    parent_result = run_cli(
        tmp_path,
        "configure",
        "exchange-directory",
        str(parent),
        environment_overrides=environment,
    )
    assert parent_result.returncode == 4
    assert parent_result.stdout == ""
    assert parent_result.stderr == (
        "patchharbor: exchange directory overlaps a registered repository\n"
    )
    assert not _configuration_path(environment).exists()


def test_register_rejects_repository_overlapping_configured_exchange(
    tmp_path: Path,
) -> None:
    from tests.registration_support import create_repository

    environment = isolated_user_environment(tmp_path / "user")
    exchange = tmp_path / "exchange"
    configured = run_cli(
        tmp_path,
        "configure",
        "exchange-directory",
        str(exchange),
        environment_overrides=environment,
    )
    assert configured.returncode == 0

    repository = create_repository(exchange / "repository")
    registered = run_cli(
        tmp_path,
        "register",
        str(repository),
        environment_overrides=environment,
    )

    assert registered.returncode == 8
    assert registered.stdout == ""
    assert registered.stderr == (
        "patchharbor: repository overlaps configured exchange directory\n"
    )
    assert not (repository / ".patchharbor").exists()
