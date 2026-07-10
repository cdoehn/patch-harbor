from __future__ import annotations

import argparse
import importlib.util
import json
import shlex
import subprocess
import sys
from pathlib import Path
from typing import Sequence

try:
    from patchharbor import __version__
except ImportError:
    __version__ = "0.1.0"

from patchharbor.patch_lint import PatchLintError
from patchharbor.environment_check import EnvironmentCheck, EnvironmentCheckError, EnvironmentCheckResult, EnvironmentCheckSpec
from patchharbor.patch_lint_api import lint_patch_file, render_patch_lint_result
from patchharbor.public_audit import PublicAuditModelError, PublicAuditPattern, PublicAuditTarget
from patchharbor.public_audit_checks import PublicAuditCheckError, scan_public_audit_targets
from patchharbor.runner_core import RunnerCoreError, RunnerExecutionConfig, run_patch_script
from patchharbor.runner_display import render_runner_result
from patchharbor.workflow_rule_store import (
    DEFAULT_WORKFLOW_RULES_PATH,
    load_workflow_rules_file,
    write_workflow_rules_file,
)
from patchharbor.workflow_rules import VALID_SEVERITIES, WorkflowRule, WorkflowRulesError, WorkflowRuleSet


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="patchharbor",
        description="Repository-agnostic development script and patch workflow tools.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"patchharbor {__version__}",
        help="print the PatchHarbor version and exit",
    )
    subparsers = parser.add_subparsers(dest="command")

    doctor = subparsers.add_parser(
        "doctor",
        help="print a minimal local environment check",
    )
    doctor.add_argument(
        "--repo",
        default=".",
        help="repository path to check; defaults to the current working directory",
    )

    lint_script = subparsers.add_parser(
        "lint-script",
        help="lint a patch script file",
    )
    lint_script.add_argument(
        "path",
        help="patch script file to lint",
    )

    run_script = subparsers.add_parser(
        "run-script",
        help="run preflight checks and optionally execute an explicit patch script file",
    )
    run_script.add_argument(
        "path",
        help="patch script file to run",
    )
    run_script.add_argument(
        "--no-execute",
        action="store_true",
        help="perform preflight, syntax, and optional lint checks without executing the script",
    )
    run_script.add_argument(
        "--lint",
        action="store_true",
        help="run PatchHarbor patch lint before execution",
    )
    run_script.add_argument(
        "--successful-patch-id",
        action="append",
        default=[],
        help="patch id that has already succeeded; may be provided multiple times for repeat checks",
    )
    run_script.add_argument(
        "--max-age-seconds",
        type=float,
        default=None,
        help="maximum allowed script age in seconds; omitted disables freshness checking",
    )
    run_script.add_argument(
        "--timeout-seconds",
        type=float,
        default=None,
        help="timeout in seconds for bash syntax and script execution",
    )
    run_script.add_argument(
        "--workdir",
        default=None,
        help="working directory for script execution",
    )
    run_script.add_argument(
        "--env",
        action="append",
        default=[],
        metavar="KEY=VALUE",
        help="environment variable to pass to the script; may be provided multiple times",
    )

    audit_public = subparsers.add_parser(
        "audit-public",
        help="scan repository targets for user-provided public-audit patterns",
    )
    audit_public.add_argument(
        "--repo",
        default=".",
        help="repository path to scan; defaults to the current working directory",
    )
    audit_public.add_argument(
        "--pattern",
        action="append",
        default=[],
        metavar="NAME=VALUE",
        help="pattern to scan for; may be NAME=VALUE or NAME:SEVERITY=VALUE",
    )
    audit_public.add_argument(
        "--target",
        action="append",
        default=[],
        metavar="PATH",
        help="relative target file to scan; defaults to git tracked files",
    )
    audit_public.add_argument(
        "--encoding",
        default="utf-8",
        help="text encoding for scanned files; defaults to utf-8",
    )

    check_env = subparsers.add_parser(
        "check-env",
        help="run generic repository environment checks",
    )
    check_env.add_argument(
        "--repo",
        default=".",
        help="repository path to check; defaults to the current working directory",
    )
    check_env.add_argument(
        "--no-defaults",
        action="store_true",
        help="do not add the default generic git/python checks",
    )
    check_env.add_argument(
        "--command",
        dest="env_command",
        action="append",
        default=[],
        metavar="NAME=COMMAND",
        help="command check; may be NAME=COMMAND or NAME:optional=COMMAND",
    )
    check_env.add_argument(
        "--file",
        action="append",
        default=[],
        metavar="NAME=PATH",
        help="file-exists check; may be NAME=PATH or NAME:optional=PATH",
    )
    check_env.add_argument(
        "--git-config",
        action="append",
        default=[],
        metavar="NAME=KEY",
        help="git config key check; may be NAME=KEY or NAME:optional=KEY",
    )
    check_env.add_argument(
        "--python-module",
        action="append",
        default=[],
        metavar="NAME=MODULE",
        help="Python import check; may be NAME=MODULE or NAME:optional=MODULE",
    )
    check_env.add_argument(
        "--optional",
        action="append",
        default=[],
        metavar="NAME",
        help="mark a named check as optional; may be provided multiple times",
    )

    rules = subparsers.add_parser(
        "rules",
        help="manage a workflow-rules JSON file",
    )
    rules_subparsers = rules.add_subparsers(dest="rules_command", required=True)
    rules_common = argparse.ArgumentParser(add_help=False)
    rules_common.add_argument(
        "--file",
        default=str(DEFAULT_WORKFLOW_RULES_PATH),
        help="workflow-rules JSON file; defaults to patch-workflow-rules.json",
    )

    rules_add = rules_subparsers.add_parser(
        "add",
        parents=[rules_common],
        help="add one workflow rule",
    )
    rules_add.add_argument("--id", required=True, help="unique stable rule id")
    rules_add.add_argument("--description", required=True, help="human-readable rule description")
    rules_add.add_argument("--category", default="general", help="rule category; defaults to general")
    rules_add.add_argument(
        "--severity",
        choices=sorted(VALID_SEVERITIES),
        default="error",
        help="diagnostic severity; defaults to error",
    )
    enabled_group = rules_add.add_mutually_exclusive_group()
    enabled_group.add_argument(
        "--enabled", dest="enabled", action="store_true", help="store the rule as enabled"
    )
    enabled_group.add_argument(
        "--disabled", dest="enabled", action="store_false", help="store the rule as disabled"
    )
    rules_add.set_defaults(enabled=True)

    rules_delete = rules_subparsers.add_parser(
        "delete",
        parents=[rules_common],
        help="delete one workflow rule by id",
    )
    rules_delete.add_argument("id", help="rule id to delete")

    rules_subparsers.add_parser(
        "list",
        parents=[rules_common],
        help="show all workflow rules in a human-readable table",
    )
    rules_subparsers.add_parser(
        "dump",
        parents=[rules_common],
        help="write the complete workflow-rules JSON document to stdout",
    )

    return parser


def _git_root(path: Path) -> Path | None:
    result = subprocess.run(
        ["git", "-C", str(path), "rev-parse", "--show-toplevel"],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if result.returncode != 0:
        return None
    return Path(result.stdout.strip()).resolve()


def _run_doctor(repo: str) -> int:
    repo_path = Path(repo).expanduser()
    print("PatchHarbor doctor")

    if not repo_path.exists():
        print("status: error")
        print(f"repository path: {repo_path}")
        print("git repository: no")
        return 1

    root = _git_root(repo_path)
    if root is None:
        print("status: error")
        print(f"repository path: {repo_path.resolve()}")
        print("git repository: no")
        return 1

    print("status: ok")
    print("git repository: yes")
    print(f"repository root: {root}")
    return 0


def _run_lint_script(path: str) -> int:
    print("PatchHarbor lint-script")
    print(f"script: {Path(path).expanduser()}")
    try:
        result = lint_patch_file(path)
    except PatchLintError as exc:
        print("status: error")
        print(f"problem: {exc}")
        return 2

    for line in render_patch_lint_result(result):
        print(line)

    return 1 if result.has_findings else 0


def _run_run_script(args: argparse.Namespace) -> int:
    print("PatchHarbor run-script")
    print(f"script: {Path(args.path).expanduser()}")

    try:
        environment = _parse_env_pairs(args.env)
        config = RunnerExecutionConfig(
            working_directory=args.workdir,
            environment=environment,
            successful_patch_ids=tuple(args.successful_patch_id),
            max_age_seconds=args.max_age_seconds,
            timeout_seconds=args.timeout_seconds,
            run_lint=args.lint,
            execute=not args.no_execute,
        )
        result = run_patch_script(args.path, config)
    except (RunnerCoreError, ValueError) as exc:
        print("status: error")
        print(str(exc))
        return 2

    for line in render_runner_result(result):
        print(line)

    return 0 if result.ok else 1


def _run_audit_public(args: argparse.Namespace) -> int:
    print("PatchHarbor audit-public")
    print(f"repository: {Path(args.repo).expanduser()}")

    try:
        repo_path = Path(args.repo).expanduser()
        root = _require_git_root(repo_path)
        patterns = _parse_public_audit_patterns(args.pattern)
        targets = _public_audit_targets(root, args.target)
        result = scan_public_audit_targets(root, targets, patterns, encoding=args.encoding)
    except (PublicAuditModelError, PublicAuditCheckError, ValueError) as exc:
        print("status: error")
        print(f"problem: {exc}")
        return 2

    print(f"repository root: {root}")
    print(f"scanned targets: {result.scanned_targets}")
    print(f"skipped targets: {result.skipped_targets}")
    print(f"findings: {result.finding_count}")

    if result.finding_count:
        for finding in result.findings:
            column = "" if finding.column is None else f":{finding.column}"
            print(
                f"{finding.path}:{finding.line}{column}: "
                f"{finding.severity}/{finding.pattern.name}: {finding.text}"
            )

    if result.failed:
        print("status: failed")
        return 1
    if result.finding_count:
        print("status: warning")
        return 0

    print("status: ok")
    return 0


def _parse_public_audit_patterns(values: Sequence[str]) -> tuple[PublicAuditPattern, ...]:
    if not values:
        raise ValueError("at least one --pattern is required")
    patterns: list[PublicAuditPattern] = []
    for value in values:
        if "=" not in value:
            raise ValueError(f"public audit pattern must use NAME=VALUE syntax: {value}")
        name_part, pattern_value = value.split("=", 1)
        if ":" in name_part:
            name, severity = name_part.split(":", 1)
        else:
            name, severity = name_part, "error"
        patterns.append(PublicAuditPattern(name=name, value=pattern_value, severity=severity))
    return tuple(patterns)


def _public_audit_targets(root: Path, values: Sequence[str]) -> tuple[PublicAuditTarget, ...]:
    if values:
        return tuple(PublicAuditTarget(value) for value in values)

    result = subprocess.run(
        ["git", "-C", str(root), "ls-files"],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if result.returncode != 0:
        raise ValueError("git ls-files failed while discovering public audit targets")
    targets = tuple(PublicAuditTarget(line) for line in result.stdout.splitlines() if line.strip())
    if not targets:
        raise ValueError("public audit target discovery found no tracked files")
    return targets


def _require_git_root(path: Path) -> Path:
    if not path.exists():
        raise ValueError(f"repository path does not exist: {path}")
    root = _git_root(path)
    if root is None:
        raise ValueError(f"repository path is not a git repository: {path.resolve()}")
    return root


def _run_check_env(args: argparse.Namespace) -> int:
    print("PatchHarbor check-env")
    print(f"repository: {Path(args.repo).expanduser()}")

    try:
        repo_path = Path(args.repo).expanduser()
        root = _require_git_root(repo_path)
        specs = _environment_check_specs_from_args(args)
        result = _run_environment_check_specs(root, specs)
    except (EnvironmentCheckError, ValueError) as exc:
        print("status: error")
        print(f"problem: {exc}")
        return 2

    print(f"repository root: {root}")
    print(f"checks: {result.total_count}")
    for check in result.checks:
        marker = "OK" if check.ok else ("FAIL" if check.required else "WARN")
        print(f"[{marker}] {check.name}: {check.detail}")
        if check.failed and check.hint:
            print(f"hint: {check.hint}")

    if result.required_failed_count:
        print("status: failed")
        return 1
    if result.optional_failed_count:
        print("status: warning")
        return 0

    print("status: ok")
    return 0


def _environment_check_specs_from_args(args: argparse.Namespace) -> tuple[EnvironmentCheckSpec, ...]:
    optional_names = set(args.optional)
    specs: list[EnvironmentCheckSpec] = []

    if not args.no_defaults:
        specs.extend(
            [
                EnvironmentCheckSpec(name="git repository", check_type="custom", category="repository"),
                EnvironmentCheckSpec(name="git user.name", check_type="git-config", path="user.name", category="git"),
                EnvironmentCheckSpec(name="git user.email", check_type="git-config", path="user.email", category="git"),
                EnvironmentCheckSpec(name="python", check_type="command", command=(sys.executable, "--version"), category="runtime"),
            ]
        )

    specs.extend(_parse_environment_check_option_values("command", args.env_command, optional_names=optional_names))
    specs.extend(_parse_environment_check_option_values("file", args.file, optional_names=optional_names))
    specs.extend(_parse_environment_check_option_values("git-config", args.git_config, optional_names=optional_names))
    specs.extend(_parse_environment_check_option_values("python-module", args.python_module, optional_names=optional_names))
    return tuple(specs)


def _parse_environment_check_option_values(
    check_type: str,
    values: Sequence[str],
    *,
    optional_names: set[str],
) -> tuple[EnvironmentCheckSpec, ...]:
    specs: list[EnvironmentCheckSpec] = []
    for value in values:
        name, required, payload = _parse_environment_check_assignment(value, optional_names=optional_names)
        if check_type == "command":
            command = tuple(shlex.split(payload))
            specs.append(EnvironmentCheckSpec(name=name, check_type=check_type, command=command, required=required, category="tooling"))
        elif check_type == "file":
            specs.append(EnvironmentCheckSpec(name=name, check_type=check_type, path=payload, required=required, category="files"))
        elif check_type == "git-config":
            specs.append(EnvironmentCheckSpec(name=name, check_type=check_type, path=payload, required=required, category="git"))
        elif check_type == "python-module":
            specs.append(EnvironmentCheckSpec(name=name, check_type=check_type, path=payload, required=required, category="python"))
        else:
            raise ValueError(f"unknown environment check type: {check_type}")
    return tuple(specs)


def _parse_environment_check_assignment(value: str, *, optional_names: set[str]) -> tuple[str, bool, str]:
    if "=" not in value:
        raise ValueError(f"environment check value must use NAME=VALUE syntax: {value}")
    name_part, payload = value.split("=", 1)
    if not payload.strip():
        raise ValueError(f"environment check value must not be empty: {value}")

    required = True
    if ":" in name_part:
        name, mode = name_part.split(":", 1)
        if mode not in {"required", "optional"}:
            raise ValueError(f"environment check mode must be required or optional: {value}")
        required = mode == "required"
    else:
        name = name_part

    if name in optional_names:
        required = False
    if not name.strip():
        raise ValueError(f"environment check name must not be empty: {value}")
    return name, required, payload


def _run_environment_check_specs(root: Path, specs: Sequence[EnvironmentCheckSpec]) -> EnvironmentCheckResult:
    checks: list[EnvironmentCheck] = []
    for spec in specs:
        checks.append(_run_environment_check_spec(root, spec))
    return EnvironmentCheckResult(tuple(checks), metadata={"repo": str(root)})


def _run_environment_check_spec(root: Path, spec: EnvironmentCheckSpec) -> EnvironmentCheck:
    if spec.check_type == "custom":
        return EnvironmentCheck(spec.name, True, str(root), required=spec.required, category=spec.category, metadata=spec.metadata)
    if spec.check_type == "command":
        return _run_environment_command_check(root, spec)
    if spec.check_type == "file":
        target = (root / spec.path).resolve()
        ok = target.exists()
        detail = str(target) if ok else f"missing: {spec.path}"
        return EnvironmentCheck(spec.name, ok, detail, hint=spec.hint, required=spec.required, category=spec.category, metadata=spec.metadata)
    if spec.check_type == "git-config":
        result = subprocess.run(
            ["git", "-C", str(root), "config", "--get", spec.path],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        value = result.stdout.strip()
        ok = result.returncode == 0 and bool(value)
        return EnvironmentCheck(
            spec.name,
            ok,
            value or "not configured",
            hint=spec.hint,
            required=spec.required,
            category=spec.category,
            metadata=spec.metadata,
        )
    if spec.check_type == "python-module":
        found = importlib.util.find_spec(spec.path) is not None
        detail = f"module available: {spec.path}" if found else f"module not found: {spec.path}"
        return EnvironmentCheck(spec.name, found, detail, hint=spec.hint, required=spec.required, category=spec.category, metadata=spec.metadata)
    raise ValueError(f"unsupported environment check type: {spec.check_type}")


def _run_environment_command_check(root: Path, spec: EnvironmentCheckSpec) -> EnvironmentCheck:
    try:
        result = subprocess.run(
            list(spec.command),
            cwd=root,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
    except OSError as exc:
        command_name = spec.command[0] if spec.command else "<empty>"
        detail = f"{command_name} not found in PATH" if isinstance(exc, FileNotFoundError) else f"{command_name} could not run: {exc.strerror}"
        return EnvironmentCheck(
            spec.name,
            False,
            detail,
            hint=spec.hint,
            required=spec.required,
            category=spec.category,
            metadata=spec.metadata,
        )

    output_lines = (result.stdout or result.stderr).strip().splitlines()
    detail = output_lines[0] if output_lines else f"exit {result.returncode}"
    return EnvironmentCheck(
        spec.name,
        result.returncode == 0,
        detail,
        hint=spec.hint if result.returncode != 0 else "",
        required=spec.required,
        category=spec.category,
        metadata=spec.metadata,
    )


def _run_rules(args: argparse.Namespace) -> int:
    file_path = Path(args.file).expanduser()
    try:
        if args.rules_command == "add":
            ruleset = load_workflow_rules_file(file_path, missing_ok=True)
            if args.id in ruleset.by_id():
                raise WorkflowRulesError(f"workflow rule id already exists: {args.id}")
            rule = WorkflowRule(
                id=args.id,
                description=args.description,
                category=args.category,
                severity=args.severity,
                enabled=args.enabled,
            )
            updated = WorkflowRuleSet(
                version=ruleset.version,
                rules=(*ruleset.rules, rule),
                source=ruleset.source,
            )
            write_workflow_rules_file(file_path, updated)
            print(f"added workflow rule: {rule.id}")
            print(f"file: {file_path}")
            return 0

        if args.rules_command == "delete":
            ruleset = load_workflow_rules_file(file_path)
            if args.id not in ruleset.by_id():
                raise WorkflowRulesError(f"workflow rule id does not exist: {args.id}")
            updated = WorkflowRuleSet(
                version=ruleset.version,
                rules=tuple(rule for rule in ruleset.rules if rule.id != args.id),
                source=ruleset.source,
            )
            write_workflow_rules_file(file_path, updated)
            print(f"deleted workflow rule: {args.id}")
            print(f"file: {file_path}")
            return 0

        ruleset = load_workflow_rules_file(file_path, missing_ok=True)
        if args.rules_command == "dump":
            print(json.dumps(ruleset.to_mapping(), indent=2, ensure_ascii=False))
            return 0
        if args.rules_command == "list":
            _print_workflow_rules(ruleset)
            return 0
    except WorkflowRulesError as exc:
        print(f"problem: {exc}", file=sys.stderr)
        return 2

    print(f"problem: unsupported rules command: {args.rules_command}", file=sys.stderr)
    return 2


def _print_workflow_rules(ruleset: WorkflowRuleSet) -> None:
    if not ruleset.rules:
        print("No workflow rules configured.")
        return

    headers = ("ID", "SEVERITY", "ENABLED", "CATEGORY", "DESCRIPTION")
    rows = [
        (rule.id, rule.severity, "yes" if rule.enabled else "no", rule.category, rule.description)
        for rule in ruleset.rules
    ]
    widths = [
        max(len(headers[index]), *(len(row[index]) for row in rows))
        for index in range(len(headers) - 1)
    ]
    print(
        f"{headers[0]:<{widths[0]}}  {headers[1]:<{widths[1]}}  "
        f"{headers[2]:<{widths[2]}}  {headers[3]:<{widths[3]}}  {headers[4]}"
    )
    for row in rows:
        print(
            f"{row[0]:<{widths[0]}}  {row[1]:<{widths[1]}}  "
            f"{row[2]:<{widths[2]}}  {row[3]:<{widths[3]}}  {row[4]}"
        )


def _parse_env_pairs(values: Sequence[str]) -> dict[str, str]:
    environment: dict[str, str] = {}
    for value in values:
        if "=" not in value:
            raise ValueError(f"environment value must use KEY=VALUE syntax: {value}")
        key, env_value = value.split("=", 1)
        if not key:
            raise ValueError("environment variable name must not be empty")
        environment[key] = env_value
    return environment


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "doctor":
        return _run_doctor(args.repo)
    if args.command == "lint-script":
        return _run_lint_script(args.path)
    if args.command == "run-script":
        return _run_run_script(args)
    if args.command == "audit-public":
        return _run_audit_public(args)
    if args.command == "check-env":
        return _run_check_env(args)
    if args.command == "rules":
        return _run_rules(args)

    parser.print_help()
    return 0
