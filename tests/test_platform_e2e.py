from __future__ import annotations

from collections.abc import Mapping
import os
from pathlib import Path
import subprocess
import sys
import zipfile

import pytest

from tests.platform_support import REQUIRES_POWERSHELL_7


PROJECT_ROOT = Path(__file__).resolve().parents[1]
REQUIRED_MARKER = "# PATCHHARBOR"


def _environment(
    overrides: Mapping[str, str] | None = None,
) -> dict[str, str]:
    environment = os.environ.copy()
    source_path = str(PROJECT_ROOT / "src")
    existing_pythonpath = environment.get("PYTHONPATH")
    environment["PYTHONPATH"] = (
        source_path
        if not existing_pythonpath
        else os.pathsep.join((source_path, existing_pythonpath))
    )
    if overrides:
        environment.update(overrides)
    return environment


def _run_patchharbor(
    source_path: Path,
    *,
    cwd: Path,
    environment_overrides: Mapping[str, str] | None = None,
    arguments: tuple[str, ...] = (),
    timeout_seconds: float = 20,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            "-m",
            "patchharbor.cli",
            "fs",
            "run",
            *arguments,
            str(source_path),
        ],
        cwd=cwd,
        env=_environment(environment_overrides),
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        timeout=timeout_seconds,
        check=False,
    )


def _platform_body(bash_body: str, powershell_body: str) -> str:
    return powershell_body if os.name == "nt" else bash_body


def _platform_script(bash_body: str, powershell_body: str) -> str:
    return f"{REQUIRED_MARKER}\n{_platform_body(bash_body, powershell_body)}\n"


def _normalized_path(path: str | Path) -> str:
    return os.path.normcase(os.path.abspath(os.fspath(path)))


def _log_path(stderr: str) -> Path:
    prefix = "patchharbor: log: "
    matching = [line for line in stderr.splitlines() if line.startswith(prefix)]
    assert matching, stderr
    return Path(matching[-1].removeprefix(prefix))


def test_platform_default_interpreter_ignores_filename_extension(
    tmp_path: Path,
) -> None:
    source_path = tmp_path / ("default.sh" if os.name == "nt" else "default.ps1")
    source_path.write_text(
        _platform_script(
            'printf "%s\\n" "bash-default"',
            '[Console]::Out.WriteLine("powershell-default")',
        ),
        encoding="utf-8",
    )

    completed = _run_patchharbor(source_path, cwd=tmp_path)

    assert completed.returncode == 0
    expected = "powershell-default\n" if os.name == "nt" else "bash-default\n"
    assert completed.stdout == expected
    assert completed.stderr == ""


def test_platform_uses_system_temp_for_staging_and_requested_cwd(
    tmp_path: Path,
) -> None:
    working_directory = tmp_path / "working directory"
    system_temp = tmp_path / "system temp"
    working_directory.mkdir()
    system_temp.mkdir()
    source_path = tmp_path / "downloaded-script.data"
    source_path.write_text(
        _platform_script(
            "pwd -P > observed-cwd.txt\nprintf '%s' \"$0\" > observed-script.txt",
            (
                '[IO.File]::WriteAllText("observed-cwd.txt", '
                '(Get-Location).Path)\n'
                '[IO.File]::WriteAllText("observed-script.txt", $PSCommandPath)'
            ),
        ),
        encoding="utf-8",
    )
    temp_environment = {
        "TMPDIR": str(system_temp),
        "TEMP": str(system_temp),
        "TMP": str(system_temp),
    }

    completed = _run_patchharbor(
        source_path,
        cwd=working_directory,
        environment_overrides=temp_environment,
    )

    assert completed.returncode == 0
    assert completed.stdout == ""
    assert completed.stderr == ""
    observed_cwd = (working_directory / "observed-cwd.txt").read_text(
        encoding="utf-8"
    ).strip()
    observed_script = (working_directory / "observed-script.txt").read_text(
        encoding="utf-8"
    ).strip()
    assert _normalized_path(observed_cwd) == _normalized_path(working_directory)
    assert _normalized_path(Path(observed_script).parent) == _normalized_path(
        system_temp
    )
    assert not Path(observed_script).exists()


def test_platform_inline_file_is_available_before_script_execution(
    tmp_path: Path,
) -> None:
    source_path = tmp_path / "inline-payload.txt"
    body = _platform_body(
        (
            '[ "$(cat platform.txt)" = "platform-data" ] || exit 41\n'
            'printf "%s\\n" "inline-ok"'
        ),
        (
            'if ([IO.File]::ReadAllText("platform.txt") -ne '
            '"platform-data") { exit 41 }\n'
            '[Console]::Out.WriteLine("inline-ok")'
        ),
    )
    source_path.write_text(
        f"{REQUIRED_MARKER}\n"
        "# PATCHHARBOR FILE platform.txt START\n"
        "# platform-data\n"
        "# PATCHHARBOR FILE platform.txt END\n"
        f"{body}\n",
        encoding="utf-8",
    )

    completed = _run_patchharbor(source_path, cwd=tmp_path)

    assert completed.returncode == 0
    assert completed.stdout == "inline-ok\n"
    assert completed.stderr == ""
    assert (tmp_path / "platform.txt").read_text(encoding="utf-8") == (
        "platform-data"
    )


def test_platform_zip_patchbundle_preserves_binary_payload(
    tmp_path: Path,
) -> None:
    archive_path = tmp_path / "platform-bundle.zip"
    binary_payload = bytes((0, 1, 2, 127, 128, 255)) + b"PATCHHARBOR"
    if os.name == "nt":
        script_name = "apply.ps1"
        script = (
            f"{REQUIRED_MARKER}\n"
            '$actual = [Convert]::ToBase64String('
            '[IO.File]::ReadAllBytes("assets/blob.bin"))\n'
            'if ($actual -ne "AAECf4D/UEFUQ0hIQVJCT1I=") { exit 42 }\n'
            '[Console]::Out.WriteLine("bundle-ok")\n'
        )
    else:
        script_name = "apply.sh"
        script = (
            f"{REQUIRED_MARKER}\n"
            'actual="$(base64 < assets/blob.bin | tr -d "\\n")"\n'
            '[ "$actual" = "AAECf4D/UEFUQ0hIQVJCT1I=" ] || exit 42\n'
            'printf "%s\\n" "bundle-ok"\n'
        )
    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.writestr(script_name, script)
        archive.writestr("assets/blob.bin", binary_payload)

    completed = _run_patchharbor(archive_path, cwd=tmp_path)

    assert completed.returncode == 0
    assert completed.stdout == "bundle-ok\n"
    assert completed.stderr == ""
    assert (tmp_path / "assets" / "blob.bin").read_bytes() == binary_payload


def test_platform_timeout_returns_124(tmp_path: Path) -> None:
    source_path = tmp_path / "timeout-script.data"
    source_path.write_text(
        _platform_script(
            "sleep 30",
            "Start-Sleep -Seconds 30",
        ),
        encoding="utf-8",
    )

    completed = _run_patchharbor(
        source_path,
        cwd=tmp_path,
        arguments=("--timeout", "0.2"),
    )

    assert completed.returncode == 124
    assert completed.stdout == ""
    assert completed.stderr == (
        "patchharbor: script timed out after 0.2 seconds\n"
    )


def test_platform_log_uses_configured_system_temp_and_contains_output(
    tmp_path: Path,
) -> None:
    system_temp = tmp_path / "log temp"
    system_temp.mkdir()
    source_path = tmp_path / "logged-script.data"
    source_path.write_text(
        _platform_script(
            'printf "%s\\n" "platform-log"',
            '[Console]::Out.WriteLine("platform-log")',
        ),
        encoding="utf-8",
    )
    temp_environment = {
        "TMPDIR": str(system_temp),
        "TEMP": str(system_temp),
        "TMP": str(system_temp),
    }

    completed = _run_patchharbor(
        source_path,
        cwd=tmp_path,
        environment_overrides=temp_environment,
        arguments=("--log",),
    )

    assert completed.returncode == 0
    assert completed.stdout == "platform-log\n"
    log_path = _log_path(completed.stderr)
    try:
        assert _normalized_path(log_path.parent) == _normalized_path(system_temp)
        log_bytes = log_path.read_bytes()
        assert b"platform-log\n" in log_bytes
        assert b"exit_code: 0\n" in log_bytes
    finally:
        log_path.unlink(missing_ok=True)


@REQUIRES_POWERSHELL_7
def test_platform_powershell_7_shebang_executes_when_available(
    tmp_path: Path,
) -> None:
    source_path = tmp_path / "powershell-seven.data"
    source_path.write_text(
        "#!/usr/bin/env pwsh\n"
        f"{REQUIRED_MARKER}\n"
        '[Console]::Out.WriteLine("pwsh-seven")\n',
        encoding="utf-8",
    )

    completed = _run_patchharbor(source_path, cwd=tmp_path)

    assert completed.returncode == 0
    assert completed.stdout == "pwsh-seven\n"
    assert completed.stderr == ""
