# PATCHHARBOR.13a2 – CLI Exit Code Contract

This document defines the current PatchHarbor CLI exit-code contract after `PATCHHARBOR.13a1 – CLI Command Inventory` and before `PATCHHARBOR.13a3 – CLI Help Snapshot Tests`.

The source of truth for implementation remains `src/patchharbor/cli.py`. This document records functional return-code categories, not cosmetic terminal layout.

## Global exit-code categories

PatchHarbor CLI commands use the following high-level exit-code categories.

| Exit code | Category | Meaning |
| --- | --- | --- |
| `0` | ok / warning accepted | command completed successfully, or only non-blocking warnings were found |
| `1` | failed | command ran successfully but found a blocking finding, failed check, lint finding, or failed runner result |
| `2` | usage/configuration error | command input, repository path, pattern/spec syntax, or model setup is invalid |

The process may still return Python or system-level non-contract codes for unhandled exceptions or interpreter failures. Those are defects, not intended command contracts.

## Display policy

Exit codes are functional contracts.

The following are not exit-code contracts:

- exact help text wrapping
- cosmetic terminal colors
- spacing and column widths
- order of display-only status lines
- progress/context display blocks

Display-only tests should be skipped or kept separate unless the specific display output is the migration contract under review.

## Top-level command contract

| Invocation | Expected exit code | Notes |
| --- | --- | --- |
| `patchharbor --help` | `0` | argparse help |
| `patchharbor --version` | `0` | argparse version action |
| `patchharbor` | `0` | prints top-level help |
| unknown top-level option | `2` | argparse usage error |
| unknown subcommand | `2` | argparse usage error |

## Subcommand contracts

### `doctor`

Implementation:

    _run_doctor(repo)

Exit-code contract:

| Condition | Exit code | Required output category |
| --- | --- | --- |
| repository path exists and resolves to a Git root | `0` | `status: ok` |
| repository path does not exist | `2` | `status: error` and `problem:` |
| repository path is not a Git repository | `2` | `status: error` and `problem:` |

Functional notes:

- `doctor` is a configuration/repository check.
- Missing or invalid repository input is a usage/configuration error, not a failed audit.

### `lint-script`

Implementation:

    _run_lint_script(path)

Exit-code contract:

| Condition | Exit code | Required output category |
| --- | --- | --- |
| patch script has no lint findings | `0` | lint status indicates success |
| patch script has one or more lint findings | `1` | lint findings are rendered |
| lint input/model handling fails | `2` | `status: error` or equivalent problem output |

Functional notes:

- Lint findings are blocking for this command.
- Exact finding display formatting is not frozen by this document.

### `run-script`

Implementation:

    _run_run_script(args)

Exit-code contract:

| Condition | Exit code | Required output category |
| --- | --- | --- |
| preflight, optional lint, syntax, and execution succeed | `0` | runner result status is successful |
| `--no-execute` preflight path succeeds | `0` | preflight/syntax path is successful |
| preflight rejects script metadata/freshness/repeat/scope | `1` | runner result is unsuccessful |
| optional lint with findings rejects the script | `1` | runner result is unsuccessful |
| syntax check fails | `1` | runner result is unsuccessful |
| script execution exits non-zero | `1` | runner result is unsuccessful |
| runner configuration/model setup is invalid | `2` | `status: error` and `problem:` |

Functional notes:

- `run-script` compresses all unsuccessful runner lifecycle states into `1`.
- Configuration/model errors are `2`.
- Terminal progress display does not affect the exit code.

### `audit-public`

Implementation:

    _run_audit_public(args)

Exit-code contract:

| Condition | Exit code | Required output category |
| --- | --- | --- |
| no findings | `0` | `status: ok` |
| only non-blocking findings exist | `0` | `status: warning` |
| at least one blocking finding exists | `1` | `status: failed` |
| repository path, pattern syntax, target setup, or model setup is invalid | `2` | `status: error` and `problem:` |

Functional notes:

- Warning findings are intentionally non-blocking.
- Blocking findings fail the command with `1`.
- Pattern input requires `NAME=VALUE` or `NAME:SEVERITY=VALUE`.

### `check-env`

Implementation:

    _run_check_env(args)

Exit-code contract:

| Condition | Exit code | Required output category |
| --- | --- | --- |
| all checks pass | `0` | `status: ok` |
| only optional checks fail | `0` | `status: warning` |
| at least one required check fails | `1` | `status: failed` |
| repository path or check specification is invalid | `2` | `status: error` and `problem:` |

Functional notes:

- Optional failures are warnings and do not fail the process.
- Required failures fail the process with `1`.
- Check spec input uses `NAME=VALUE` or `NAME:optional=VALUE`.

## Command-to-test mapping

| Command | Existing tests expected to cover exit codes |
| --- | --- |
| top-level parser / `doctor` | `tests/test_cli.py` |
| `lint-script` | `tests/test_cli_patch_lint.py` |
| `run-script` | `tests/test_cli_runner.py` |
| `audit-public` | `tests/test_cli_public_audit.py` |
| `check-env` | `tests/test_cli_environment_check.py` |

## Acceptance for future exit-code tests

Future tests for this contract should assert:

- expected process return code
- stable functional status marker such as `status: ok`, `status: failed`, `status: warning`, or `status: error`
- stable problem marker such as `problem:` for configuration errors

Future tests should not assert:

- terminal color codes
- exact help wrapping
- exact display column widths
- progress-context placement
- cosmetic display order unless explicitly declared functional

## Non-goals for PATCHHARBOR.13a2

This patch does not:

- change CLI behavior
- change exit codes
- add exit-code tests
- add help snapshot tests
- change help output
- change packaging metadata
- change source-side wrappers
- change source-side aliases
- change `c`
- change `r`
- add display-only assertions

## Acceptance for this patch

PATCHHARBOR.13a2 is accepted when:

- every current target-side subcommand has an exit-code section
- `0`, `1`, and `2` categories are defined
- warning semantics are explicitly non-blocking for `audit-public` and `check-env`
- configuration/model errors are documented as exit code `2`
- runner lifecycle failures are documented as exit code `1`
- display-only assertions are explicitly out of scope
- the target CLI tests still pass
- the source repository remains unchanged
