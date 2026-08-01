from __future__ import annotations

from io import StringIO
import os
from pathlib import Path

import pytest

from patchharbor.errors import ExitCode, PatchHarborError
from patchharbor.application import discover_directory_candidates, run_script_path
from patchharbor.sources import DirectoryCandidate, select_directory_candidate


REQUIRED_MARKER = "# PATCHHARBOR"


def _write_script(path: Path) -> None:
    path.write_text(f"{REQUIRED_MARKER}\n", encoding="utf-8")


def test_discovery_is_non_recursive_ignores_symlinks_and_sorts(tmp_path: Path) -> None:
    newest = tmp_path / "newest.sh"
    alpha = tmp_path / "alpha.sh"
    beta = tmp_path / "beta.sh"
    for path in (newest, alpha, beta):
        _write_script(path)
    os.utime(newest, ns=(300, 300))
    os.utime(alpha, ns=(200, 200))
    os.utime(beta, ns=(200, 200))

    nested = tmp_path / "nested"
    nested.mkdir()
    _write_script(nested / "hidden.sh")
    try:
        (tmp_path / "linked.sh").symlink_to(newest)
    except OSError:
        pass

    candidates = discover_directory_candidates(tmp_path)

    assert [candidate.display_name for candidate in candidates] == [
        "newest.sh",
        "alpha.sh",
        "beta.sh",
    ]


def test_selection_uses_candidate_data_without_rescanning(tmp_path: Path) -> None:
    candidates = (
        DirectoryCandidate(tmp_path / "first.sh", 2),
        DirectoryCandidate(tmp_path / "second.sh", 1),
    )
    output = StringIO()

    selected = select_directory_candidate(
        candidates,
        input_stream=StringIO("2\n"),
        output_stream=output,
    )

    assert selected is candidates[1]
    assert "first.sh" in output.getvalue()
    assert "second.sh" in output.getvalue()


class _DeletingInput(StringIO):
    def __init__(self, path: Path) -> None:
        super().__init__("1\n")
        self._path = path

    def readline(self, *args: object, **kwargs: object) -> str:
        self._path.unlink()
        return super().readline(*args, **kwargs)


def test_disappeared_selected_file_has_a_clear_source_error(tmp_path: Path) -> None:
    first = tmp_path / "first.sh"
    second = tmp_path / "second.sh"
    _write_script(first)
    _write_script(second)
    os.utime(first, ns=(200, 200))
    os.utime(second, ns=(100, 100))

    with pytest.raises(PatchHarborError) as raised:
        run_script_path(
            tmp_path,
            cwd=tmp_path,
            timeout_seconds=1,
            selection_input=_DeletingInput(first),
            selection_output=StringIO(),
        )

    assert raised.value.exit_code is ExitCode.SOURCE_ERROR
    assert str(raised.value) == "selected script is no longer available: first.sh"
