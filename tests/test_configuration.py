from __future__ import annotations

import errno
import json
import os
from pathlib import Path

import pytest

import patchharbor.platform.filesystem as filesystem_module
from patchharbor.configuration import (
    UserConfiguration,
    load_configuration,
    write_exchange_directory,
)
from patchharbor.errors import ErrorKind, ExitCode, PatchHarborError
from patchharbor.user_paths import (
    RegistrationUserPaths,
    configuration_user_paths,
    registration_user_paths,
)
from tests.registration_support import set_isolated_user_environment


def _isolated_paths(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> RegistrationUserPaths:
    set_isolated_user_environment(monkeypatch, tmp_path / "user")
    return registration_user_paths()


def _assert_configuration_error(
    paths: RegistrationUserPaths,
    *,
    message: str,
) -> PatchHarborError:
    with pytest.raises(PatchHarborError) as captured:
        load_configuration(paths)
    assert captured.value.exit_code is ExitCode.SOURCE_ERROR
    assert captured.value.error_kind is ErrorKind.CONFIGURATION_ERROR
    assert str(captured.value) == message
    return captured.value


def _write_document(
    paths: RegistrationUserPaths,
    document: object,
) -> None:
    paths.configuration_path.write_text(
        json.dumps(document, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def test_shared_configuration_round_trips_direct_file_edits(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    paths = _isolated_paths(tmp_path, monkeypatch)
    first_exchange = tmp_path / "first" / "exchange"

    written = write_exchange_directory(paths, first_exchange)

    assert written == UserConfiguration(first_exchange.resolve())
    assert first_exchange.is_dir()
    assert json.loads(paths.configuration_path.read_text(encoding="utf-8")) == {
        "exchange_directory": str(first_exchange.resolve()),
        "format_version": 1,
    }

    second_exchange = tmp_path / "second-exchange"
    second_exchange.mkdir()
    _write_document(
        paths,
        {
            "exchange_directory": str(second_exchange.resolve()),
            "format_version": 1,
        },
    )

    loaded = load_configuration(paths)

    assert loaded == UserConfiguration(second_exchange.resolve())


def test_written_configuration_is_exact_utf8_with_one_lf(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    paths = _isolated_paths(tmp_path, monkeypatch)
    exchange_directory = tmp_path / "Übergabe"

    configuration = write_exchange_directory(paths, exchange_directory)

    expected = (
        json.dumps(
            {
                "exchange_directory": str(exchange_directory.resolve()),
                "format_version": 1,
            },
            ensure_ascii=False,
            allow_nan=False,
            separators=(",", ":"),
        )
        + "\n"
    ).encode("utf-8")
    assert configuration.exchange_directory == exchange_directory.resolve()
    assert paths.configuration_path.read_bytes() == expected
    assert not tuple(paths.configuration_directory.glob(".patchharbor-*.tmp"))


def test_exchange_directory_is_physically_canonicalized(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    paths = _isolated_paths(tmp_path, monkeypatch)
    physical_directory = tmp_path / "physical"
    physical_directory.mkdir()
    alias = tmp_path / "alias"
    try:
        alias.symlink_to(physical_directory, target_is_directory=True)
    except OSError as exc:
        pytest.skip(f"directory symlinks are unavailable: {exc}")

    written = write_exchange_directory(paths, alias)
    _write_document(
        paths,
        {
            "exchange_directory": str(alias),
            "format_version": 1,
        },
    )
    loaded = load_configuration(paths)

    assert written.exchange_directory == physical_directory.resolve()
    assert loaded.exchange_directory == physical_directory.resolve()


@pytest.mark.parametrize(
    ("document", "message"),
    [
        (
            {"format_version": 1},
            "configuration must contain exactly the two format-1 fields",
        ),
        (
            {
                "exchange_directory": "/missing",
                "format_version": 1,
                "future_field": True,
            },
            "configuration must contain exactly the two format-1 fields",
        ),
        (
            {"exchange_directory": "/missing", "format_version": True},
            "configuration format_version is invalid",
        ),
        (
            {"exchange_directory": "/missing", "format_version": 1.0},
            "configuration format_version is invalid",
        ),
        (
            {"exchange_directory": "/missing", "format_version": 2},
            "configuration format_version is invalid",
        ),
        (
            {"exchange_directory": 7, "format_version": 1},
            "configuration exchange_directory is invalid",
        ),
        (
            {"exchange_directory": "relative/exchange", "format_version": 1},
            "exchange directory must be an absolute path",
        ),
    ],
    ids=(
        "missing-field",
        "unknown-field-before-path",
        "boolean-version-before-path",
        "float-version-before-path",
        "unsupported-version-before-path",
        "path-type-before-path",
        "relative-path",
    ),
)
def test_closed_schema_rejects_distinct_direct_edits(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    document: object,
    message: str,
) -> None:
    paths = _isolated_paths(tmp_path, monkeypatch)
    _write_document(paths, document)

    _assert_configuration_error(paths, message=message)


@pytest.mark.parametrize(
    ("content", "message"),
    [
        (
            b"\xef\xbb\xbf{}",
            "configuration must be UTF-8 without a BOM",
        ),
        (b"\xff", "configuration is not valid UTF-8"),
        (b"[]\n", "configuration must contain one JSON object"),
        (
            b'{"format_version":1,"format_version":1}\n',
            "configuration is not one valid JSON object",
        ),
        (
            b'{"format_version":NaN}\n',
            "configuration is not one valid JSON object",
        ),
        (
            b'{"format_version":1}{}',
            "configuration is not one valid JSON object",
        ),
    ],
    ids=(
        "bom",
        "invalid-utf8",
        "non-object",
        "duplicate-key",
        "non-finite-number",
        "trailing-document",
    ),
)
def test_json_contract_rejects_ambiguous_direct_edits(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    content: bytes,
    message: str,
) -> None:
    paths = _isolated_paths(tmp_path, monkeypatch)
    paths.configuration_path.write_bytes(content)

    _assert_configuration_error(paths, message=message)


def test_direct_configuration_requires_an_existing_directory(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    paths = _isolated_paths(tmp_path, monkeypatch)
    missing_directory = tmp_path / "missing"
    _write_document(
        paths,
        {
            "exchange_directory": str(missing_directory.resolve()),
            "format_version": 1,
        },
    )

    _assert_configuration_error(
        paths,
        message="exchange directory does not exist",
    )

    regular_file = tmp_path / "regular-file"
    regular_file.write_text("not a directory", encoding="utf-8")
    _write_document(
        paths,
        {
            "exchange_directory": str(regular_file.resolve()),
            "format_version": 1,
        },
    )

    _assert_configuration_error(
        paths,
        message="exchange directory is not a directory",
    )


def test_configure_rejects_relative_path_without_side_effects(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    paths = _isolated_paths(tmp_path, monkeypatch)
    relative_directory = Path("relative-exchange")

    with pytest.raises(PatchHarborError) as captured:
        write_exchange_directory(paths, relative_directory)

    assert captured.value.exit_code is ExitCode.SOURCE_ERROR
    assert captured.value.error_kind is ErrorKind.CONFIGURATION_ERROR
    assert str(captured.value) == "exchange directory must be an absolute path"
    assert not paths.configuration_path.exists()
    assert not relative_directory.exists()


def test_configuration_target_is_checked_before_exchange_creation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    paths = _isolated_paths(tmp_path, monkeypatch)
    paths.configuration_path.mkdir()
    exchange_directory = tmp_path / "not-created"

    with pytest.raises(PatchHarborError) as captured:
        write_exchange_directory(paths, exchange_directory)

    assert captured.value.exit_code is ExitCode.SOURCE_ERROR
    assert captured.value.error_kind is ErrorKind.CONFIGURATION_ERROR
    assert str(captured.value) == "configuration must be a regular file"
    assert not exchange_directory.exists()


def test_atomic_replace_failure_preserves_previous_configuration(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    paths = _isolated_paths(tmp_path, monkeypatch)
    first_exchange = tmp_path / "first"
    write_exchange_directory(paths, first_exchange)
    previous_content = paths.configuration_path.read_bytes()
    second_exchange = tmp_path / "second"

    def reject_replace(_source: object, _target: object) -> None:
        raise OSError(errno.EACCES, "native platform wording")

    monkeypatch.setattr(filesystem_module.os, "replace", reject_replace)

    with pytest.raises(PatchHarborError) as captured:
        write_exchange_directory(paths, second_exchange)

    assert captured.value.exit_code is ExitCode.SOURCE_ERROR
    assert captured.value.error_kind is ErrorKind.CONFIGURATION_ERROR
    assert str(captured.value) == "cannot write configuration: permission denied"
    assert paths.configuration_path.read_bytes() == previous_content
    assert second_exchange.is_dir()
    assert not tuple(paths.configuration_directory.glob(".patchharbor-*.tmp"))


def test_configuration_user_path_failures_have_their_own_category(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    if os.name == "nt":
        monkeypatch.delenv("APPDATA", raising=False)
        monkeypatch.delenv("LOCALAPPDATA", raising=False)
    else:
        monkeypatch.delenv("HOME", raising=False)

    with pytest.raises(PatchHarborError) as captured:
        configuration_user_paths()

    assert captured.value.exit_code is ExitCode.SOURCE_ERROR
    assert captured.value.error_kind is ErrorKind.CONFIGURATION_ERROR
    assert "required for configuration" in str(captured.value)
