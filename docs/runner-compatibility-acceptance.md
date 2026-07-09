# PatchHarbor.06 runner and compatibility acceptance

PatchHarbor.06 establishes the generic runner and compatibility foundation in the target repository.

This phase is intentionally limited to reusable primitives and an explicit CLI command. It does not replace any source-repository wrapper, local alias, or automatic download-folder workflow.

## Accepted scope

PatchHarbor.06 is accepted when the target repository contains:

- runner and compatibility migration inventory documentation
- a generic runner result and status model
- preflight APIs for metadata, repeat detection, and freshness checks
- download-file discovery and lifecycle planning without mutation
- an explicit script runner core
- a context, milestone, result, and footer display renderer
- a `patchharbor run-script <file>` CLI command for explicit runner use
- tests for each component and acceptance tests for the full phase boundary

## Current target components

| Component | Path |
| --- | --- |
| migration inventory | `docs/runner-compatibility-migration.md` |
| runner status model | `src/patchharbor/runner_status.py` |
| runner preflight APIs | `src/patchharbor/runner_preflight.py` |
| download discovery and lifecycle planning | `src/patchharbor/runner_lifecycle.py` |
| explicit script runner core | `src/patchharbor/runner_core.py` |
| runner display renderer | `src/patchharbor/runner_display.py` |
| explicit CLI command | `src/patchharbor/cli.py` |
| runner status tests | `tests/test_runner_status.py` |
| runner preflight tests | `tests/test_runner_preflight.py` |
| runner lifecycle tests | `tests/test_runner_lifecycle.py` |
| runner core tests | `tests/test_runner_core.py` |
| runner display tests | `tests/test_runner_display.py` |
| runner CLI tests | `tests/test_cli_runner.py` |

## Accepted behavior

The status model can represent runner phases, issues, aggregate results, skipped phases, and derived status.

The preflight API validates patch metadata through the target metadata contract, detects repeated patch identifiers, and checks script freshness when requested.

The lifecycle API can discover candidate scripts and plan success or failure destinations, but it does not move files or create download lifecycle directories.

The runner core can run preflight checks, Bash syntax checks, optional patch lint checks, and optional execution for a script path that the caller provides explicitly.

The display renderer can render progress metadata, phase summaries, effective runner status, issue details, and footer lines. Display code derives the user-facing status from phases and issues when a result was constructed directly.

The CLI exposes `patchharbor run-script <file>` for explicit manual use. It can disable execution, enable linting, pass environment variables, set a working directory, set a timeout, set freshness limits, and provide successful patch identifiers for repeat checks.

Existing `patchharbor lint-script` output remains compatible with the earlier linting phase. Missing or unreadable files return status error with a `problem:` line.

## Explicit non-goals

PatchHarbor.06 does not introduce:

- automatic newest-download script selection in the CLI
- moving successful scripts into a done directory
- moving failed scripts into a failed directory
- alias installation
- shell rc-file edits
- source-repository wrapper changes
- automatic compatibility command replacement
- project-specific default paths
- source-repository commits
- background execution or asynchronous monitoring

Those behaviors belong to later compatibility or wrapper phases after the generic target-side contracts are stable.

## Compatibility boundary

PatchHarbor now owns the reusable runner primitives:

- status and issue data
- metadata, repeat, and freshness preflight behavior
- lifecycle planning
- explicit script execution
- display rendering
- explicit CLI invocation

Source repositories should later use thin wrappers or configuration for local aliases, repository-specific paths, download-folder defaults, and compatibility command names.

The generic target APIs must remain safe for other repositories. They should not depend on a contributor's home directory, private address, workstation name, source checkout location, or a particular local shell alias.

## Acceptance checks

The phase is accepted when the target repository passes:

    python3 -m compileall src tests
    PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_*.py'
    PYTHONPATH=src python3 -m patchharbor doctor --repo .

Manual smoke checks can use:

    patchharbor run-script path/to/patch.sh --no-execute
    patchharbor run-script path/to/patch.sh --lint --env KEY=VALUE
    patchharbor lint-script path/to/patch.sh

The explicit runner command should report structured runner phase output and should not mutate download lifecycle directories.
