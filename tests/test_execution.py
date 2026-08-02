from __future__ import annotations

from pathlib import Path
import subprocess

import pytest

from patchharbor.errors import ExitCode, PatchHarborError
import patchharbor.execution as execution
from patchharbor.execution import execute_script_text
import patchharbor.interpreters as interpreters


class _CompletedProcess:
    def __init__(self, returncode: int) -> None:
        self.pid = 123456
        self.returncode: int | None = None
        self._result = returncode

    def wait(self, timeout: float | None = None) -> int:
        self.returncode = self._result
        return self._result

    def poll(self) -> int | None:
        return self.returncode

    def kill(self) -> None:
        self.returncode = -9


class _TimedOutProcess(_CompletedProcess):
    def wait(self, timeout: float | None = None) -> int:
        raise subprocess.TimeoutExpired(["interpreter"], timeout)


class _InterruptedProcess(_CompletedProcess):
    def wait(self, timeout: float | None = None) -> int:
        raise KeyboardInterrupt


def _patch_resolved_interpreter(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        interpreters.shutil,
        "which",
        lambda executable: f"/interpreters/{executable}",
    )


def test_execution_stages_with_selected_technical_suffix(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed: list[tuple[list[str], Path]] = []
    _patch_resolved_interpreter(monkeypatch)

    def fake_start_process(
        command: list[str],
        *,
        cwd: Path,
    ) -> tuple[_CompletedProcess, None]:
        script_path = Path(command[-1])
        assert script_path.suffix == ".sh"
        assert script_path.read_text(encoding="utf-8").startswith(
            "#!/usr/bin/env bash"
        )
        observed.append((command, cwd))
        return _CompletedProcess(0), None

    monkeypatch.setattr(execution, "_start_process", fake_start_process)
    monkeypatch.setattr(
        execution,
        "_stop_process_tree",
        lambda *args, **kwargs: None,
    )

    result = execute_script_text(
        "#!/usr/bin/env bash\n# PATCHHARBOR\n",
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

    monkeypatch.setattr(execution, "_start_process", fail_if_started)

    with pytest.raises(PatchHarborError) as raised:
        execute_script_text(
            "#!/usr/bin/env python3\n# PATCHHARBOR\n",
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

    monkeypatch.setattr(execution, "_start_process", fail_if_started)

    with pytest.raises(PatchHarborError) as raised:
        execute_script_text(
            "#!/usr/bin/env bash\n# PATCHHARBOR\n",
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
    _patch_resolved_interpreter(monkeypatch)

    def fake_start_process(
        command: list[str],
        *,
        cwd: Path,
    ) -> tuple[_CompletedProcess, None]:
        observed_command.extend(command)
        return _CompletedProcess(1), None

    monkeypatch.setattr(execution, "_start_process", fake_start_process)
    monkeypatch.setattr(
        execution,
        "_stop_process_tree",
        lambda *args, **kwargs: None,
    )

    result = execute_script_text(
        "#!powershell.exe\n# PATCHHARBOR\n",
        cwd=tmp_path,
        timeout_seconds=7,
    )

    assert result == 1
    lowered = {argument.casefold() for argument in observed_command}
    assert "-executionpolicy" not in lowered
    assert "bypass" not in lowered


def test_timeout_stops_the_process_tree_and_returns_124(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_resolved_interpreter(monkeypatch)
    process = _TimedOutProcess(0)
    stop_calls: list[bool] = []

    monkeypatch.setattr(
        execution,
        "_start_process",
        lambda command, cwd: (process, None),
    )
    monkeypatch.setattr(
        execution,
        "_stop_process_tree",
        lambda process, job_handle, *, graceful: stop_calls.append(graceful),
    )

    with pytest.raises(PatchHarborError) as raised:
        execute_script_text(
            "#!/usr/bin/env bash\n# PATCHHARBOR\n",
            cwd=tmp_path,
            timeout_seconds=0.25,
        )

    assert raised.value.exit_code is ExitCode.TIMEOUT
    assert stop_calls == [True]


def test_keyboard_interrupt_stops_the_process_tree_and_returns_130(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_resolved_interpreter(monkeypatch)
    process = _InterruptedProcess(0)
    stop_calls: list[bool] = []

    monkeypatch.setattr(
        execution,
        "_start_process",
        lambda command, cwd: (process, None),
    )
    monkeypatch.setattr(
        execution,
        "_stop_process_tree",
        lambda process, job_handle, *, graceful: stop_calls.append(graceful),
    )

    with pytest.raises(PatchHarborError) as raised:
        execute_script_text(
            "#!/usr/bin/env bash\n# PATCHHARBOR\n",
            cwd=tmp_path,
            timeout_seconds=7,
        )

    assert raised.value.exit_code is ExitCode.INTERRUPTED
    assert str(raised.value) == "script aborted by user"
    assert stop_calls == [True]


def test_force_kill_follows_the_two_second_grace_period(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    process = _CompletedProcess(0)
    events: list[str] = []

    monkeypatch.setattr(
        execution,
        "_request_process_tree_stop",
        lambda process, job_handle: events.append("request"),
    )
    def fake_wait_for_tree(
        process: _CompletedProcess,
        job_handle: object | None,
        *,
        timeout_seconds: float,
    ) -> bool:
        events.append(f"wait:{timeout_seconds:g}")
        return timeout_seconds == 1.0

    monkeypatch.setattr(
        execution,
        "_wait_for_process_tree_exit",
        fake_wait_for_tree,
    )
    monkeypatch.setattr(
        execution,
        "_force_process_tree_stop",
        lambda process, job_handle: events.append("force"),
    )
    monkeypatch.setattr(
        execution,
        "_reap_root_process",
        lambda process: events.append("reap"),
    )

    execution._stop_process_tree(process, None, graceful=True)

    assert events == ["request", "wait:2", "force", "wait:1", "reap"]
