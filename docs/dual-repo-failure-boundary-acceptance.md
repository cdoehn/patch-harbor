# PATCHHARBOR.16b2 – Dual repo failure boundary acceptance

This document records Milestone 16 failure-boundary acceptance for the dual-repository PatchHarbor and RepoDossier migration.

The acceptance is target-only. It proves that expected failure cases are contained in temporary runner repositories and do not mutate the RepoDossier source checkout.

## Purpose

PATCHHARBOR.16b1 accepted the normal dual-repo boundary.

PATCHHARBOR.16b2 accepts the failure boundary:

- a failing PatchHarbor runner smoke may fail
- a preflight-only runner smoke may skip execution
- failure artifacts must remain in temporary test repositories
- RepoDossier source files must remain unchanged
- PatchHarbor runtime code must remain unchanged by this acceptance patch

## Failure-boundary contract

The accepted failure-boundary contract is:

1. intentional runner failures must use temporary git repositories
2. intentional runner failures must not call RepoDossier `c`
3. intentional runner failures must not call RepoDossier `r`
4. intentional runner failures must not edit source wrappers
5. intentional runner failures must not edit shell rc files
6. intentional runner failures must not write real RepoDossier exports
7. `run-script --no-execute` may preflight a failing script without executing its failure body
8. source git status must be identical before and after the failure checks
9. public failure-boundary docs and tests must not store contributor-specific local paths

## Evidence

The failure boundary is tested by:

| Evidence | Role |
| --- | --- |
| `docs/dual-repo-failure-boundary-acceptance.md` | failure-boundary acceptance contract |
| `tests/test_dual_repo_failure_boundary_acceptance.py` | failure-boundary acceptance tests |

The tests create temporary patch scripts with `patchharbor-meta` records and run them through PatchHarbor.

The executed failure script writes only to a temporary marker path and exits non-zero.

The preflight-only failure script uses the same failing body, but `run-script --no-execute` must not create the marker file.

## Relationship to 16a and 16b1

PATCHHARBOR.16b2 depends on:

- PATCHHARBOR.16a1 discovery smoke
- PATCHHARBOR.16a2 patch-runner smoke
- PATCHHARBOR.16a3 source-wrapper smoke
- PATCHHARBOR.16a4 export smoke
- PATCHHARBOR.16b1 boundary acceptance

PATCHHARBOR.16b2 does not replace those tests. It adds negative-path confidence on top of them.

## Non-goals

PATCHHARBOR.16b2 does not:

- change PatchHarbor runtime code
- change RepoDossier runtime code
- change source wrappers
- change aliases
- edit shell rc files
- apply downloaded patches
- write real RepoDossier exports
- publish a release
- change version numbers

## Handoff to next acceptance

PATCHHARBOR.16b3 should add recovery acceptance.

That later patch should document and test how a contributor recognizes the safe recovery path after a failed dual-repo smoke.


## PATCHHARBOR.16b3 applied

- Dual repo recovery acceptance now lives in `docs/dual-repo-recovery-acceptance.md` and `tests/test_dual_repo_recovery_acceptance.py`.
