from __future__ import annotations

from pathlib import Path
import subprocess

import pytest

from patchharbor.errors import ExitCode, PatchHarborError
import patchharbor.execution as execution
from patchharbor.execution import execute_script_text
import patchharbor.interpreters as interpreters


def test_execution_stages_with_selected_technical_suffix_and_ignores_source_suffix(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed: list[tuple[list[str], Path]] = []

    monkeypatch.setattr(
        interpreters.shutil,
        "which",
        lambda executable: f"/interpreters/{executable}",
    )

    def fake_run(
        command: list[str],
        **kwargs: object,
    ) -> subprocess.CompletedProcess[str]:
        script_path = Path(command[-1])
        assert script_path.suffix == ".sh"
        assert script_path.read_text(encoding="utf-8").startswith(
            "#!/usr/bin/env bash"
        )
        observed.append((command, Path(kwargs["cwd"])))
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(execution.subprocess, "run", fake_run)

    result = execute_script_text(
        "#!/usr/bin/env bash\n# PATCHHARBOR\n",
        suffix=".ps1",
        cwd=tmp_path,
        timeout_seconds=7,
    )

    assert result == 0
    assert len(observed) == 1
    command, observed_cwd = observed[0]
    assert command[0] == "/interpreters/bash"
    assert Path(command[-1]).suffix == ".sh"
    assert observed_cwd == tmp_path


def test_interpreter_selection_error_happens_before_process_start(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    process_started = False

    def fail_if_started(*args: object, **kwargs: object) -> None:
        nonlocal process_started
        process_started = True
        raise AssertionError("process must not start")

    monkeypatch.setattr(execution.subprocess, "run", fail_if_started)

    with pytest.raises(PatchHarborError) as raised:
        execute_script_text(
            "#!/usr/bin/env python3\n# PATCHHARBOR\n",
            suffix=".py",
            cwd=tmp_path,
            timeout_seconds=7,
        )

    assert raised.value.exit_code is ExitCode.INTERPRETER_ERROR
    assert not process_started


def test_missing_selected_interpreter_happens_before_process_start(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    process_started = False
    monkeypatch.setattr(interpreters.shutil, "which", lambda executable: None)

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


def test_nonzero_powershell_result_is_returned_without_policy_bypass(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed_command: list[str] = []
    monkeypatch.setattr(
        interpreters.shutil,
        "which",
        lambda executable: f"/interpreters/{executable}",
    )

    def fake_run(
        command: list[str],
        **kwargs: object,
    ) -> subprocess.CompletedProcess[str]:
        assert "stdout" not in kwargs
        assert "stderr" not in kwargs
        observed_command.extend(command)
        return subprocess.CompletedProcess(command, 1)

    monkeypatch.setattr(execution.subprocess, "run", fake_run)

    result = execute_script_text(
        "#!powershell.exe\n# PATCHHARBOR\n",
        suffix=".txt",
        cwd=tmp_path,
        timeout_seconds=7,
    )

    assert result == 1
    lowered = {argument.casefold() for argument in observed_command}
    assert "-executionpolicy" not in lowered
    assert "bypass" not in lowered
