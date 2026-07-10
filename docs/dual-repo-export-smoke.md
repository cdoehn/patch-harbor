# PATCHHARBOR.16a4 – Dual repo export smoke

This document records the Milestone 16 dual-repository RepoDossier export smoke.

The smoke is target-only. It exercises safe RepoDossier export-wrapper entry points with list and dry-run style checks, and it proves the RepoDossier source checkout remains unchanged.

## Purpose

PATCHHARBOR.16a1 proved dual-repo discovery.

PATCHHARBOR.16a2 proved PatchHarbor runner execution in a temporary test repository.

PATCHHARBOR.16a3 proved source wrapper syntax and boundary markers.

PATCHHARBOR.16a4 proves the RepoDossier export wrapper is still discoverable, safe to inspect, and capable of dry-run/list-mode behavior from a dual-repo PatchHarbor test.

## Export wrapper contract

The smoke checks these RepoDossier source paths:

| Source path | Current role |
| --- | --- |
| `scripts/dev/r.sh` | source-side export alias wrapper |
| `scripts/dev/run_repodossier_exports.sh` | source-side RepoDossier export runner |

The smoke checks the public export behavior described by RepoDossier docs:

- `r --list-modes`
- `r --dry-run`
- `full`
- `ai`
- `docs`
- `changed`

## What the smoke does

The smoke:

1. discovers the RepoDossier source checkout
2. discovers the PatchHarbor target checkout
3. validates Bash syntax for the export wrappers
4. runs safe list-mode behavior when available
5. runs dry-run export behavior when available
6. checks source status before and after the smoke
7. verifies the smoke is linked from the 16a docs chain
8. stores no contributor-specific local paths

## What the smoke does not do

The smoke must not:

- write real export files
- apply patches
- run the Download patch runner `c`
- edit RepoDossier source files
- edit shell aliases
- edit shell rc files
- edit PatchHarbor runtime code
- require network access

## Handoff to next acceptance

PATCHHARBOR.16b1 should add the dual-repo boundary acceptance.

That later acceptance can aggregate 16a1 through 16a4 and enforce the source-only/target-only boundary as a milestone-level contract.


## PATCHHARBOR.16b1 applied

- Dual repo boundary acceptance now lives in `docs/dual-repo-boundary-acceptance.md` and `tests/test_dual_repo_boundary_acceptance.py`; it accepts the 16a smoke series as the current source/target boundary contract.
