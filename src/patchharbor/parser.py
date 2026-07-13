"""Parsing rules for the PatchHarbor script format."""

from __future__ import annotations

from dataclasses import dataclass
import re


REQUIRED_MARKER = "# PATCHHARBOR"
_NAME = r"[A-Za-z0-9.]+"
_META_PATTERN = re.compile(rf"^# PATCHHARBOR META ({_NAME})=(.*)$")
_MESSAGE_START_PATTERN = re.compile(
    rf"^# PATCHHARBOR MESSAGE ({_NAME}) START$"
)


class ScriptFormatError(ValueError):
    """The script does not satisfy the required PatchHarbor format."""


@dataclass(frozen=True)
class Metadata:
    """One informational META value from a script."""

    name: str
    value: str


@dataclass(frozen=True)
class Message:
    """One named informational MESSAGE block."""

    name: str
    text: str


@dataclass(frozen=True)
class ParsedScript:
    """Structured script data passed to later processing layers."""

    text: str
    metadata: tuple[Metadata, ...]
    messages: tuple[Message, ...]


def validate_required_marker(script_text: str) -> None:
    """Require the exact marker as a complete normalized line."""
    if REQUIRED_MARKER not in script_text.splitlines():
        raise ScriptFormatError(
            f"missing required marker line: {REQUIRED_MARKER}"
        )


def _message_content(line: str) -> str | None:
    if line == "#":
        return ""
    if line.startswith("# "):
        return line[2:]
    return None


def parse_script(script_text: str) -> ParsedScript:
    """Parse the required marker and well-formed informational data."""
    validate_required_marker(script_text)
    lines = script_text.splitlines()
    metadata: list[Metadata] = []
    messages: list[Message] = []
    index = 0

    while index < len(lines):
        line = lines[index]
        if metadata_match := _META_PATTERN.fullmatch(line):
            metadata.append(
                Metadata(
                    name=metadata_match.group(1),
                    value=metadata_match.group(2),
                )
            )
            index += 1
            continue

        start_match = _MESSAGE_START_PATTERN.fullmatch(line)
        if start_match is None:
            index += 1
            continue

        name = start_match.group(1)
        end_line = f"# PATCHHARBOR MESSAGE {name} END"
        content: list[str] = []
        block_is_valid = True
        index += 1

        while index < len(lines) and lines[index] != end_line:
            content_line = _message_content(lines[index])
            if content_line is None:
                block_is_valid = False
            else:
                content.append(content_line)
            index += 1

        if index < len(lines) and block_is_valid:
            messages.append(Message(name=name, text="\n".join(content)))

        if index < len(lines):
            index += 1

    return ParsedScript(
        text=script_text,
        metadata=tuple(metadata),
        messages=tuple(messages),
    )
