"""Cross-platform acceptance scenarios for the public PatchHarbor workflow."""

from __future__ import annotations

import os
from pathlib import Path
import zipfile

import pytest

from tests.platform_support import (
    IS_WINDOWS,
    REQUIRED_MARKER,
    log_path_from_stderr,
    native_script,
    native_value,
    run_cli,
)


pytestmark = pytest.mark.acceptance


def _script_path(directory: Path, stem: str) -> Path:
    return directory / f"{stem}{native_value('.sh', '.ps1')}"


def _output_script(value: str, *, exit_code: int = 0) -> str:
    return native_script(
        f'printf "%s\\n" "{value}"\nexit {exit_code}',
        f'Write-Output "{value}"\nexit {exit_code}',
    )


def test_acceptance_direct_script_message_plain_output_and_log(
    tmp_path: Path,
) -> None:
    script_path = _script_path(tmp_path, "direct-workflow")
    script_body = native_value(
        'printf "%s\n" "direct-accepted"',
        'Write-Output "direct-accepted"',
    )
    script_path.write_text(
        "\n".join(
            (
                REQUIRED_MARKER,
                "# PATCHHARBOR MESSAGE summary START",
                "# Acceptance run with one informational message.",
                "# PATCHHARBOR MESSAGE summary END",
                script_body,
                "",
            )
        ),
        encoding="utf-8",
    )

    completed = run_cli(
        tmp_path,
        "fs",
        "run",
        "--plain",
        "--no-color",
        "--log",
        str(script_path),
    )

    assert isinstance(completed.stdout, str)
    assert isinstance(completed.stderr, str)
    assert completed.returncode == 0
    assert completed.stdout == "direct-accepted\n"

    log_path = log_path_from_stderr(completed.stderr)
    try:
        log_text = log_path.read_text(encoding="utf-8")
        assert "direct-accepted\n" in log_text
        assert "exit_code: 0\n" in log_text
    finally:
        log_path.unlink(missing_ok=True)


def test_acceptance_directory_selection_uses_displayed_index(tmp_path: Path) -> None:
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    newest = _script_path(inbox, "newest")
    older = _script_path(inbox, "older")
    newest.write_text(_output_script("newest"), encoding="utf-8")
    older.write_text(_output_script("older"), encoding="utf-8")
    os.utime(newest, ns=(200, 200))
    os.utime(older, ns=(100, 100))

    completed = run_cli(
        tmp_path,
        "fs",
        "run",
        str(inbox),
        input_text="2\n",
    )

    assert isinstance(completed.stdout, str)
    assert isinstance(completed.stderr, str)
    assert completed.returncode == 0
    assert f"1 {newest.name}" in completed.stdout
    assert f"2 {older.name}" in completed.stdout
    assert completed.stdout.endswith("older\n")
    assert completed.stderr == ""


def test_acceptance_zip_bundle_transfers_binary_and_runs_scripts_in_order(
    tmp_path: Path,
) -> None:
    archive_path = tmp_path / "bundle.zip"
    binary_payload = b"\x00PatchHarbor\xff\x10"
    first_script = native_script(
        '[ -f assets/blob.bin ] || exit 41\n'
        'printf "%s\\n" first >> order.txt',
        'if (-not (Test-Path -LiteralPath "assets/blob.bin" -PathType Leaf)) '
        '{ exit 41 }\nAdd-Content -LiteralPath "order.txt" -Value "first" '
        '-Encoding UTF8',
    )
    second_script = native_script(
        'printf "%s\\n" second >> order.txt',
        'Add-Content -LiteralPath "order.txt" -Value "second" '
        '-Encoding UTF8',
    )
    first_name = native_value("10-first.sh", "10-first.ps1")
    second_name = native_value("20-second.sh", "20-second.ps1")

    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.writestr(first_name, first_script)
        archive.writestr("assets/blob.bin", binary_payload)
        archive.writestr(second_name, second_script)

    completed = run_cli(tmp_path, "fs", "run", str(archive_path))

    assert isinstance(completed.stdout, str)
    assert isinstance(completed.stderr, str)
    assert completed.returncode == 0
    assert completed.stdout == ""
    assert completed.stderr == ""
    assert (tmp_path / "assets" / "blob.bin").read_bytes() == binary_payload
    assert (tmp_path / "order.txt").read_text(encoding="utf-8-sig").splitlines() == [
        "first",
        "second",
    ]


def test_acceptance_pipe_runs_direct_script(tmp_path: Path) -> None:
    completed = run_cli(
        tmp_path,
        "fs",
        "run",
        input_text=_output_script("pipe-accepted"),
    )

    assert isinstance(completed.stdout, str)
    assert isinstance(completed.stderr, str)
    assert completed.returncode == 0
    assert completed.stdout == "pipe-accepted\n"
    assert completed.stderr == ""


def test_acceptance_timeout_returns_124(tmp_path: Path) -> None:
    script_path = _script_path(tmp_path, "timeout")
    script_path.write_text(
        native_script(
            "while :; do :; done",
            "while ($true) {}",
        ),
        encoding="utf-8",
    )

    completed = run_cli(
        tmp_path,
        "fs",
        "run",
        "--timeout",
        "0.05",
        str(script_path),
    )

    assert completed.returncode == 124


def test_acceptance_script_exit_code_is_forwarded(tmp_path: Path) -> None:
    script_path = _script_path(tmp_path, "exit-code")
    script_path.write_text(_output_script("failed", exit_code=23), encoding="utf-8")

    completed = run_cli(tmp_path, "fs", "run", str(script_path))

    assert isinstance(completed.stdout, str)
    assert isinstance(completed.stderr, str)
    assert completed.returncode == 23
    assert completed.stdout == "failed\n"
    assert completed.stderr == ""


@pytest.mark.skipif(not IS_WINDOWS, reason="requires a real Windows runner")
def test_acceptance_windows_runner_uses_windows_powershell(tmp_path: Path) -> None:
    script_path = tmp_path / "windows-powershell.txt"
    script_path.write_text(
        native_script("", 'Write-Output "windows-powershell"'),
        encoding="utf-8",
    )

    completed = run_cli(tmp_path, "fs", "run", str(script_path))

    assert completed.returncode == 0
    assert completed.stdout == "windows-powershell\n"


@pytest.mark.skipif(not IS_WINDOWS, reason="requires a real Windows runner")
def test_acceptance_windows_runner_uses_powershell_7(tmp_path: Path) -> None:
    script_path = tmp_path / "powershell-seven.txt"
    script_path.write_text(
        "#!/usr/bin/env pwsh\n"
        f"{REQUIRED_MARKER}\n"
        'Write-Output "powershell-seven"\n',
        encoding="utf-8",
    )

    completed = run_cli(tmp_path, "fs", "run", str(script_path))

    assert completed.returncode == 0
    assert completed.stdout == "powershell-seven\n"
