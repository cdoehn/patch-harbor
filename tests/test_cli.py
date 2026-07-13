from __future__ import annotations

from io import StringIO

import pytest

from patchharbor.cli import main


class _TerminalInput(StringIO):
    def isatty(self) -> bool:
        return True


def test_fs_run_without_path_on_terminal_is_a_usage_error(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit) as raised:
        main(["fs", "run"], stdin=_TerminalInput())

    assert raised.value.code == 2
    assert "PATH is required when standard input is a terminal" in capsys.readouterr().err
