<!-- PATCHHARBOR.15b4 historical-migration-doc -->

> Historical migration document.
>
> This file records PatchHarbor extraction and adoption history. It is retained for traceability, but it is not the current public command contract.
> Current public runner docs live in `docs/runner.md`; compatibility docs live in `docs/compatibility.md`; CLI docs live in `docs/cli.md`.

# PatchHarbor.03 extraction baseline

PatchHarbor.03 is the first small extraction phase after the standalone target skeleton.

It intentionally extracts only foundation pieces:

- a generic console and footer helper module
- focused tests for that console helper
- a generic patch metadata parser and basic validator
- tests that cover the new generic marker and the legacy transition marker
- a target-side inventory of future Dev-Script migration candidates

## Accepted scope

This phase is accepted when the target repository can:

- import and test `patchharbor.console`
- render deterministic plain-text footers without requiring terminal colors
- parse `patchharbor-meta` metadata records
- continue accepting the legacy metadata marker during migration
- validate the basic patch metadata shape used by current patch scripts
- run the full target test suite through unittest
- pass `patchharbor doctor --repo` for the target repository

## Explicit non-goals

PatchHarbor.03 is not a complete runner migration.

It does not migrate the download patch runner, export runner, alias installer, public repository audit, or project-specific wrappers.

It also does not claim feature parity with the source repository's existing metadata validator. The metadata module is a foundation for incremental migration, not the final policy engine.

## Boundary

RepoDossier remains unchanged in this phase.

PatchHarbor should keep reusable logic generic and covered by tests before any source repository wrappers are changed.
