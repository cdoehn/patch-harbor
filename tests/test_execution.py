from __future__ import annotations

from pathlib import Path

import pytest

from patchharbor.errors import ExitCode, PatchHarborError
import patchharbor.execution as execution
from patchharbor.execution import execute_script_text
import patchharbor.interpreters as interpreters
from patchharbor.platform import ProcessTreeTimeout


class _FakeProcessTree:
    def __init__(
        self,
        *,
        returncode: int = 0,
        wait_error: BaseException | None = None,
        stop_error: OSError | None = None,
    ) -> None:
        self.returncode = returncode
        self.wait_error = wait_error
        self.stop_error = stop_error
        self.wait_timeouts: list[float] = []
        self.stop_calls: list[bool] = []
        self.entered = 0
        self.closed = 0
        self.exit_exception: type[BaseException] | None = None

    def __enter__(self) -> _FakeProcessTree:
        self.entered += 1
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: object,
    ) -> bool:
        self.exit_exception = exc_type
        self.closed += 1
        return False

    def wait(self, *, timeout_seconds: float) -> int:
        self.wait_timeouts.append(timeout_seconds)
        if self.wait_error is not None:
            raise self.wait_error
        return self.returncode

    def stop(self, *, graceful: bool) -> None:
        self.stop_calls.append(graceful)
        if self.stop_error is not None:
            raise self.stop_error


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
    process_tree = _FakeProcessTree(returncode=0)
    _patch_resolved_interpreter(monkeypatch)

    def fake_create_process_tree(
        command: list[str],
        *,
        cwd: Path,
    ) -> _FakeProcessTree:
        script_path = Path(command[-1])
        assert script_path.suffix == ".sh"
        assert script_path.read_text(encoding="utf-8").startswith(
            "#!/usr/bin/env bash"
        )
        observed.append((command, cwd))
        return process_tree

    monkeypatch.setattr(
        execution,
        "create_process_tree",
        fake_create_process_tree,
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
    assert process_tree.wait_timeouts == [7]
    assert process_tree.stop_calls == [False]
    assert process_tree.entered == 1
    assert process_tree.closed == 1


def test_interpreter_selection_error_happens_before_process_start(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    process_started = False

    def fail_if_started(*args: object, **kwargs: object) -> None:
        nonlocal process_started
        process_started = True
        raise AssertionError("process must not start")

    monkeypatch.setattr(execution, "create_process_tree", fail_if_started)

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

    monkeypatch.setattr(execution, "create_process_tree", fail_if_started)

    with pytest.raises(PatchHarborError) as raised:
        execute_script_text(
            "#!/usr/bin/env bash\n# PATCHHARBOR\n",
            cwd=tmp_path,
            timeout_seconds=7,
        )

    assert raised.value.exit_code is ExitCode.INTERPRETER_ERROR
    assert str(raised.value) == "script interpreter not found: bash"
    assert not process_started


def test_process_start_error_is_reported_as_interpreter_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_resolved_interpreter(monkeypatch)
    monkeypatch.setattr(
        execution,
        "create_process_tree",
        lambda command, cwd: (_ for _ in ()).throw(OSError("start failed")),
    )

    with pytest.raises(PatchHarborError) as raised:
        execute_script_text(
            "#!/usr/bin/env bash\n# PATCHHARBOR\n",
            cwd=tmp_path,
            timeout_seconds=7,
        )

    assert raised.value.exit_code is ExitCode.INTERPRETER_ERROR
    assert str(raised.value) == "cannot start script interpreter: start failed"


def test_nonzero_powershell_result_is_returned_without_policy_bypass(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed_command: list[str] = []
    process_tree = _FakeProcessTree(returncode=1)
    _patch_resolved_interpreter(monkeypatch)

    def fake_create_process_tree(
        command: list[str],
        *,
        cwd: Path,
    ) -> _FakeProcessTree:
        observed_command.extend(command)
        return process_tree

    monkeypatch.setattr(
        execution,
        "create_process_tree",
        fake_create_process_tree,
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
    assert process_tree.stop_calls == [False]
    assert process_tree.closed == 1


def test_timeout_stops_the_process_tree_and_returns_124(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_resolved_interpreter(monkeypatch)
    process_tree = _FakeProcessTree(wait_error=ProcessTreeTimeout())
    monkeypatch.setattr(
        execution,
        "create_process_tree",
        lambda command, cwd: process_tree,
    )

    with pytest.raises(PatchHarborError) as raised:
        execute_script_text(
            "#!/usr/bin/env bash\n# PATCHHARBOR\n",
            cwd=tmp_path,
            timeout_seconds=0.25,
        )

    assert raised.value.exit_code is ExitCode.TIMEOUT
    assert process_tree.stop_calls == [True]
    assert process_tree.closed == 1
    assert process_tree.exit_exception is PatchHarborError


def test_keyboard_interrupt_stops_the_process_tree_and_returns_130(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_resolved_interpreter(monkeypatch)
    process_tree = _FakeProcessTree(wait_error=KeyboardInterrupt())
    monkeypatch.setattr(
        execution,
        "create_process_tree",
        lambda command, cwd: process_tree,
    )

    with pytest.raises(PatchHarborError) as raised:
        execute_script_text(
            "#!/usr/bin/env bash\n# PATCHHARBOR\n",
            cwd=tmp_path,
            timeout_seconds=7,
        )

    assert raised.value.exit_code is ExitCode.INTERRUPTED
    assert str(raised.value) == "script aborted by user"
    assert process_tree.stop_calls == [True]
    assert process_tree.closed == 1
    assert process_tree.exit_exception is PatchHarborError


def test_process_tree_is_closed_when_waiting_raises_an_os_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_resolved_interpreter(monkeypatch)
    process_tree = _FakeProcessTree(wait_error=OSError("wait failed"))
    monkeypatch.setattr(
        execution,
        "create_process_tree",
        lambda command, cwd: process_tree,
    )

    with pytest.raises(PatchHarborError) as raised:
        execute_script_text(
            "#!/usr/bin/env bash\n# PATCHHARBOR\n",
            cwd=tmp_path,
            timeout_seconds=7,
        )

    assert raised.value.exit_code is ExitCode.EXECUTION_ERROR
    assert str(raised.value) == "cannot control script process tree: wait failed"
    assert process_tree.closed == 1
    assert process_tree.exit_exception is OSError


def test_process_tree_is_closed_when_final_descendant_cleanup_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_resolved_interpreter(monkeypatch)
    process_tree = _FakeProcessTree(
        returncode=0,
        stop_error=OSError("cleanup failed"),
    )
    monkeypatch.setattr(
        execution,
        "create_process_tree",
        lambda command, cwd: process_tree,
    )

    with pytest.raises(PatchHarborError) as raised:
        execute_script_text(
            "#!/usr/bin/env bash\n# PATCHHARBOR\n",
            cwd=tmp_path,
            timeout_seconds=7,
        )

    assert raised.value.exit_code is ExitCode.EXECUTION_ERROR
    assert str(raised.value) == (
        "cannot control script process tree: cleanup failed"
    )
    assert process_tree.stop_calls == [False]
    assert process_tree.closed == 1
    assert process_tree.exit_exception is OSError
