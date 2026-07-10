# PatchHarbor CLI documentation

This document is the consolidated public CLI contract created by PATCHHARBOR.15b3.

It brings together command inventory, help behavior, exit codes, runner links, linting links, compatibility boundaries, and packaging smoke expectations.

## Public command surface

PatchHarbor exposes these public commands:

| Command | Purpose | Related docs |
| --- | --- | --- |
| `patchharbor --help` | show top-level help | `docs/cli-command-inventory.md` |
| `patchharbor --version` | show package version | `docs/packaging-acceptance.md` |
| `patchharbor doctor --repo` | check repository and environment assumptions | `docs/runner.md` |
| `patchharbor lint-script` | lint a patch script without executing it | `docs/patch-linting-acceptance.md` |
| `patchharbor run-script` | execute a patch script through PatchHarbor runner behavior | `docs/runner.md` |
| `patchharbor audit-public` | check for private/local values before public release | `docs/compatibility.md` |
| `patchharbor check-env` | check local development environment assumptions | `docs/compatibility.md` |

## Command examples

Show top-level help:

    patchharbor --help

Show the installed version:

    patchharbor --version

Check the current repository:

    patchharbor doctor --repo .

Lint a patch script:

    patchharbor lint-script ./example_patch.sh

Run a patch script:

    patchharbor run-script ./example_patch.sh

Audit for private/local values:

    patchharbor audit-public --repo .

Check the development environment:

    patchharbor check-env --repo .

## Exit-code contract

PatchHarbor CLI commands should use explicit exit codes.

| Code | Meaning |
| --- | --- |
| 0 | success |
| 1 | generic failure |
| 2 | command-line usage error |
| 10 | metadata or validation failure |
| 20 | patch lint or preflight failure |

Detailed exit-code notes remain in:

    docs/cli-exit-code-contract.md

PATCHHARBOR.15b3 does not delete that source document.

## Help-output contract

CLI help must remain stable enough for snapshot tests and user documentation.

Help expectations:

1. top-level help lists public subcommands
2. each subcommand has a short purpose
3. required arguments are visible in subcommand help
4. command names match tests and public docs
5. compatibility behavior is described without RepoDossier-only assumptions
6. help text avoids contributor-specific local paths

The help snapshot tests remain the guard for command naming and help text.

## Runner and lint links

Runner behavior is documented in:

    docs/runner.md

Patch linting behavior is documented in:

    docs/patch-linting-acceptance.md

CLI documentation should link to those documents instead of duplicating their complete runner and linting contracts.

## Compatibility links

Compatibility behavior is documented in:

    docs/compatibility.md

Compatibility docs cover source-wrapper boundaries, alias boundaries, workflow-rule behavior, and target-only versus source-only patch boundaries.

## Packaging links

Packaging behavior is documented in:

    docs/packaging-acceptance.md

Packaging acceptance covers pipx smoke behavior, importability, console entry points, and package metadata expectations.

## Related historical inputs

This consolidated document supersedes these documents for public CLI reading order:

| Path | Current role after PATCHHARBOR.15b3 |
| --- | --- |
| `docs/cli-command-inventory.md` | source input for command inventory |
| `docs/cli-exit-code-contract.md` | source input for exit-code contract |
| `docs/patch-linting-acceptance.md` | still-active lint behavior proof |
| `docs/packaging-acceptance.md` | still-active packaging proof |

The related documents are not deleted by PATCHHARBOR.15b3.

## CLI acceptance expectations

CLI documentation is accepted when:

1. `docs/cli.md` exists.
2. public commands are listed explicitly.
3. examples use `patchharbor` commands.
4. exit codes are summarized.
5. help-output stability is described.
6. runner docs and compatibility docs are linked.
7. related historical inputs are listed.
8. target tests cover the consolidated document.
9. target-only docs patches leave RepoDossier unchanged.
10. no contributor-specific local values are stored.

## Non-goals

PATCHHARBOR.15b3 does not:

- change CLI implementation
- change runner implementation
- change patch linting behavior
- change compatibility behavior
- edit RepoDossier
- edit source aliases
- delete migration documents
- mark migration documents historical
- change package metadata

Historical migration docs are marked historical by PATCHHARBOR.15b4.


## PATCHHARBOR.15b4 applied

- Historical CLI and migration inputs were marked historical by PATCHHARBOR.15b4; this document is the current CLI contract.


## PATCHHARBOR.15c1 applied

- Public API inventory now lives in `docs/public-api-inventory.md`; CLI docs remain the public command contract.


## PATCHHARBOR.15c2 applied

- Public API stability tests now live in `tests/test_public_api_stability.py` and protect public CLI commands listed in this document.
