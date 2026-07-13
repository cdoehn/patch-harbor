from __future__ import annotations

from pathlib import Path
import subprocess

import pytest

from patchharbor.errors import ExitCode, InterpreterError
from patchharbor.execution import execute_script_file


def test_process_start_failure_is_a_tool_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def fail_to_start(*args: object, **kwargs: object) -> None:
        raise FileNotFoundError("missing interpreter")

    monkeypatch.setattr(subprocess, "run", fail_to_start)

    with pytest.raises(InterpreterError) as captured:
        execute_script_file(
            Path("script.sh"),
            cwd=Path.cwd(),
            timeout_seconds=1,
        )

    assert captured.value.exit_code == ExitCode.INTERPRETER_ERROR
    assert str(captured.value) == (
        "cannot start script interpreter: missing interpreter"
    )
