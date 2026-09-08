from __future__ import annotations

import errno
import json
from pathlib import Path

import pytest

from patchharbor.application import configure_bundle_suffix, configure_exchange_directory
from patchharbor.bundle_names import append_bundle_suffix, validate_bundle_suffix
from patchharbor.configuration import load_configuration, write_exchange_directory
from patchharbor.errors import ErrorKind, PatchHarborError, ExitCode
from patchharbor.user_paths import registration_user_paths
from tests.registration_support import set_isolated_user_environment


@pytest.fixture
def paths(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    set_isolated_user_environment(monkeypatch, tmp_path / "user")
    return registration_user_paths()


@pytest.mark.parametrize("suffix", ["", ".txt", ".TXT", "-copilot.txt", "_data", ".tar.txt", "x" * 32])
def test_suffix_is_literal_and_only_changes_outer_name(suffix: str) -> None:
    assert validate_bundle_suffix(suffix) == suffix
    for kind in ("Patch", "Result"):
        name = f"repository_{kind}_120000_0908_abcdef.zip"
        assert append_bundle_suffix(name, suffix) == name + suffix


@pytest.mark.parametrize("suffix", [
    None, True, 7, [], {}, ".", "..", "...", "___", "--", ".txt.",
    ".x..txt", "../x", "/txt", "\\txt", "a/b", "a\\b", ":txt", ".txt ",
    " .txt", ".t xt", "\n", "\x00", "é", "x" * 33,
    ".part", ".PART", ".partial", ".download", ".crdownload", ".opdownload", ".tmp",
    ".txt.crdownload",
])
def test_suffix_rejects_unsafe_or_undiscoverable_values(suffix: object) -> None:
    with pytest.raises(ValueError):
        validate_bundle_suffix(suffix)


def test_appending_requires_an_unsuffixed_zip_base() -> None:
    with pytest.raises(ValueError):
        append_bundle_suffix("bundle.zip.txt", ".txt")


def test_legacy_configuration_is_read_only_until_explicit_write(paths, tmp_path: Path) -> None:
    exchange = tmp_path / "exchange"
    exchange.mkdir()
    original = json.dumps({"format_version": 1, "exchange_directory": str(exchange.resolve())}).encode()
    paths.configuration_path.write_bytes(original)
    assert load_configuration(paths).bundle_suffix == ""
    assert paths.configuration_path.read_bytes() == original
    configure_bundle_suffix(".txt")
    assert json.loads(paths.configuration_path.read_bytes()) == {
        "format_version": 2, "exchange_directory": str(exchange.resolve()), "bundle_suffix": ".txt",
    }
    assert load_configuration(paths).bundle_suffix == ".txt"
    configure_bundle_suffix("")
    assert load_configuration(paths).bundle_suffix == ""


def test_setting_either_option_preserves_the_other(paths, tmp_path: Path) -> None:
    first = tmp_path / "first"
    write_exchange_directory(paths, first)
    configure_bundle_suffix(".txt")
    assert load_configuration(paths).exchange_directory == first.resolve()
    second = tmp_path / "second"
    configure_exchange_directory(second)
    assert load_configuration(paths).exchange_directory == second.resolve()
    assert load_configuration(paths).bundle_suffix == ".txt"
    # A vanished old Exchange must still be repairable without losing the suffix.
    second.rmdir()
    configure_exchange_directory(first)
    assert load_configuration(paths).bundle_suffix == ".txt"


def test_suffix_requires_existing_exchange_configuration(paths) -> None:
    with pytest.raises(PatchHarborError, match="configuration does not exist"):
        configure_bundle_suffix(".txt")
    assert not paths.configuration_path.exists()


@pytest.mark.parametrize("suffix", [None, False, 17, "/unsafe", ".txt\n", ".part"])
def test_format_two_validates_suffix_before_directory(paths, suffix: object) -> None:
    paths.configuration_path.write_text(json.dumps({
        "format_version": 2, "exchange_directory": "/missing", "bundle_suffix": suffix,
    }))
    with pytest.raises(PatchHarborError) as captured:
        load_configuration(paths)
    assert captured.value.error_kind is ErrorKind.CONFIGURATION_ERROR
    assert "bundle suffix" in str(captured.value)


@pytest.mark.parametrize("document", [
    {"format_version": 2, "exchange_directory": "/missing"},
    {"format_version": 2, "exchange_directory": "/missing", "bundle_suffix": "", "extra": 0},
    {"format_version": 1, "exchange_directory": "/missing", "bundle_suffix": ""},
])
def test_both_configuration_versions_remain_closed(paths, document) -> None:
    paths.configuration_path.write_text(json.dumps(document))
    with pytest.raises(PatchHarborError, match="exactly"):
        load_configuration(paths)


def test_duplicate_suffix_field_is_not_accepted(paths) -> None:
    paths.configuration_path.write_text(
        '{"format_version":2,"exchange_directory":"/missing","bundle_suffix":".txt","bundle_suffix":""}'
    )
    with pytest.raises(PatchHarborError, match="one valid JSON object"):
        load_configuration(paths)


def test_failed_suffix_write_preserves_previous_bytes(paths, tmp_path: Path, monkeypatch) -> None:
    import patchharbor.platform.filesystem as filesystem
    write_exchange_directory(paths, tmp_path / "exchange")
    configure_bundle_suffix(".txt")
    original = paths.configuration_path.read_bytes()
    def fail_replace(*args):
        raise OSError(errno.EACCES, "denied")
    monkeypatch.setattr(filesystem.os, "replace", fail_replace)
    with pytest.raises(PatchHarborError, match="cannot write configuration"):
        configure_bundle_suffix(".data")
    assert paths.configuration_path.read_bytes() == original
    assert not tuple(paths.configuration_directory.glob(".patchharbor-*.tmp"))


def test_invalid_cli_value_never_overwrites_existing_configuration(paths, tmp_path: Path) -> None:
    write_exchange_directory(paths, tmp_path / "exchange")
    original = paths.configuration_path.read_bytes()
    with pytest.raises(PatchHarborError, match="bundle suffix"):
        configure_bundle_suffix("../unsafe")
    assert paths.configuration_path.read_bytes() == original


def test_suffix_update_holds_shared_lock(paths, tmp_path: Path, monkeypatch) -> None:
    import patchharbor.application as application
    from tests.platform_support import project_environment
    from tests.registration_support import probe_registry_lock
    write_exchange_directory(paths, tmp_path / "exchange")
    original = application.write_prepared_configuration
    def write_under_lock(*args):
        assert probe_registry_lock(project_environment()) == int(ExitCode.REPOSITORY_ERROR)
        return original(*args)
    monkeypatch.setattr(application, "write_prepared_configuration", write_under_lock)
    configure_bundle_suffix(".txt")


def test_suffix_documentation_carries_full_chat_and_configuration_contract() -> None:
    root = Path(__file__).resolve().parents[1]
    for name in ("README.md", "CHAT_INSTRUCTIONS.md", "spec/SPECIFICATION.md"):
        text = (root / name).read_text(encoding="utf-8")
        assert "patchharbor configure bundle-suffix .txt" in text
        assert "patchharbor configure bundle-suffix --clear" in text
        assert "bundle_suffix" in text
        assert ".zip.txt" in text
        assert "context.json" in text
        assert "patch.json" in text
    cli = (root / "src/patchharbor/cli.py").read_text(encoding="utf-8")
    assert '"bundle-suffix"' in cli
