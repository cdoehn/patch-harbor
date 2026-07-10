# PATCHHARBOR.16a4 – Dual repo private value audit

This document records the plan-correct Milestone 16 dual-repository private value audit.

It is added by PATCHHARBOR.16a4-fix2 because the operative plan in `planning/milestones_migration.md` defines PATCHHARBOR.16a4 as `Dual Repo Private Value Audit` with commit `Add dual repository private value audit`.

The audit is target-only. It reads RepoDossier and PatchHarbor files, scans public Milestone 16 documents and tests for private/local values, and leaves the RepoDossier source checkout unchanged.

## Purpose

PATCHHARBOR.16a4-fix2 repairs the Milestone 16 acceptance chain without deleting already green dual-repo smoke evidence.

The accepted plan-correct 16a4 contract is:

| Field | Value |
| --- | --- |
| Patch id | PATCHHARBOR.16a4 |
| Plan title | Dual Repo Private Value Audit |
| Commit | Add dual repository private value audit |
| Repair id | PATCHHARBOR.16a4-fix2 |

## Audit scope

The audit covers the public Milestone 16 target documents and tests:

| Target path | Role |
| --- | --- |
| `docs/dual-repo-discovery-smoke.md` | discovery smoke |
| `docs/dual-repo-patch-runner-smoke.md` | patch-runner smoke |
| `docs/dual-repo-source-wrapper-smoke.md` | source-wrapper smoke |
| `docs/dual-repo-export-smoke.md` | retained export-smoke evidence |
| `docs/dual-repo-private-value-audit.md` | plan-correct private-value audit |
| `docs/dual-repo-boundary-acceptance.md` | boundary acceptance |
| `docs/dual-repo-failure-boundary-acceptance.md` | failure-boundary acceptance |
| `docs/dual-repo-recovery-acceptance.md` | recovery acceptance |
| `docs/public-readiness-acceptance.md` | public-readiness chain |
| `tests/test_dual_repo_private_value_audit.py` | private-value audit test |

The audit also reads the RepoDossier plan to verify that the source plan still defines PATCHHARBOR.16a4 as Dual Repo Private Value Audit.

## Private/local value classes

The audit checks that public Milestone 16 docs and tests do not store:

- local home paths
- local user email addresses
- workstation names
- project-root shortcuts tied to one contributor
- literal Markdown fences in generated public documents

The tests construct concrete private/local patterns at runtime so the test source itself does not store the forbidden combined values.

## Boundary contract

The audit must not:

- edit RepoDossier source files
- edit PatchHarbor runtime code
- run downloaded patches
- run RepoDossier `c`
- run RepoDossier `r`
- rewrite source wrappers
- rewrite aliases
- edit shell rc files
- write real RepoDossier exports

## Relationship to retained export smoke

A previous green artifact used PATCHHARBOR.16a4 wording for the dual-repo export smoke. The operative plan now remains authoritative:

- PATCHHARBOR.16a3 is the plan slot for Dual Repo Export Smoke.
- PATCHHARBOR.16a4 is the plan slot for Dual Repo Private Value Audit.

The existing export-smoke documents and tests are retained as useful Milestone 16 evidence. PATCHHARBOR.16a4-fix2 adds the missing plan-correct private-value audit instead of deleting green smoke coverage.

## Handoff

After this patch is green, the next plan-repair patch is PATCHHARBOR.16b1-fix1 – Migration Rollback Notes.


## PATCHHARBOR.16b1-fix1 applied

- Plan repair: PATCHHARBOR.16b1-fix1 adds the plan-correct Migration Rollback Notes in `docs/migration-rollback-notes.md` and `tests/test_migration_rollback_notes.py`.
