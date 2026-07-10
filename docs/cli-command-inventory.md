# PATCHHARBOR.13a1 – CLI Command Inventory

This document inventories the current PatchHarbor command-line surface before the `PATCHHARBOR.13a2 – CLI Exit Code Contract` and `PATCHHARBOR.13a3 – CLI Help Snapshot Tests` steps.

The source of truth for command behavior is `src/patchharbor/cli.py`. The packaging entry point is defined in `pyproject.toml` as:

    patchharbor = "patchharbor.cli:main"

The module entry point `python -m patchharbor` is provided by `src/patchharbor/__main__.py`.

## Inventory policy

This inventory is functional, not a terminal-layout snapshot.

It records:

- command names
- required and optional arguments
- implementation entry functions
- model/helper dependencies
- expected high-level status categories

It does not freeze exact help text wrapping, terminal colors, column widths, or cosmetic display order. Display-only assertions belong to explicit help/display tests and should not block functional migration unless the display is itself the contract under review.

## Top-level command

| Command surface | Implementation | Notes |
| --- | --- | --- |
| `patchharbor` | `patchharbor.cli:main` | console script from `pyproject.toml` |
| `python -m patchharbor` | `patchharbor.__main__` | module execution path |
| `patchharbor --version` | argparse version action | prints package version |
| `patchharbor` without subcommand | `build_parser().print_help()` | prints help and exits successfully |

## Subcommand inventory

| Subcommand | Implementation function | Main dependencies | Current purpose |
| --- | --- | --- | --- |
| `doctor` | `_run_doctor(repo)` | `git rev-parse --show-toplevel` | minimal repository sanity check |
| `lint-script` | `_run_lint_script(path)` | `patchharbor.patch_lint_api` | lint one patch script file |
| `run-script` | `_run_run_script(args)` | `RunnerExecutionConfig`, `run_patch_script`, `render_runner_result` | run PatchHarbor preflight, optional lint, and optional script execution |
| `audit-public` | `_run_audit_public(args)` | `PublicAuditPattern`, `PublicAuditTarget`, `scan_public_audit_targets` | scan repository targets for caller-provided public-audit patterns |
| `check-env` | `_run_check_env(args)` | `EnvironmentCheck`, `EnvironmentCheckSpec`, `EnvironmentCheckResult` | run generic repository environment checks |

## Command details

### `doctor`

Purpose:

- Checks whether `--repo` exists.
- Checks whether `--repo` resolves to a Git repository.
- Prints the resolved repository root on success.

Options:

| Option | Required | Meaning |
| --- | --- | --- |
| `--repo PATH` | no | repository path to check; defaults to current directory |

High-level result categories:

| Category | Meaning |
| --- | --- |
| ok | repository exists and is inside a Git worktree |
| error | repository path does not exist or is not a Git repository |

### `lint-script`

Purpose:

- Runs PatchHarbor's patch-script lint API against one explicit script file.
- Renders lint findings through the lint API renderer.

Arguments:

| Argument | Required | Meaning |
| --- | --- | --- |
| `path` | yes | patch script file to lint |

High-level result categories:

| Category | Meaning |
| --- | --- |
| ok | lint result has no findings |
| findings | lint result contains at least one finding |
| error | lint input/model handling failed |

### `run-script`

Purpose:

- Executes the generic PatchHarbor runner path for one explicit patch script.
- Supports preflight-only mode through `--no-execute`.
- Supports optional patch linting before execution.
- Supports repeat, freshness, timeout, working-directory, and environment configuration.

Arguments and options:

| Option | Required | Meaning |
| --- | --- | --- |
| `path` | yes | patch script file to run |
| `--no-execute` | no | run preflight/syntax/lint path without executing the script |
| `--lint` | no | run patch lint before execution |
| `--successful-patch-id ID` | no | repeat guard input; may be provided multiple times |
| `--max-age-seconds SECONDS` | no | freshness limit for patch scripts |
| `--timeout-seconds SECONDS` | no | timeout for syntax and execution subprocesses |
| `--workdir DIR` | no | working directory for script execution |
| `--env KEY=VALUE` | no | additional environment variable; may be provided multiple times |

High-level result categories:

| Category | Meaning |
| --- | --- |
| ok | runner result is successful |
| failed | preflight, lint, syntax, or execution result is not successful |
| error | runner configuration or core execution setup failed |

### `audit-public`

Purpose:

- Builds public-audit patterns from caller-provided `--pattern` values.
- Scans explicit `--target` values or Git-tracked files by default.
- Reports findings through generic PatchHarbor public-audit models.

Options:

| Option | Required | Meaning |
| --- | --- | --- |
| `--repo PATH` | no | repository path to scan; defaults to current directory |
| `--pattern NAME=VALUE` | yes | pattern to scan for |
| `--pattern NAME:SEVERITY=VALUE` | no | pattern with explicit severity |
| `--target PATH` | no | relative target file; may be provided multiple times |
| `--encoding ENCODING` | no | target text encoding; defaults to UTF-8 |

High-level result categories:

| Category | Meaning |
| --- | --- |
| ok | no findings |
| warning | non-blocking findings exist |
| failed | blocking findings exist |
| error | repository, pattern, target, or model setup failed |

### `check-env`

Purpose:

- Builds generic environment check specs from command-line options.
- Runs default generic repository checks unless `--no-defaults` is provided.
- Supports command, file, Git config, and Python module checks.
- Treats optional failures as warnings.

Options:

| Option | Required | Meaning |
| --- | --- | --- |
| `--repo PATH` | no | repository path to check; defaults to current directory |
| `--no-defaults` | no | do not add default Git/Python checks |
| `--command NAME=COMMAND` | no | command check |
| `--command NAME:optional=COMMAND` | no | optional command check |
| `--file NAME=PATH` | no | file-exists check |
| `--file NAME:optional=PATH` | no | optional file-exists check |
| `--git-config NAME=KEY` | no | Git config key check |
| `--git-config NAME:optional=KEY` | no | optional Git config key check |
| `--python-module NAME=MODULE` | no | Python import check |
| `--python-module NAME:optional=MODULE` | no | optional Python import check |
| `--optional NAME` | no | mark a named check optional |

High-level result categories:

| Category | Meaning |
| --- | --- |
| ok | all checks pass |
| warning | only optional checks fail |
| failed | at least one required check fails |
| error | repository path or check specification is invalid |

## Current implementation dependencies

| Area | Files |
| --- | --- |
| CLI parser and dispatch | `src/patchharbor/cli.py` |
| console entry point | `pyproject.toml` |
| module entry point | `src/patchharbor/__main__.py` |
| lint command model/API | `src/patchharbor/patch_lint.py`, `src/patchharbor/patch_lint_api.py`, `src/patchharbor/patch_lint_rules.py` |
| runner command model/API | `src/patchharbor/runner_core.py`, `src/patchharbor/runner_display.py`, `src/patchharbor/runner_preflight.py`, `src/patchharbor/runner_status.py` |
| public audit model/API | `src/patchharbor/public_audit.py`, `src/patchharbor/public_audit_checks.py` |
| environment model/API | `src/patchharbor/environment_check.py` |

## Current CLI test coverage

| Area | Test files |
| --- | --- |
| base CLI and doctor | `tests/test_cli.py` |
| patch lint CLI | `tests/test_cli_patch_lint.py` |
| runner CLI | `tests/test_cli_runner.py` |
| public audit CLI | `tests/test_cli_public_audit.py` |
| environment CLI | `tests/test_cli_environment_check.py` |

## Non-goals for PATCHHARBOR.13a1

This patch does not:

- change CLI behavior
- change exit codes
- change help output
- add help snapshot tests
- change packaging metadata
- add or remove console scripts
- change source-side wrappers
- change source-side aliases
- change `c`
- change `r`
- add display-only assertions

## Acceptance for this patch

PATCHHARBOR.13a1 is accepted when:

- all current target-side subcommands are listed
- each subcommand has its implementation function documented
- each subcommand has arguments/options documented at a high level
- source-specific wrappers are not treated as target CLI commands
- display-only help formatting is explicitly out of scope
- the target CLI still exposes the documented commands through `build_parser()`
- the source repository remains unchanged
