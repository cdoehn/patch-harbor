from __future__ import annotations

import pytest

from patchharbor.parser import ScriptFormatError, validate_required_marker


@pytest.mark.parametrize(
    "line_ending",
    ["\n", "\r\n", "\r"],
)
def test_required_marker_accepts_common_line_endings(line_ending: str) -> None:
    validate_required_marker(
        f"first{line_ending}# PATCHHARBOR{line_ending}last"
    )


@pytest.mark.parametrize(
    "script_text",
    [
        "echo no-marker\n",
        " # PATCHHARBOR\n",
        "# PATCHHARBOR extra\n",
        "# patchharbor\n",
        "# PATCHHARBOR MESSAGE note\n",
    ],
)
def test_required_marker_rejects_non_exact_lines(script_text: str) -> None:
    with pytest.raises(
        ScriptFormatError,
        match=r"^missing required marker line: # PATCHHARBOR$",
    ):
        validate_required_marker(script_text)
