from __future__ import annotations

from pathlib import Path
import subprocess

import pytest

from patchharbor.errors import ExitCode, PatchHarborError
import patchharbor.execution as execution
from patchharbor.execution import execute_script_text


@pytest.mark.parametrize(
    ("shebang", "expected_executable", "expected_suffix", "power_shell"),
    (
        ("#!/bin/bash", "bash", ".sh", False),
        ("#!/usr/bin/bash", "bash", ".sh", False),
        ("#!/usr/bin/env bash", "bash", ".sh", False),
        ("#!powershell", "powershell.exe", ".ps1", True),
        ("#!powershell.exe", "powershell.exe", ".ps1", True),
        ("#!/usr/bin/env powershell", "powershell.exe", ".ps1", True),
        ("#!/usr/bin/env powershell.exe", "powershell.exe", ".ps1", True),
        ("#!pwsh", "pwsh", ".ps1", True),
        ("#!pwsh.exe", "pwsh", ".ps1", True),
        ("#!/usr/bin/pwsh", "pwsh", ".ps1", True),
        ("#!/usr/bin/env pwsh", "pwsh", ".ps1", True),
        ("#!/usr/bin/env pwsh.exe", "pwsh", ".ps1", True),
    ),
)
def test_supported_shebang_selects_expected_interpreter_command(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    shebang: str,
    expected_executable: str,
    expected_suffix: str,
    power_shell: bool,
) -> None:
    observed: list[tuple[list[str], Path]] = []

    def fake_which(executable: str) -> str:
        assert executable == expected_executable
        return f"/interpreters/{executable}"

    def fake_run(
        command: list[str],
        **kwargs: object,
    ) -> subprocess.CompletedProcess[str]:
        script_path = Path(command[-1])
        assert script_path.suffix == expected_suffix
        assert script_path.read_text(encoding="utf-8").startswith(shebang)
        observed.append((command, Path(kwargs["cwd"])))
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(execution.shutil, "which", fake_which)
    monkeypatch.setattr(execution.subprocess, "run", fake_run)

    result = execute_script_text(
        f"{shebang}\n# PATCHHARBOR\n",
        suffix=".irrelevant",
        cwd=tmp_path,
        timeout_seconds=7,
    )

    assert result == 0
    command, observed_cwd = observed[0]
    assert command[0] == f"/interpreters/{expected_executable}"
    assert observed_cwd == tmp_path
    if power_shell:
        assert command[1:-1] == [
            "-NoLogo",
            "-NoProfile",
            "-NonInteractive",
            "-File",
        ]
    else:
        assert len(command) == 2


def test_unknown_shebang_is_rejected_before_interpreter_lookup(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    lookup_called = False

    def fake_which(executable: str) -> str | None:
        nonlocal lookup_called
        lookup_called = True
        return None

    monkeypatch.setattr(execution.shutil, "which", fake_which)

    with pytest.raises(PatchHarborError) as raised:
        execute_script_text(
            "#!/usr/bin/env python3\n# PATCHHARBOR\n",
            suffix=".py",
            cwd=tmp_path,
            timeout_seconds=7,
        )

    assert raised.value.exit_code is ExitCode.INTERPRETER_ERROR
    assert str(raised.value) == (
        "unsupported script interpreter in shebang: /usr/bin/env python3"
    )
    assert not lookup_called


def test_missing_selected_interpreter_is_reported_before_process_start(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    process_started = False

    monkeypatch.setattr(execution.shutil, "which", lambda executable: None)

    def fail_if_started(*args: object, **kwargs: object) -> None:
        nonlocal process_started
        process_started = True
        raise AssertionError("process must not start")

    monkeypatch.setattr(execution.subprocess, "run", fail_if_started)

    with pytest.raises(PatchHarborError) as raised:
        execute_script_text(
            "#!/usr/bin/env bash\n# PATCHHARBOR\n",
            suffix=".sh",
            cwd=tmp_path,
            timeout_seconds=7,
        )

    assert raised.value.exit_code is ExitCode.INTERPRETER_ERROR
    assert str(raised.value) == "script interpreter not found: bash"
    assert not process_started
