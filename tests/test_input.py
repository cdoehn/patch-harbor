from __future__ import annotations

from io import StringIO
from pathlib import Path

from patchharbor.input import read_script_file, read_script_stdin


def test_file_and_stdin_produce_the_same_neutral_shape(tmp_path: Path) -> None:
    script_path = tmp_path / "example.sh"
    script_path.write_text("# PATCHHARBOR\n", encoding="utf-8")

    file_source = read_script_file(script_path)
    stdin_source = read_script_stdin(StringIO("# PATCHHARBOR\n"))

    assert file_source.text == stdin_source.text
    assert file_source.suffix == ".sh"
    assert stdin_source.suffix in {".sh", ".ps1"}
