from __future__ import annotations

import io
from pathlib import Path

import pytest

from patchharbor.errors import ExitCode, PatchHarborError
import patchharbor.execution as execution
from patchharbor.execution import execute_script_text
import patchharbor.interpreters as interpreters
from patchharbor.output import OutputTargets
from patchharbor.platform import ProcessResult, ProcessState


class _FakeProcessTree:
    def __init__(
        self,
        *,
        result: ProcessResult | None = None,
        run_error: BaseException | None = None,
        close_error: OSError | None = None,
        output_bytes: bytes = b"",
    ) -> None:
        self.result = result or ProcessResult(ProcessState.EXITED, 0)
        self.run_error = run_error
        self.close_error = close_error
        self.run_timeouts: list[float] = []
        self.entered = 0
        self.closed = 0
        self.exit_exception: type[BaseException] | None = None
        self.output_stream = io.BytesIO(output_bytes)

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
        if self.close_error is not None and exc_type is None:
            raise self.close_error
        return False

    def run(self, *, timeout_seconds: float) -> ProcessResult:
        self.run_timeouts.append(timeout_seconds)
        if self.run_error is not None:
            raise self.run_error
        return self.result


def _patch_resolved_interpreter(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        interpreters,
        "find_executable",
        lambda executable: f"/interpreters/{executable}",
    )


def test_execution_stages_with_selected_technical_suffix(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed: list[tuple[list[str], Path]] = []
    process_tree = _FakeProcessTree()
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
    assert process_tree.run_timeouts == [7]
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
    monkeypatch.setattr(interpreters, "find_executable", lambda executable: None)

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
    assert str(raised.value) == (
        "cannot start script interpreter: operating-system operation failed"
    )


def test_nonzero_powershell_result_is_returned_without_policy_bypass(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed_command: list[str] = []
    process_tree = _FakeProcessTree(result=ProcessResult(ProcessState.EXITED, 1))
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
    assert process_tree.closed == 1


def test_timeout_stops_the_process_tree_and_returns_124(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_resolved_interpreter(monkeypatch)
    process_tree = _FakeProcessTree(result=ProcessResult(ProcessState.TIMED_OUT))
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
    assert process_tree.closed == 1
    assert process_tree.exit_exception is PatchHarborError


def test_keyboard_interrupt_stops_the_process_tree_and_returns_130(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_resolved_interpreter(monkeypatch)
    process_tree = _FakeProcessTree(result=ProcessResult(ProcessState.INTERRUPTED))
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
    assert process_tree.closed == 1
    assert process_tree.exit_exception is PatchHarborError


def test_process_tree_is_closed_when_waiting_raises_an_os_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_resolved_interpreter(monkeypatch)
    process_tree = _FakeProcessTree(run_error=OSError("wait failed"))
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
        "cannot control script process tree: operating-system operation failed"
    )
    assert process_tree.closed == 1
    assert process_tree.exit_exception is OSError


def test_process_tree_is_closed_when_final_descendant_cleanup_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_resolved_interpreter(monkeypatch)
    process_tree = _FakeProcessTree(
        close_error=OSError("cleanup failed"),
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
        "cannot control script process tree: operating-system operation failed"
    )
    assert process_tree.closed == 1
    assert process_tree.exit_exception is None


def test_execution_shows_only_last_five_merged_lines(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_resolved_interpreter(monkeypatch)
    process_tree = _FakeProcessTree(
        output_bytes="".join(
            f"line-{number}\n" for number in range(1, 13)
        ).encode()
    )
    monkeypatch.setattr(
        execution,
        "create_process_tree",
        lambda command, cwd: process_tree,
    )
    destination = io.StringIO()

    result = execute_script_text(
        "#!/usr/bin/env bash\n# PATCHHARBOR\n",
        cwd=tmp_path,
        timeout_seconds=7,
        output=OutputTargets(visible_text_stream=destination),
    )

    assert result == 0
    assert destination.getvalue() == "".join(
        f"line-{number}\n" for number in range(8, 13)
    )
    assert process_tree.output_stream.closed


def test_execution_replaces_invalid_utf8_output(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_resolved_interpreter(monkeypatch)
    process_tree = _FakeProcessTree(output_bytes=b"bad-\xff-output\n")
    monkeypatch.setattr(
        execution,
        "create_process_tree",
        lambda command, cwd: process_tree,
    )
    destination = io.StringIO()

    result = execute_script_text(
        "#!/usr/bin/env bash\n# PATCHHARBOR\n",
        cwd=tmp_path,
        timeout_seconds=7,
        output=OutputTargets(visible_text_stream=destination),
    )

    assert result == 0
    assert destination.getvalue() == "bad-�-output\n"


def test_execution_plain_mode_streams_all_lines_without_bounded_replay(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_resolved_interpreter(monkeypatch)
    process_tree = _FakeProcessTree(
        output_bytes="".join(
            f"plain-{number}\n" for number in range(1, 13)
        ).encode()
    )
    monkeypatch.setattr(
        execution,
        "create_process_tree",
        lambda command, cwd: process_tree,
    )
    plain_destination = io.StringIO()
    bounded_destination = io.StringIO()

    result = execute_script_text(
        "#!/usr/bin/env bash\n# PATCHHARBOR\n",
        cwd=tmp_path,
        timeout_seconds=7,
        output=OutputTargets(
            visible_text_stream=bounded_destination,
            live_text_stream=plain_destination,
        ),
    )

    assert result == 0
    assert plain_destination.getvalue() == "".join(
        f"plain-{number}\n" for number in range(1, 13)
    )
    assert bounded_destination.getvalue() == ""
