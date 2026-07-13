from __future__ import annotations

import pytest

from patchharbor.errors import ExitCode, PatchHarborError
import patchharbor.files as payload_files
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


@pytest.mark.parametrize(
    "name",
    (
        ".",
        "..",
        "folder/file.txt",
        r"folder\file.txt",
        "name.",
        "name ",
        "CON.txt",
        "LPT9",
        "ä.txt",
        "a" * 129,
    ),
)
def test_invalid_file_name_discards_block_with_warning(name: str) -> None:
    parsed = parse_script(
        "\n".join(
            (
                "# PATCHHARBOR",
                f"# PATCHHARBOR FILE {name} START",
                "# ignored",
                f"# PATCHHARBOR FILE {name} END",
            )
        )
    )

    assert parsed.payload_files == ()
    assert parsed.warnings == (
        f"discarded FILE {name!r}: invalid file name",
    )


def test_damaged_file_blocks_are_discarded_without_losing_later_file() -> None:
    parsed = parse_script(
        "\n".join(
            (
                "# PATCHHARBOR",
                "# PATCHHARBOR FILE mismatch.txt START",
                "# ignored",
                "# PATCHHARBOR FILE other.txt END",
                "# PATCHHARBOR FILE uncommented.txt START",
                "not commented",
                "# PATCHHARBOR FILE uncommented.txt END",
                "# PATCHHARBOR FILE good.txt START",
                "# retained",
                "# PATCHHARBOR FILE good.txt END",
                "# PATCHHARBOR FILE unfinished.txt START",
                "# ignored",
            )
        )
    )

    assert parsed.payload_files == (
        PayloadFile(name="good.txt", text="retained"),
    )
    assert parsed.warnings == (
        "discarded FILE 'mismatch.txt': END name 'other.txt' does not match",
        "discarded FILE 'uncommented.txt': content is not fully commented",
        "discarded FILE 'unfinished.txt': missing END marker",
    )


def test_large_file_payload_adds_warning(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(payload_files, "PAYLOAD_WARNING_BYTES", 3)
    monkeypatch.setattr(payload_files, "MAX_PAYLOAD_BYTES", 10)

    parsed = parse_script(
        "\n".join(
            (
                "# PATCHHARBOR",
                "# PATCHHARBOR FILE large.txt START",
                "# 1234",
                "# PATCHHARBOR FILE large.txt END",
            )
        )
    )

    assert parsed.payload_files == (
        PayloadFile(name="large.txt", text="1234"),
    )
    assert parsed.warnings == ("FILE 'large.txt' is large (4 bytes)",)


def test_file_payload_over_hard_budget_is_fatal(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(payload_files, "MAX_PAYLOAD_BYTES", 3)

    with pytest.raises(PatchHarborError) as raised:
        parse_script(
            "\n".join(
                (
                    "# PATCHHARBOR",
                    "# PATCHHARBOR FILE too-large.txt START",
                    "# 1234",
                    "# PATCHHARBOR FILE too-large.txt END",
                )
            )
        )

    assert raised.value.exit_code is ExitCode.SOURCE_ERROR
    assert str(raised.value) == "FILE 'too-large.txt' exceeds the 3 byte limit"
