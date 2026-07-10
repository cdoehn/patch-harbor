# PATCHHARBOR.16a3 – Dual repo source wrapper smoke

This document records the Milestone 16 dual-repository source-wrapper smoke.

The smoke is target-only. It reads and syntax-checks RepoDossier source wrappers, but it does not execute the RepoDossier `c` runner, does not execute the RepoDossier `r` runner, and does not edit source files.

## Purpose

PATCHHARBOR.16a1 proved dual-repo discovery.

PATCHHARBOR.16a2 proved PatchHarbor runner execution in a temporary test repository.

PATCHHARBOR.16a3 proves that the source-side wrapper files still exist, remain syntactically valid, and still point at the intended RepoDossier and PatchHarbor boundary.

## Source wrapper contract

The smoke checks these RepoDossier source paths:

| Source path | Current role |
| --- | --- |
| `scripts/dev/run_latest_download_patch.sh` | source-side Download patch workflow used by `c` |
| `scripts/dev/run_patchharbor_patch.sh` | source-side bridge wrapper for PatchHarbor patch execution |
| `scripts/dev/r.sh` | source-side RepoDossier export workflow used by `r` |
| `scripts/dev/install_aliases.sh` | source-side developer alias installer |

The smoke confirms that removed migration-only helpers are not active source files:

| Removed path |
| --- |
| `scripts/dev/validate_patch_metadata.py` |
| `scripts/dev/lint_patch_script.py` |
| `scripts/dev/run_latest_download_patch_patchharbor_candidate.sh` |

## What the smoke does

The smoke:

1. discovers the RepoDossier source checkout
2. discovers the PatchHarbor target checkout
3. runs `bash -n` on source shell wrappers
4. verifies the `c` runner still uses PatchHarbor `lint-script`
5. verifies the `c` runner keeps internal metadata validation
6. verifies the PatchHarbor source wrapper still mentions PatchHarbor
7. verifies `r` still calls RepoDossier export behavior
8. verifies the alias installer still documents `c`, `r`, and `patchharbor-patch`
9. verifies removed helper files do not exist
10. proves source git status is unchanged after read-only checks

## What the smoke does not do

The smoke must not:

- run `c`
- run `r`
- apply a downloaded patch
- rewrite alias installers
- edit shell rc files
- edit RepoDossier source files
- edit PatchHarbor runtime code
- use network access
- store contributor-specific local paths

## Handoff to next smoke

PATCHHARBOR.16a4 should add the dual-repo export smoke.

That later smoke can exercise RepoDossier export behavior in a controlled way, but PATCHHARBOR.16a3 only checks wrapper presence, syntax, boundary markers, and source immutability.
