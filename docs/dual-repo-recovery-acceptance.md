# PATCHHARBOR.16b3 – Dual repo recovery acceptance

This document records Milestone 16 recovery acceptance for the dual-repository PatchHarbor and RepoDossier migration.

The acceptance is target-only. It proves that after an expected PatchHarbor runner failure, a contributor can run a clean recovery smoke in a temporary repository while the RepoDossier source checkout remains unchanged.

## Purpose

PATCHHARBOR.16b1 accepted the normal dual-repo boundary.

PATCHHARBOR.16b2 accepted the failure boundary.

PATCHHARBOR.16b3 accepts the recovery boundary:

- a failed runner smoke may leave artifacts only in a temporary repository
- a later successful runner smoke may run in the same temporary repository
- source git status must remain unchanged across failure and recovery
- recovery docs must clearly keep source wrappers, aliases, shell rc files, and real exports out of scope

## Recovery contract

The accepted recovery contract is:

1. recovery tests must use temporary git repositories
2. recovery tests may intentionally run one failing patch script
3. recovery tests must then run one successful patch script
4. failing and successful markers must stay inside the temporary repository
5. recovery tests must not call RepoDossier `c`
6. recovery tests must not call RepoDossier `r`
7. recovery tests must not edit source wrappers
8. recovery tests must not write real RepoDossier exports
9. RepoDossier source status must be identical before and after recovery checks
10. public recovery docs and tests must not store contributor-specific local paths

## Evidence

The recovery boundary is tested by:

| Evidence | Role |
| --- | --- |
| `docs/dual-repo-recovery-acceptance.md` | recovery acceptance contract |
| `tests/test_dual_repo_recovery_acceptance.py` | recovery acceptance tests |

The tests create two temporary patch scripts:

| Script | Expected result |
| --- | --- |
| failing smoke patch | writes a failure marker in the temporary repository and exits non-zero |
| recovery smoke patch | writes a recovery marker in the temporary repository and exits zero |

The source repository status is captured before the failing run and after the recovery run. The values must be identical.

## Relationship to 16b1 and 16b2

PATCHHARBOR.16b3 depends on:

- PATCHHARBOR.16b1 boundary acceptance
- PATCHHARBOR.16b2 failure-boundary acceptance

PATCHHARBOR.16b3 does not replace those tests. It adds positive recovery confidence after a negative-path failure.

## Non-goals

PATCHHARBOR.16b3 does not:

- change PatchHarbor runtime code
- change RepoDossier runtime code
- change source wrappers
- change aliases
- edit shell rc files
- apply downloaded patches
- write real RepoDossier exports
- publish a release
- change version numbers

## Handoff to milestone acceptance

PATCHHARBOR.16c1 should add the final dual-repo milestone acceptance.

That later patch should aggregate 16a and 16b evidence into a Milestone 16 readiness statement.
