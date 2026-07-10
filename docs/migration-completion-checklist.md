# PATCHHARBOR.16b2 – Migration completion checklist

This document records the plan-correct Milestone 16 migration completion checklist.

It is added by PATCHHARBOR.16b2-fix1 because the operative plan in `planning/milestones_migration.md` defines PATCHHARBOR.16b2 as `Migration Completion Checklist` with commit `Add migration completion checklist`.

The checklist is target-only. It verifies that the migration repair chain has the documents, tests, source/target boundary checks, and rollback notes needed before final migration acceptance.

## Plan contract

| Field | Value |
| --- | --- |
| Patch id | PATCHHARBOR.16b2 |
| Plan title | Migration Completion Checklist |
| Commit | Add migration completion checklist |
| Repair id | PATCHHARBOR.16b2-fix1 |

## Required completion evidence

Milestone 16 completion requires these plan-correct repair artifacts:

| Patch | Required evidence |
| --- | --- |
| PATCHHARBOR.16a4-fix2 | `docs/dual-repo-private-value-audit.md` and `tests/test_dual_repo_private_value_audit.py` |
| PATCHHARBOR.16b1-fix1 | `docs/migration-rollback-notes.md` and `tests/test_migration_rollback_notes.py` |
| PATCHHARBOR.16b2-fix1 | `docs/migration-completion-checklist.md` and `tests/test_migration_completion_checklist.py` |

Previously green dual-repo smoke and boundary evidence is retained as supporting evidence:

| Evidence | Role |
| --- | --- |
| `docs/dual-repo-discovery-smoke.md` | discovery smoke |
| `docs/dual-repo-patch-runner-smoke.md` | patch-runner smoke |
| `docs/dual-repo-source-wrapper-smoke.md` | source-wrapper smoke |
| `docs/dual-repo-export-smoke.md` | retained export smoke |
| `docs/dual-repo-boundary-acceptance.md` | retained boundary acceptance |
| `docs/dual-repo-failure-boundary-acceptance.md` | retained failure-boundary acceptance |
| `docs/dual-repo-recovery-acceptance.md` | retained recovery acceptance |

## Checklist

Before final migration acceptance, all of these must be true:

1. the operative source plan is `planning/milestones_migration.md`
2. PATCHHARBOR.16a4 is represented by Dual Repo Private Value Audit
3. PATCHHARBOR.16b1 is represented by Migration Rollback Notes
4. PATCHHARBOR.16b2 is represented by Migration Completion Checklist
5. the next patch is PATCHHARBOR.16b3-fix1 – Final Migration Acceptance
6. no `PATCHHARBOR.16c1` patch is required by the operative plan
7. source status remains unchanged by target-only completion checks
8. rollback notes explain what to do after a red patch
9. private/local values are absent from Milestone 16 public docs and tests
10. literal Markdown fences are absent from Milestone 16 public docs and tests
11. PatchHarbor runtime code is not changed by the completion checklist
12. RepoDossier source wrappers are not changed by the completion checklist

## Explicit non-completion conditions

Milestone 16 is not complete if any of these are true:

- `planning/milestones_migration.md` is ignored
- PATCHHARBOR.16c1 is treated as a real plan slot
- target-only fixes edit RepoDossier source files
- failed patch logs are ignored
- private/local values are committed into public docs
- rollback notes are missing
- completion checklist is missing
- final migration acceptance is missing

## Source/target boundary

The checklist may read source files to verify the plan, but it must not edit them.

Allowed read-only source checks:

| Source path | Allowed interaction |
| --- | --- |
| `planning/milestones_migration.md` | verify plan slots and commit contracts |
| `scripts/dev/run_latest_download_patch.sh` | read or syntax-check only |
| `scripts/dev/run_patchharbor_patch.sh` | read or syntax-check only |
| `scripts/dev/r.sh` | read or syntax-check only |
| `scripts/dev/run_repodossier_exports.sh` | read or syntax-check only |

## Handoff

After this checklist is green, the next plan-repair patch is PATCHHARBOR.16b3-fix1 – Final Migration Acceptance.


## PATCHHARBOR.16b3-fix1 applied

- Plan repair: PATCHHARBOR.16b3-fix1 adds the plan-correct Final Migration Acceptance in `docs/final-migration-acceptance.md` and `tests/test_final_migration_acceptance.py`; next operative plan step is PATCHHARBOR.17a1.
