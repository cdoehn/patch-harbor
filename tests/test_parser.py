from __future__ import annotations

import pytest

from patchharbor.parser import ScriptFormatError, validate_required_marker


def test_required_marker_accepts_common_line_endings() -> None:
    for line_ending in ("\n", "\r\n", "\r"):
        validate_required_marker(
            f"first{line_ending}# PATCHHARBOR{line_ending}last"
        )


def test_required_marker_rejects_non_exact_lines() -> None:
    invalid_scripts = (
        "echo no-marker\n",
        " # PATCHHARBOR\n",
        "# PATCHHARBOR extra\n",
        "# patchharbor\n",
        "# PATCHHARBOR MESSAGE note\n",
    )

    for script_text in invalid_scripts:
        with pytest.raises(ScriptFormatError):
            validate_required_marker(script_text)


def test_missing_marker_error_is_explicit() -> None:
    with pytest.raises(
        ScriptFormatError,
        match=r"^missing required marker line: # PATCHHARBOR$",
    ):
        validate_required_marker("echo no-marker\n")
