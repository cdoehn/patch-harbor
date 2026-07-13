"""Parsing rules for the PatchHarbor script format."""

from __future__ import annotations

from dataclasses import dataclass
import re


REQUIRED_MARKER = "# PATCHHARBOR"
_NAME = r"[A-Za-z0-9.]+"
_META_PREFIX = "# PATCHHARBOR META "
_META_PATTERN = re.compile(rf"^# PATCHHARBOR META ({_NAME})=(.*)$")
_MESSAGE_PREFIX = "# PATCHHARBOR MESSAGE "
_MESSAGE_START_PATTERN = re.compile(
    rf"^# PATCHHARBOR MESSAGE ({_NAME}) START$"
)
_MESSAGE_END_PATTERN = re.compile(
    r"^# PATCHHARBOR MESSAGE (.+) END$"
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
class ParseWarning:
    """One non-fatal problem in optional script information."""

    text: str


@dataclass(frozen=True)
class ParsedScript:
    """Structured script data passed to later processing layers."""

    text: str
    metadata: tuple[Metadata, ...]
    messages: tuple[Message, ...]
    warnings: tuple[ParseWarning, ...]


@dataclass(frozen=True)
class _MessageBlockResult:
    message: Message | None
    next_index: int
    warning: ParseWarning | None


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


def _parse_message_block(
    lines: list[str],
    *,
    start_index: int,
    name: str,
) -> _MessageBlockResult:
    content: list[str] = []
    invalid_content_line: int | None = None
    index = start_index + 1

    while index < len(lines):
        line = lines[index]
        if end_match := _MESSAGE_END_PATTERN.fullmatch(line):
            end_name = end_match.group(1)
            if end_name != name:
                return _MessageBlockResult(
                    message=None,
                    next_index=index + 1,
                    warning=ParseWarning(
                        f"discarded MESSAGE {name!r}: END name "
                        f"{end_name!r} does not match"
                    ),
                )
            if invalid_content_line is not None:
                return _MessageBlockResult(
                    message=None,
                    next_index=index + 1,
                    warning=ParseWarning(
                        f"discarded MESSAGE {name!r}: line "
                        f"{invalid_content_line} is not commented"
                    ),
                )
            return _MessageBlockResult(
                message=Message(name=name, text="\n".join(content)),
                next_index=index + 1,
                warning=None,
            )

        content_line = _message_content(line)
        if content_line is None:
            invalid_content_line = invalid_content_line or index + 1
        else:
            content.append(content_line)
        index += 1

    return _MessageBlockResult(
        message=None,
        next_index=index,
        warning=ParseWarning(
            f"discarded MESSAGE {name!r}: missing END marker"
        ),
    )


def _skip_invalid_message_block(lines: list[str], start_index: int) -> int:
    index = start_index + 1
    while index < len(lines):
        if _MESSAGE_END_PATTERN.fullmatch(lines[index]):
            return index + 1
        index += 1
    return index


def parse_script(script_text: str) -> ParsedScript:
    """Parse required syntax and collect non-fatal optional-data warnings."""
    validate_required_marker(script_text)
    lines = script_text.splitlines()
    metadata: list[Metadata] = []
    messages: list[Message] = []
    warnings: list[ParseWarning] = []
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

        if line.startswith(_META_PREFIX):
            warnings.append(
                ParseWarning(f"ignored invalid META line {index + 1}")
            )
            index += 1
            continue

        if start_match := _MESSAGE_START_PATTERN.fullmatch(line):
            result = _parse_message_block(
                lines,
                start_index=index,
                name=start_match.group(1),
            )
            if result.message is not None:
                messages.append(result.message)
            if result.warning is not None:
                warnings.append(result.warning)
            index = result.next_index
            continue

        if line.startswith(_MESSAGE_PREFIX) and line.endswith(" START"):
            warnings.append(
                ParseWarning(
                    f"discarded invalid MESSAGE block at line {index + 1}"
                )
            )
            index = _skip_invalid_message_block(lines, index)
            continue

        index += 1

    return ParsedScript(
        text=script_text,
        metadata=tuple(metadata),
        messages=tuple(messages),
        warnings=tuple(warnings),
    )
