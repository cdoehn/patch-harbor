from __future__ import annotations

from pathlib import Path
from typing import Callable, Iterable, Sequence

from patchharbor.patch_lint import PatchLintError, PatchLintResult, sort_findings
from patchharbor.patch_lint_rules import (
    lint_git_pager_commands,
    lint_markdown_fence_literals,
    lint_missing_footer,
    lint_missing_test_execution,
)


PatchLintRule = Callable[[str], PatchLintResult]

DEFAULT_PATCH_LINT_RULES: tuple[PatchLintRule, ...] = (
    lint_git_pager_commands,
    lint_missing_footer,
    lint_missing_test_execution,
    lint_markdown_fence_literals,
)


def default_patch_lint_rules() -> tuple[PatchLintRule, ...]:
    return DEFAULT_PATCH_LINT_RULES


def lint_patch_text(
    text: str,
    *,
    rules: Sequence[PatchLintRule] | None = None,
    sort: bool = True,
) -> PatchLintResult:
    if not isinstance(text, str):
        raise PatchLintError("patch text must be a string")

    selected_rules = _normalize_rules(rules)
    result = PatchLintResult()

    for rule in selected_rules:
        rule_result = rule(text)
        if not isinstance(rule_result, PatchLintResult):
            rule_name = getattr(rule, "__name__", repr(rule))
            raise PatchLintError(f"patch lint rule did not return PatchLintResult: {rule_name}")
        result = result.extend(rule_result.findings)

    if sort:
        return PatchLintResult(sort_findings(result.findings))
    return result


def lint_patch_file(
    path: str | Path,
    *,
    rules: Sequence[PatchLintRule] | None = None,
    sort: bool = True,
) -> PatchLintResult:
    file_path = Path(path)
    try:
        text = file_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise PatchLintError(f"unable to read patch script: {file_path}") from exc
    return lint_patch_text(text, rules=rules, sort=sort)


def lint_patch_files(
    paths: Iterable[str | Path],
    *,
    rules: Sequence[PatchLintRule] | None = None,
    sort: bool = True,
) -> dict[Path, PatchLintResult]:
    if isinstance(paths, (str, bytes, Path)):
        raise PatchLintError("patch file collection must be an iterable of paths, not a single path")

    results: dict[Path, PatchLintResult] = {}
    for path in paths:
        file_path = Path(path)
        results[file_path] = lint_patch_file(file_path, rules=rules, sort=sort)
    return results


def render_patch_lint_result(result: PatchLintResult) -> tuple[str, ...]:
    if not isinstance(result, PatchLintResult):
        raise PatchLintError("result must be a PatchLintResult")

    if not result.has_findings:
        return ("status: ok",)

    if result.errors:
        status = "status: error"
    elif result.warnings:
        status = "status: warning"
    else:
        status = "status: info"

    return (status, *result.render_findings())


def patch_lint_rule_names(rules: Sequence[PatchLintRule] | None = None) -> tuple[str, ...]:
    return tuple(getattr(rule, "__name__", repr(rule)) for rule in _normalize_rules(rules))


def _normalize_rules(rules: Sequence[PatchLintRule] | None) -> tuple[PatchLintRule, ...]:
    if rules is None:
        return DEFAULT_PATCH_LINT_RULES

    normalized = tuple(rules)
    for rule in normalized:
        if not callable(rule):
            raise PatchLintError("patch lint rules must be callable")
    return normalized
