from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re

from patchharbor.patch_lint import PatchLintFinding, PatchLintResult
from patchharbor.shell_scan import iter_shell_code_lines_outside_heredocs


RULE_GIT_NO_PAGER = "patch.git_no_pager"
RULE_FOOTER = "patch.footer"
RULE_TEST_EXECUTION = "patch.tests"
RULE_MARKDOWN_FENCE = "patch.markdown_fence"

_MARKDOWN_FENCE = chr(96) * 3
_CONTROL_PREFIXES = frozenset({"if", "then", "while", "until", "do", "command", "time"})


@dataclass(frozen=True)
class _CommandSegment:
    line_number: int
    start_column: int
    text: str


@dataclass(frozen=True)
class _Token:
    text: str
    start: int


def lint_git_pager_commands(text: str) -> PatchLintResult:
    findings: list[PatchLintFinding] = []

    for line in iter_shell_code_lines_outside_heredocs(text):
        visible = _shell_visible_text(line.text)
        for segment in _split_command_segments(visible, line_number=line.line_number):
            finding = _lint_git_pager_segment(segment)
            if finding is not None:
                findings.append(finding)

    return PatchLintResult(tuple(findings))


def lint_missing_footer(text: str) -> PatchLintResult:
    shell_text = "\n".join(line.text for line in iter_shell_code_lines_outside_heredocs(text))
    has_footer_function = re.search(r"^\s*print_footer\s*\(\)", shell_text, re.M) is not None
    has_footer_trap = "trap print_footer EXIT" in shell_text
    if has_footer_function and has_footer_trap:
        return PatchLintResult()

    return PatchLintResult(
        (
            PatchLintFinding(
                rule_id=RULE_FOOTER,
                message="Patch script should define print_footer and register it with trap print_footer EXIT",
                severity="warning",
                hint="Add a deterministic footer with current and next-step status.",
            ),
        )
    )


def lint_missing_test_execution(text: str) -> PatchLintResult:
    shell_lines = iter_shell_code_lines_outside_heredocs(text)
    visible = "\n".join(_shell_visible_text(line.text).lower() for line in shell_lines)
    test_markers = (
        "python3 -m compileall",
        "python -m compileall",
        "python3 -m unittest",
        "python -m unittest",
        "pytest",
        "bash -n",
    )
    if any(marker in visible for marker in test_markers):
        return PatchLintResult()

    return PatchLintResult(
        (
            PatchLintFinding(
                rule_id=RULE_TEST_EXECUTION,
                message="Patch script should run at least one syntax or test command",
                severity="warning",
                hint="Run focused tests such as compileall, unittest, pytest, or bash -n.",
            ),
        )
    )


def lint_markdown_fence_literals(text: str) -> PatchLintResult:
    findings: list[PatchLintFinding] = []

    for index, line in enumerate(text.splitlines(), start=1):
        column = line.find(_MARKDOWN_FENCE)
        if column >= 0:
            findings.append(
                PatchLintFinding(
                    rule_id=RULE_MARKDOWN_FENCE,
                    message="Avoid literal Markdown fence sequences inside patch scripts",
                    severity="warning",
                    line_number=index,
                    column=column + 1,
                    hint="Construct fence text dynamically when needed.",
                )
            )

    return PatchLintResult(tuple(findings))


def lint_patch_text(text: str) -> PatchLintResult:
    result = PatchLintResult()
    for rule_result in (
        lint_git_pager_commands(text),
        lint_missing_footer(text),
        lint_missing_test_execution(text),
        lint_markdown_fence_literals(text),
    ):
        result = result.extend(rule_result.findings)
    return result


def lint_patch_file(path: str | Path) -> PatchLintResult:
    file_path = Path(path)
    return lint_patch_text(file_path.read_text(encoding="utf-8"))


def _lint_git_pager_segment(segment: _CommandSegment) -> PatchLintFinding | None:
    tokens = _tokenize_segment(segment.text)
    if not tokens:
        return None

    index = 0
    safe_prefix = False

    while index < len(tokens):
        token = tokens[index].text

        if token in _CONTROL_PREFIXES or token == "!":
            index += 1
            continue

        if token == "env":
            index += 1
            while index < len(tokens) and _is_assignment(tokens[index].text):
                if tokens[index].text == "GIT_PAGER=cat":
                    safe_prefix = True
                index += 1
            continue

        if _is_assignment(token):
            if token == "GIT_PAGER=cat":
                safe_prefix = True
            index += 1
            continue

        break

    if index >= len(tokens) or tokens[index].text != "git":
        return None

    git_token = tokens[index]
    argument_index = index + 1
    safe_command = safe_prefix

    if argument_index < len(tokens) and tokens[argument_index].text == "--no-pager":
        safe_command = True
        argument_index += 1

    if argument_index >= len(tokens):
        return None

    command = tokens[argument_index].text
    if command not in {"diff", "log"}:
        return None

    if safe_command:
        return None

    return PatchLintFinding(
        rule_id=RULE_GIT_NO_PAGER,
        message=f"Use git --no-pager {command} or set GIT_PAGER=cat to avoid interactive pagers",
        severity="warning",
        line_number=segment.line_number,
        column=segment.start_column + git_token.start + 1,
        hint="Prefer git --no-pager for patch scripts.",
        data={"command": f"git {command}"},
    )


def _split_command_segments(line: str, *, line_number: int) -> tuple[_CommandSegment, ...]:
    segments: list[_CommandSegment] = []
    start = 0
    index = 0

    while index < len(line):
        separator_length = _separator_length_at(line, index)
        if separator_length:
            _append_segment(segments, line[start:index], line_number=line_number, start_column=start)
            index += separator_length
            start = index
            continue
        index += 1

    _append_segment(segments, line[start:], line_number=line_number, start_column=start)
    return tuple(segments)


def _append_segment(
    segments: list[_CommandSegment],
    text: str,
    *,
    line_number: int,
    start_column: int,
) -> None:
    stripped = text.lstrip()
    if not stripped:
        return
    leading = len(text) - len(stripped)
    segments.append(_CommandSegment(line_number=line_number, start_column=start_column + leading, text=stripped))


def _separator_length_at(line: str, index: int) -> int:
    char = line[index]
    if char == ";":
        return 1
    if char == "&":
        return 2 if index + 1 < len(line) and line[index + 1] == "&" else 1
    if char == "|":
        return 2 if index + 1 < len(line) and line[index + 1] == "|" else 1
    return 0


def _tokenize_segment(segment: str) -> tuple[_Token, ...]:
    return tuple(_Token(match.group(0), match.start()) for match in re.finditer(r"\S+", segment))


def _is_assignment(token: str) -> bool:
    return re.match(r"^[A-Za-z_][A-Za-z0-9_]*=.*$", token) is not None


def _shell_visible_text(line: str) -> str:
    result: list[str] = []
    quote: str | None = None
    escaped = False

    for char in line:
        if escaped:
            if quote is None:
                result.append(" ")
            escaped = False
            continue

        if quote == '"' and char == "\\":
            result.append(" ")
            escaped = True
            continue

        if quote is None and char == "\\":
            result.append(" ")
            escaped = True
            continue

        if quote is None and char in ("'", '"'):
            result.append(" ")
            quote = char
            continue

        if quote is not None:
            result.append(" ")
            if char == quote:
                quote = None
            continue

        if char == "#":
            break

        result.append(char)

    return "".join(result)
