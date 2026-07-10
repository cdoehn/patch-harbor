# PATCHHARBOR.16b1 – Dual repo boundary acceptance

This document records the Milestone 16 dual-repository boundary acceptance.

The acceptance is target-only. It aggregates the completed 16a smoke series and verifies that PatchHarbor target work and RepoDossier source work remain separated.

## Purpose

Milestone 16a added four dual-repository smokes:

| Patch | Evidence |
| --- | --- |
| PATCHHARBOR.16a1 | `docs/dual-repo-discovery-smoke.md` and `tests/test_dual_repo_discovery_smoke.py` |
| PATCHHARBOR.16a2 | `docs/dual-repo-patch-runner-smoke.md` and `tests/test_dual_repo_patch_runner_smoke.py` |
| PATCHHARBOR.16a3 | `docs/dual-repo-source-wrapper-smoke.md` and `tests/test_dual_repo_source_wrapper_smoke.py` |
| PATCHHARBOR.16a4 | `docs/dual-repo-export-smoke.md` and `tests/test_dual_repo_export_smoke.py` |

PATCHHARBOR.16b1 accepts the boundary contract created by those smokes.

## Boundary contract

The accepted dual-repo boundary is:

1. PatchHarbor target patches may edit PatchHarbor docs, tests, and runtime only when the patch scope explicitly allows it.
2. PatchHarbor target-only acceptance patches must not edit RepoDossier source files.
3. RepoDossier source wrapper checks may read and syntax-check source wrapper files.
4. RepoDossier source wrapper checks must not execute `c` or `r` as mutation workflows.
5. PatchHarbor runner smokes may execute only against temporary test repositories unless a later milestone explicitly expands scope.
6. RepoDossier export smokes may use safe list/dry-run behavior and must verify source status before and after.
7. Public-readiness docs must link the completed 16a smoke series.
8. No public acceptance doc or test may store contributor-specific local paths.

## Accepted source-side files

The source-side files that Milestone 16 may inspect are:

| Source path | Allowed interaction |
| --- | --- |
| `planning/milestones_migration.md` | read milestone contract |
| `scripts/dev/run_latest_download_patch.sh` | read and syntax-check |
| `scripts/dev/run_patchharbor_patch.sh` | read and syntax-check |
| `scripts/dev/r.sh` | read and syntax-check |
| `scripts/dev/run_repodossier_exports.sh` | read, syntax-check, list/dry-run only |
| `scripts/dev/install_aliases.sh` | read and syntax-check |
| `docs/installation.md` | read documentation context |

These reads must leave the RepoDossier git status unchanged.

## Accepted target-side evidence

The target-side acceptance evidence is:

| Target path | Role |
| --- | --- |
| `docs/dual-repo-discovery-smoke.md` | discovery smoke contract |
| `docs/dual-repo-patch-runner-smoke.md` | runner smoke contract |
| `docs/dual-repo-source-wrapper-smoke.md` | source-wrapper smoke contract |
| `docs/dual-repo-export-smoke.md` | export smoke contract |
| `docs/dual-repo-boundary-acceptance.md` | aggregated boundary acceptance |
| `tests/test_dual_repo_discovery_smoke.py` | discovery smoke test |
| `tests/test_dual_repo_patch_runner_smoke.py` | runner smoke test |
| `tests/test_dual_repo_source_wrapper_smoke.py` | source-wrapper smoke test |
| `tests/test_dual_repo_export_smoke.py` | export smoke test |
| `tests/test_dual_repo_boundary_acceptance.py` | aggregated boundary acceptance test |

## Non-goals

PATCHHARBOR.16b1 does not:

- change PatchHarbor runtime code
- change RepoDossier runtime code
- change source wrappers
- change aliases
- edit shell rc files
- run downloaded patches
- write real RepoDossier exports
- publish a release
- change version numbers

## Handoff to next acceptance

PATCHHARBOR.16b2 should add failure-boundary acceptance for the same dual-repo system.

That later patch should prove that failed or partial smokes do not blur the source/target boundary and that recovery instructions remain clear.


## PATCHHARBOR.16b2 applied

- Dual repo failure-boundary acceptance now lives in `docs/dual-repo-failure-boundary-acceptance.md` and `tests/test_dual_repo_failure_boundary_acceptance.py`.


## PATCHHARBOR.16b3 applied

- Dual repo recovery acceptance now lives in `docs/dual-repo-recovery-acceptance.md` and `tests/test_dual_repo_recovery_acceptance.py`; it proves a clean recovery run after a contained runner failure.


## PATCHHARBOR.16a4-fix2 applied

- Plan repair: PATCHHARBOR.16a4-fix2 adds `docs/dual-repo-private-value-audit.md` and `tests/test_dual_repo_private_value_audit.py` so Milestone 16 again matches the operative `planning/milestones_migration.md` 16a4 slot.


## PATCHHARBOR.16b1-fix1 applied

- Plan repair: PATCHHARBOR.16b1-fix1 adds `docs/migration-rollback-notes.md` and `tests/test_migration_rollback_notes.py` so Milestone 16b again follows the operative plan.
