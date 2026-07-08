from __future__ import annotations

import re
from dataclasses import dataclass


_HEREDOC_START_RE = re.compile(
    r"(?<!<)(?P<operator><<-|<<)(?!<)\s*(?P<quote>['\"]?)(?P<delimiter>[A-Za-z_][A-Za-z0-9_]*)"
    r"(?P=quote)"
)


@dataclass(frozen=True)
class ShellCodeLine:
    line_number: int
    text: str

    def __post_init__(self) -> None:
        if not isinstance(self.line_number, int) or self.line_number < 1:
            raise ValueError("shell code line_number must be a positive integer")
        if not isinstance(self.text, str):
            raise ValueError("shell code line text must be a string")


@dataclass(frozen=True)
class HeredocStart:
    delimiter: str
    line_number: int
    strip_tabs: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.delimiter, str) or not self.delimiter:
            raise ValueError("heredoc delimiter must be a non-empty string")
        if not isinstance(self.line_number, int) or self.line_number < 1:
            raise ValueError("heredoc line_number must be a positive integer")
        if not isinstance(self.strip_tabs, bool):
            raise ValueError("heredoc strip_tabs must be a boolean")


def find_heredoc_starts(line: str, *, line_number: int = 1) -> tuple[HeredocStart, ...]:
    if not isinstance(line, str):
        raise ValueError("line must be a string")
    if not isinstance(line_number, int) or line_number < 1:
        raise ValueError("line_number must be a positive integer")

    comment_start = _unquoted_comment_start(line)
    search_line = line if comment_start is None else line[:comment_start]
    starts: list[HeredocStart] = []
    quoted_indexes = _quoted_indexes(search_line)

    for match in _HEREDOC_START_RE.finditer(search_line):
        if match.start("operator") in quoted_indexes:
            continue
        starts.append(
            HeredocStart(
                delimiter=match.group("delimiter"),
                line_number=line_number,
                strip_tabs=match.group("operator") == "<<-",
            )
        )

    return tuple(starts)


def iter_shell_code_lines_outside_heredocs(text: str) -> tuple[ShellCodeLine, ...]:
    if not isinstance(text, str):
        raise ValueError("text must be a string")

    active: list[HeredocStart] = []
    result: list[ShellCodeLine] = []

    for index, raw_line in enumerate(text.splitlines(), start=1):
        if active:
            current = active[0]
            if is_heredoc_terminator(raw_line, current.delimiter, strip_tabs=current.strip_tabs):
                active.pop(0)
            continue

        code_line = ShellCodeLine(index, raw_line)
        result.append(code_line)
        active.extend(find_heredoc_starts(raw_line, line_number=index))

    return tuple(result)


def shell_text_outside_heredocs(text: str) -> str:
    return "\n".join(line.text for line in iter_shell_code_lines_outside_heredocs(text))


def is_heredoc_terminator(line: str, delimiter: str, *, strip_tabs: bool = False) -> bool:
    if not isinstance(line, str):
        raise ValueError("line must be a string")
    if not isinstance(delimiter, str) or not delimiter:
        raise ValueError("delimiter must be a non-empty string")
    candidate = line.rstrip("\n")
    if strip_tabs:
        candidate = candidate.lstrip("\t")
    return candidate == delimiter


def _quoted_indexes(line: str) -> frozenset[int]:
    quoted: set[int] = set()
    quote: str | None = None
    escaped = False

    for index, char in enumerate(line):
        if escaped:
            if quote is not None:
                quoted.add(index)
            escaped = False
            continue

        if quote == '"' and char == "\\":
            quoted.add(index)
            escaped = True
            continue

        if quote is None and char == "\\":
            escaped = True
            continue

        if quote is None and char in ("'", '"'):
            quoted.add(index)
            quote = char
            continue

        if quote is not None:
            quoted.add(index)
            if char == quote:
                quote = None

    return frozenset(quoted)


def _unquoted_comment_start(line: str) -> int | None:
    quoted = _quoted_indexes(line)
    for index, char in enumerate(line):
        if char == "#" and index not in quoted:
            return index
    return None
