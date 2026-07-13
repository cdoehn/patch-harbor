from __future__ import annotations

import pytest

from patchharbor.parser import (
    Message,
    PayloadFile,
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


def test_damaged_optional_information_is_discarded_with_warnings() -> None:
    parsed = parse_script(
        "\n".join(
            (
                "# PATCHHARBOR",
                "# PATCHHARBOR META bad-name=value",
                "# PATCHHARBOR MESSAGE First START",
                "# ignored",
                "# PATCHHARBOR MESSAGE Other END",
                "# PATCHHARBOR MESSAGE Second START",
                "not commented",
                "# PATCHHARBOR MESSAGE Second END",
                "# PATCHHARBOR MESSAGE Third START",
                "# unfinished",
            )
        )
    )

    assert parsed.metadata == ()
    assert parsed.messages == ()
    assert parsed.warnings == (
        "ignored invalid META directive",
        "discarded MESSAGE 'First': END name 'Other' does not match",
        "discarded MESSAGE 'Second': content is not fully commented",
        "discarded MESSAGE 'Third': missing END marker",
    )


def test_valid_message_after_damaged_block_is_still_parsed() -> None:
    parsed = parse_script(
        "\n".join(
            (
                "# PATCHHARBOR",
                "# PATCHHARBOR MESSAGE Broken START",
                "# PATCHHARBOR MESSAGE Wrong END",
                "# PATCHHARBOR MESSAGE Good START",
                "# retained",
                "# PATCHHARBOR MESSAGE Good END",
            )
        )
    )

    assert parsed.messages == (Message(name="Good", text="retained"),)
    assert len(parsed.warnings) == 1


def test_invalid_message_name_discards_the_whole_block() -> None:
    parsed = parse_script(
        "\n".join(
            (
                "# PATCHHARBOR",
                "# PATCHHARBOR MESSAGE bad-name START",
                "# ignored",
                "# PATCHHARBOR MESSAGE bad-name END",
                "# PATCHHARBOR MESSAGE Good START",
                "# retained",
                "# PATCHHARBOR MESSAGE Good END",
            )
        )
    )

    assert parsed.messages == (Message(name="Good", text="retained"),)
    assert parsed.warnings == ("discarded invalid MESSAGE block",)


def test_duplicate_optional_data_warnings_are_reported_once() -> None:
    parsed = parse_script(
        "\n".join(
            (
                "# PATCHHARBOR",
                "# PATCHHARBOR META bad-name=first",
                "# PATCHHARBOR META other-name=second",
                "# PATCHHARBOR MESSAGE bad-name START",
                "# ignored",
                "# PATCHHARBOR MESSAGE bad-name END",
                "# PATCHHARBOR MESSAGE other-name START",
                "# ignored",
                "# PATCHHARBOR MESSAGE other-name END",
            )
        )
    )

    assert parsed.warnings == (
        "ignored invalid META directive",
        "discarded invalid MESSAGE block",
    )


def test_multiple_file_blocks_are_parsed_in_order() -> None:
    parsed = parse_script(
        "\n".join(
            (
                "# PATCHHARBOR",
                "# PATCHHARBOR FILE first.txt START",
                "# first line",
                "#",
                "# third line",
                "# PATCHHARBOR FILE first.txt END",
                "# PATCHHARBOR FILE payload.b64 START",
                "# SGVsbG8=",
                "# PATCHHARBOR FILE payload.b64 END",
            )
        )
    )

    assert parsed.payload_files == (
        PayloadFile(name="first.txt", text="first line\n\nthird line"),
        PayloadFile(name="payload.b64", text="SGVsbG8="),
    )
