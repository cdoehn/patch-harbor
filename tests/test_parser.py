from __future__ import annotations

import pytest

from patchharbor.parser import (
    Message,
    Metadata,
    ScriptFormatError,
    parse_script,
    validate_required_marker,
)


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


def test_metadata_and_multiple_named_messages_are_parsed_in_order() -> None:
    parsed = parse_script(
        "\n".join(
            (
                "# PATCHHARBOR",
                "# PATCHHARBOR META author=Christian",
                "# PATCHHARBOR META build.V1=ready=yes",
                "# PATCHHARBOR MESSAGE Intro.1 START",
                "# First line",
                "#",
                "# Third line",
                "# PATCHHARBOR MESSAGE Intro.1 END",
                "# PATCHHARBOR MESSAGE result2 START",
                "# Finished",
                "# PATCHHARBOR MESSAGE result2 END",
            )
        )
    )

    assert parsed.metadata == (
        Metadata(name="author", value="Christian"),
        Metadata(name="build.V1", value="ready=yes"),
    )
    assert parsed.messages == (
        Message(name="Intro.1", text="First line\n\nThird line"),
        Message(name="result2", text="Finished"),
    )
