from __future__ import annotations

from io import StringIO
from pathlib import Path
import zipfile

import pytest

from patchharbor.errors import ExitCode, PatchHarborError
import patchharbor.input as script_input
from patchharbor.input import ScriptSource, discover_directory_candidates, run_script_path


REQUIRED_MARKER = "# PATCHHARBOR"


def _write_zip(path: Path, entries: list[tuple[str, str]]) -> None:
    with zipfile.ZipFile(path, "w") as archive:
        for name, content in entries:
            archive.writestr(name, content)


def _run_path(path: Path, cwd: Path, *, timeout_seconds: float = 1) -> int:
    return run_script_path(
        path,
        cwd=cwd,
        timeout_seconds=timeout_seconds,
        selection_input=StringIO(),
        selection_output=StringIO(),
    )


def test_directory_discovery_includes_zip_with_valid_script(tmp_path: Path) -> None:
    archive_path = tmp_path / "scripts.zip"
    _write_zip(
        archive_path,
        [("run.sh", f"{REQUIRED_MARKER}\n")],
    )

    candidates = discover_directory_candidates(tmp_path)

    assert [candidate.path for candidate in candidates] == [archive_path]


def test_zip_ignores_directories_links_and_nested_archives(tmp_path: Path) -> None:
    nested_path = tmp_path / "nested.zip"
    _write_zip(nested_path, [("nested.sh", f"{REQUIRED_MARKER}\n")])
    nested_bytes = nested_path.read_bytes()

    archive_path = tmp_path / "scripts.zip"
    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.writestr("folder/", "")
        link = zipfile.ZipInfo("linked.sh")
        link.create_system = 3
        link.external_attr = (0o120777 << 16)
        archive.writestr(link, f"{REQUIRED_MARKER}\n")
        archive.writestr("nested.zip", nested_bytes)

    with pytest.raises(PatchHarborError) as raised:
        _run_path(archive_path, tmp_path)

    assert raised.value.exit_code is ExitCode.NO_VALID_SCRIPT
    assert str(raised.value).startswith("no valid PatchHarbor scripts found")


@pytest.mark.parametrize(
    ("constant_name", "limit", "entries"),
    [
        (
            "MAX_ZIP_ENTRIES",
            1,
            [("one.txt", "1"), ("two.txt", "2")],
        ),
        (
            "MAX_ZIP_ENTRY_BYTES",
            4,
            [("large.txt", "12345")],
        ),
        (
            "MAX_ZIP_TOTAL_BYTES",
            8,
            [("one.txt", "12345"), ("two.txt", "67890")],
        ),
    ],
)
def test_zip_resource_budgets_fail_before_execution(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    constant_name: str,
    limit: int,
    entries: list[tuple[str, str]],
) -> None:
    archive_path = tmp_path / "limited.zip"
    _write_zip(archive_path, entries)
    monkeypatch.setattr(script_input, constant_name, limit)

    with pytest.raises(PatchHarborError) as raised:
        _run_path(archive_path, tmp_path)

    assert raised.value.exit_code is ExitCode.SOURCE_ERROR
    assert "ZIP archive exceeds resource limit" in str(raised.value)


def test_each_zip_script_receives_its_own_timeout(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    archive_path = tmp_path / "scripts.zip"
    _write_zip(
        archive_path,
        [
            ("first.sh", f"{REQUIRED_MARKER}\n"),
            ("second.sh", f"{REQUIRED_MARKER}\n"),
        ],
    )
    observed: list[tuple[ScriptSource, float]] = []

    def fake_run_script_source(
        source: ScriptSource,
        *,
        cwd: Path,
        timeout_seconds: float,
    ) -> int:
        observed.append((source, timeout_seconds))
        return 0

    monkeypatch.setattr(script_input, "run_script_source", fake_run_script_source)

    result = _run_path(archive_path, tmp_path, timeout_seconds=7.5)

    assert result == 0
    assert len(observed) == 2
    assert [timeout for _, timeout in observed] == [7.5, 7.5]
