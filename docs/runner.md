# PatchHarbor runner documentation

This document is the consolidated public runner contract created by PATCHHARBOR.15b1.

It brings together the current runner API, lifecycle, compatibility, and migration-facing runner notes without deleting the historical source documents.

## Current runner surfaces

PatchHarbor exposes runner behavior through three public surfaces:

| Surface | Purpose | Status |
| --- | --- | --- |
| `patchharbor run-script` | run a patch script through PatchHarbor runner behavior | active public CLI |
| `patchharbor lint-script` | validate patch script structure before execution | active public CLI |
| `patchharbor doctor --repo` | check repository/environment assumptions | active public CLI |

The implementation is owned by the PatchHarbor package:

| Path | Role |
| --- | --- |
| `src/patchharbor/runner_core.py` | runner lifecycle and execution behavior |
| `src/patchharbor/cli.py` | command-line parser and command dispatch |
| `src/patchharbor/patch_lint_api.py` | public lint API used by lint-script and tests |
| `src/patchharbor/patch_lint.py` | lint implementation |
| `src/patchharbor/console.py` | console formatting helpers |

## Runner lifecycle

The runner lifecycle contract is:

1. resolve the script path
2. validate that the script exists
3. validate script freshness when freshness checks are enabled
4. run Bash syntax checks
5. run preflight linting where requested
6. execute the patch script
7. preserve and report the exit code
8. write or preserve diagnostics
9. avoid mutating the wrong repository
10. keep output stable for source wrappers and users

PatchHarbor runner behavior is generic. RepoDossier-specific Download handling remains in the RepoDossier source-side `c` runner until a later milestone explicitly changes that workflow.

## Compatibility boundary

PatchHarbor runner behavior must preserve these compatibility rules:

- source wrappers may call PatchHarbor commands without changing their user-facing alias names
- target runner behavior must not require RepoDossier-only source paths
- target-only patches must not edit RepoDossier source files
- source-only patches must not edit PatchHarbor target files
- runner output should remain stable enough for wrapper and acceptance tests
- failures must be explicit and diagnosable

## Source wrapper relationship

RepoDossier currently keeps product-specific workflows in source-side scripts.

PatchHarbor provides generic runner infrastructure.

Current relationship:

| RepoDossier source workflow | PatchHarbor target support |
| --- | --- |
| `c` Download patch runner | uses PatchHarbor `lint-script` for dry-run preflight |
| `run_patchharbor_patch.sh` source wrapper | bridges source workflow to PatchHarbor runner behavior |
| `r` export runner | RepoDossier-specific and not a PatchHarbor runner responsibility |

PatchHarbor must not assume that a RepoDossier source checkout exists unless a compatibility test explicitly sets up that condition.

## Public examples

Run a script through PatchHarbor:

    patchharbor run-script ./example_patch.sh

Lint a script without running it:

    patchharbor lint-script ./example_patch.sh

Check a repository:

    patchharbor doctor --repo .

Show command help:

    patchharbor run-script --help
    patchharbor lint-script --help
    patchharbor doctor --help

## Related documents

This consolidated document supersedes these documents for public runner reading order:

| Path | Current role after PATCHHARBOR.15b1 |
| --- | --- |
| `docs/download-runner-api-inventory.md` | historical input and API reference for runner consolidation |
| `docs/download-runner-lifecycle-plan-acceptance.md` | lifecycle acceptance input |
| `docs/runner-compatibility-acceptance.md` | compatibility acceptance input |
| `docs/runner-compatibility-migration.md` | historical migration input |

The related documents are not deleted by PATCHHARBOR.15b1.

## Acceptance expectations

Runner documentation is accepted when:

1. `docs/runner.md` exists.
2. CLI runner commands are named explicitly.
3. target implementation paths are named explicitly.
4. lifecycle steps are documented.
5. source wrapper compatibility boundary is documented.
6. related historical documents are listed.
7. target tests cover the consolidated document.
8. target-only docs patches leave RepoDossier unchanged.

## Non-goals

PATCHHARBOR.15b1 does not:

- change runner code
- change CLI code
- change source wrappers
- edit RepoDossier
- delete migration documents
- mark migration documents historical
- consolidate CLI docs
- consolidate compatibility docs
- change package metadata

Compatibility docs are consolidated by PATCHHARBOR.15b2.

CLI docs are consolidated by PATCHHARBOR.15b3.

Historical migration docs are marked historical by PATCHHARBOR.15b4.
