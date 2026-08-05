"""Parsing rules for the PatchHarbor script format."""

from __future__ import annotations

from dataclasses import dataclass
import re


REQUIRED_MARKER = "# PATCHHARBOR"
_NAME = r"[A-Za-z0-9.]+"
_META_PREFIX = "# PATCHHARBOR META "
_META_PATTERN = re.compile(rf"^# PATCHHARBOR META ({_NAME})=(.*)$")
_MESSAGE_START_PATTERN = re.compile(r"^# PATCHHARBOR MESSAGE (.+) START$")
_MESSAGE_END_PATTERN = re.compile(r"^# PATCHHARBOR MESSAGE (.+) END$")
_MESSAGE_START_PREFIX = "# PATCHHARBOR MESSAGE "


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
    warnings: tuple[str, ...]


def validate_required_marker(script_text: str) -> None:
    """Require the exact marker as a complete normalized line."""
    if REQUIRED_MARKER not in script_text.splitlines():
        raise ScriptFormatError(
            f"missing required marker line: {REQUIRED_MARKER}"
        )


def _comment_content(line: str) -> str | None:
    if line == "#":
        return ""
    if line.startswith("# "):
        return line[2:]
    return None


def _invalid_message_start(line: str) -> bool:
    return line.startswith(_MESSAGE_START_PREFIX) and line.endswith(" START")


def parse_script(script_text: str) -> ParsedScript:
    """Parse required syntax and retain only valid optional information."""
    validate_required_marker(script_text)
    metadata: list[Metadata] = []
    messages: list[Message] = []
    warnings: list[str] = []
    seen_warnings: set[str] = set()

    active_name: str | None = None
    active_content: list[str] = []
    active_content_is_valid = True
    discarding_message = False

    def warn(text: str) -> None:
        if text not in seen_warnings:
            warnings.append(text)
            seen_warnings.add(text)

    def reset_active_message() -> None:
        nonlocal active_name, active_content, active_content_is_valid
        active_name = None
        active_content = []
        active_content_is_valid = True

    for line in script_text.splitlines():
        end_match = _MESSAGE_END_PATTERN.fullmatch(line)

        if discarding_message:
            if end_match:
                discarding_message = False
            continue

        if active_name is not None:
            if end_match:
                end_name = end_match.group(1)
                if end_name != active_name:
                    warn(
                        f"discarded MESSAGE {active_name!r}: "
                        f"END name {end_name!r} does not match"
                    )
                elif not active_content_is_valid:
                    warn(
                        f"discarded MESSAGE {active_name!r}: "
                        "content is not fully commented"
                    )
                else:
                    messages.append(
                        Message(
                            name=active_name,
                            text="\n".join(active_content),
                        )
                    )
                reset_active_message()
                continue

            content_line = _comment_content(line)
            if content_line is None:
                active_content_is_valid = False
            else:
                active_content.append(content_line)
            continue

        if metadata_match := _META_PATTERN.fullmatch(line):
            metadata.append(
                Metadata(
                    name=metadata_match.group(1),
                    value=metadata_match.group(2),
                )
            )
            continue

        if line.startswith(_META_PREFIX):
            warn("ignored invalid META directive")
            continue

        if start_match := _MESSAGE_START_PATTERN.fullmatch(line):
            name = start_match.group(1)
            if re.fullmatch(_NAME, name) is None:
                warn("discarded invalid MESSAGE block")
                discarding_message = True
            else:
                active_name = name
            continue

        if _invalid_message_start(line):
            warn("discarded invalid MESSAGE block")
            discarding_message = True

    if active_name is not None:
        warn(f"discarded MESSAGE {active_name!r}: missing END marker")

    return ParsedScript(
        text=script_text,
        metadata=tuple(metadata),
        messages=tuple(messages),
        warnings=tuple(warnings),
    )
