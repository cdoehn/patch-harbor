# PatchHarbor compatibility documentation

This document is the consolidated public compatibility contract created by PATCHHARBOR.15b2.

It brings together source wrapper compatibility, source-side adoption constraints, workflow-rule compatibility, alias planning boundaries, and target-only cleanup rules.

## Compatibility purpose

PatchHarbor was extracted from RepoDossier development scripts. Compatibility documentation exists to make that transition safe without freezing historical migration artifacts forever.

Compatibility means:

- existing source wrappers can keep delegating to PatchHarbor commands
- source aliases can keep their user-facing names until a later explicit milestone changes them
- target CLI behavior remains stable for source wrappers and direct PatchHarbor users
- target-only patches do not edit RepoDossier source files
- source-only patches do not edit PatchHarbor target files
- migration history remains available without being mistaken for current command instructions

## Current compatibility surfaces

| Surface | Current contract | Status |
| --- | --- | --- |
| source wrapper compatibility | source wrappers can call PatchHarbor commands without changing user-facing source workflows | active compatibility contract |
| source-side adoption compatibility | target behavior supports staged adoption from RepoDossier | active compatibility contract |
| workflow-rule compatibility | workflow-rule schemas and validation stay deterministic | active compatibility contract |
| alias compatibility | source alias installers are not rewritten by target-only patches | active compatibility contract |
| runner compatibility | generic runner behavior stays stable for wrappers and direct CLI users | covered by `docs/runner.md` |
| CLI compatibility | command names, help, and exit codes remain stable | consolidated by PATCHHARBOR.15b3 |

## Source wrapper compatibility

PatchHarbor target code must support source wrappers without assuming that source-specific behavior belongs in the target package.

Current source-wrapper contract:

1. PatchHarbor owns generic patch infrastructure.
2. RepoDossier owns product-specific Download and export workflows.
3. Source wrappers may delegate to `patchharbor run-script`, `patchharbor lint-script`, `patchharbor audit-public`, or `patchharbor check-env`.
4. Target-only patches must leave source wrappers unchanged.
5. Source-only patches must leave target package code unchanged.
6. Compatibility tests must describe the expected bridge behavior before any deprecation.

Relevant documents:

| Path | Role after PATCHHARBOR.15b2 |
| --- | --- |
| `docs/source-wrapper-compatibility-acceptance.md` | acceptance input for source-wrapper compatibility |
| `docs/source-wrapper-compatibility-migration.md` | historical migration input |
| `docs/source-side-adoption-acceptance.md` | acceptance input for source-side adoption |
| `docs/source-side-adoption-inventory.md` | historical adoption planning input |
| `docs/source-side-adoption-preflight-inventory.md` | historical preflight planning input |

## Alias compatibility

PatchHarbor target patches must not edit shell rc files or source alias installers.

Current alias boundary:

- `rdrepo` is a RepoDossier source alias.
- `c` is a RepoDossier source alias for the Download patch workflow.
- `r` is a RepoDossier source alias for RepoDossier exports.
- `patchharbor-patch` is a source-side bridge alias.
- PatchHarbor target docs may describe target commands, but they must not instruct users to rewrite source aliases unless a later milestone explicitly changes the source workflow.

Relevant historical input:

    docs/source-side-alias-compatibility-plan.md

## Workflow-rule compatibility

PatchHarbor keeps workflow-rule behavior deterministic and schema-driven.

Compatibility expectations:

1. workflow-rule JSON remains validated by target code
2. rule IDs remain stable unless a migration explicitly changes them
3. validation errors stay explicit
4. migration and acceptance docs distinguish current behavior from extraction history
5. public docs do not require RepoDossier-only paths for generic PatchHarbor behavior

Relevant document:

    docs/workflow-rules-acceptance.md

## Runner and CLI boundary

Runner behavior is now consolidated in:

    docs/runner.md

CLI behavior is consolidated later by PATCHHARBOR.15b3.

Compatibility docs should link to runner and CLI docs instead of duplicating their full contracts.

## Compatibility acceptance gates

Compatibility documentation is accepted when:

1. `docs/compatibility.md` exists.
2. source-wrapper compatibility is described as active compatibility behavior.
3. source-side adoption compatibility is described as active compatibility behavior.
4. alias compatibility says target-only patches must not edit source alias installers.
5. workflow-rule compatibility is listed as deterministic and schema-driven.
6. runner compatibility links to `docs/runner.md`.
7. CLI compatibility is deferred to PATCHHARBOR.15b3.
8. related historical migration documents are listed without being deleted.
9. public and migration inventories point to this consolidated document.
10. source repository state remains unchanged for target-only docs patches.

## Non-goals

PATCHHARBOR.15b2 does not:

- change target CLI code
- change runner code
- change compatibility config code
- edit RepoDossier
- edit source wrappers
- edit source aliases
- delete migration documents
- mark migration documents historical
- consolidate CLI docs
- change package metadata

CLI docs are consolidated by PATCHHARBOR.15b3.

Historical migration docs are marked historical by PATCHHARBOR.15b4.


## PATCHHARBOR.15b3 applied

- CLI command documentation now lives in `docs/cli.md`.
- Compatibility docs keep boundary rules and link to CLI docs for public command names and exit-code summary.


## PATCHHARBOR.15b4 applied

- Historical compatibility and source-adoption inputs were marked historical by PATCHHARBOR.15b4; this document is the current compatibility contract.


## PATCHHARBOR.15c1 applied

- Public API inventory now lives in `docs/public-api-inventory.md`; compatibility docs remain the public compatibility behavior contract.


## PATCHHARBOR.15c2 applied

- Public API stability tests now live in `tests/test_public_api_stability.py` and protect public compatibility API surfaces listed in `docs/public-api-inventory.md`.
