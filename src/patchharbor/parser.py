"""Parsing rules for the PatchHarbor script format."""

from __future__ import annotations

from dataclasses import dataclass
import re

from patchharbor.files import is_safe_payload_name, payload_size_warning


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
_FILE_PREFIX = "# PATCHHARBOR FILE "
_FILE_START_PATTERN = re.compile(
    r"^# PATCHHARBOR FILE (.+) START$"
)
_FILE_END_PATTERN = re.compile(
    r"^# PATCHHARBOR FILE (.+) END$"
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
class PayloadFile:
    """One text file transferred alongside a script."""

    name: str
    text: str


@dataclass(frozen=True)
class ParsedScript:
    """Structured script data passed to later processing layers."""

    text: str
    metadata: tuple[Metadata, ...]
    messages: tuple[Message, ...]
    payload_files: tuple[PayloadFile, ...]
    warnings: tuple[str, ...]


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
    """Parse required syntax and retain only valid optional information."""
    validate_required_marker(script_text)
    metadata: list[Metadata] = []
    messages: list[Message] = []
    payload_files: list[PayloadFile] = []
    warnings: list[str] = []
    seen_warnings: set[str] = set()

    active_kind: str | None = None
    active_name: str | None = None
    active_content: list[str] = []
    active_content_is_valid = True
    discarding_invalid_kind: str | None = None

    def warn(text: str) -> None:
        if text not in seen_warnings:
            warnings.append(text)
            seen_warnings.add(text)

    for line in script_text.splitlines():
        if discarding_invalid_kind is not None:
            end_pattern = (
                _MESSAGE_END_PATTERN
                if discarding_invalid_kind == "MESSAGE"
                else _FILE_END_PATTERN
            )
            if end_pattern.fullmatch(line):
                discarding_invalid_kind = None
            continue

        if active_kind is not None and active_name is not None:
            end_pattern = (
                _MESSAGE_END_PATTERN
                if active_kind == "MESSAGE"
                else _FILE_END_PATTERN
            )
            if end_match := end_pattern.fullmatch(line):
                end_name = end_match.group(1)
                if end_name != active_name:
                    warn(
                        f"discarded {active_kind} {active_name!r}: END name "
                        f"{end_name!r} does not match"
                    )
                elif not active_content_is_valid:
                    warn(
                        f"discarded {active_kind} {active_name!r}: "
                        "content is not fully commented"
                    )
                else:
                    text = "\n".join(active_content)
                    if active_kind == "MESSAGE":
                        messages.append(Message(name=active_name, text=text))
                    else:
                        if not is_safe_payload_name(active_name):
                            warn(
                                f"discarded FILE {active_name!r}: "
                                "invalid file name"
                            )
                        else:
                            if size_warning := payload_size_warning(
                                active_name, text
                            ):
                                warn(size_warning)
                            payload_files.append(
                                PayloadFile(name=active_name, text=text)
                            )
                active_kind = None
                active_name = None
                active_content = []
                active_content_is_valid = True
                continue

            content_line = _message_content(line)
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
            active_kind = "MESSAGE"
            active_name = start_match.group(1)
            active_content = []
            active_content_is_valid = True
            continue

        if start_match := _FILE_START_PATTERN.fullmatch(line):
            active_kind = "FILE"
            active_name = start_match.group(1)
            active_content = []
            active_content_is_valid = True
            continue

        if line.startswith(_MESSAGE_PREFIX) and line.endswith(" START"):
            warn("discarded invalid MESSAGE block")
            discarding_invalid_kind = "MESSAGE"
            continue

        if line.startswith(_FILE_PREFIX) and line.endswith(" START"):
            warn("discarded invalid FILE block")
            discarding_invalid_kind = "FILE"

    if active_kind is not None and active_name is not None:
        warn(f"discarded {active_kind} {active_name!r}: missing END marker")

    return ParsedScript(
        text=script_text,
        metadata=tuple(metadata),
        messages=tuple(messages),
        payload_files=tuple(payload_files),
        warnings=tuple(warnings),
    )
