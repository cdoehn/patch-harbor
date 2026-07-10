# PATCHHARBOR.16b1 – Migration rollback notes

This document records the plan-correct Milestone 16 migration rollback notes.

It is added by PATCHHARBOR.16b1-fix1 because the operative plan in `planning/milestones_migration.md` defines PATCHHARBOR.16b1 as `Migration Rollback Notes` with commit `Add migration rollback notes`.

The notes are target-only. They document safe recovery and rollback procedures for the PatchHarbor and RepoDossier migration without modifying RepoDossier source files.

## Plan contract

| Field | Value |
| --- | --- |
| Patch id | PATCHHARBOR.16b1 |
| Plan title | Migration Rollback Notes |
| Commit | Add migration rollback notes |
| Repair id | PATCHHARBOR.16b1-fix1 |

## When to use these notes

Use these notes when a migration patch, smoke, acceptance test, or downloaded patch runner stops before a clean commit.

The first rule is: do not start the next migration step until the failed step is understood.

## Safe rollback decision tree

### Case 1: Patch failed before any commit

If a patch failed before creating a commit:

1. inspect the runner log
2. inspect target changes with `git status --short`
3. confirm whether only the current patch scope changed
4. either run a fix patch or restore the current patch files
5. do not manually edit RepoDossier source files from a target-only fix

A target-only rollback may restore only the target files changed by the failed patch.

### Case 2: Patch failed after writing target files but before commit

If docs or tests were written but the commit did not happen:

1. keep the failed log
2. do not commit partial files manually
3. prefer a fix patch that overwrites the failed files into a known-good state
4. keep the original commit message from the operative plan
5. verify source status before and after the fix

### Case 3: Patch committed but later test evidence was wrong

If a patch committed successfully but the milestone slot was wrong:

1. do not rewrite history unless explicitly requested
2. add a plan-repair patch with a fix id
3. keep the green evidence if it is useful and harmless
4. add the missing plan-correct docs and tests
5. document why the repair exists

PATCHHARBOR.16a4-fix2 is the model for this case.

### Case 4: Source repository changed during a target-only patch

If RepoDossier source files changed during a target-only patch:

1. stop immediately
2. do not continue to the next milestone
3. inspect `git status --short` in the source repository
4. restore only unintended source changes
5. add a fix patch that proves source status is unchanged

Source-side editor swap files may be ignored by scope checks, but real source changes must not be ignored.

### Case 5: Runner execution failure in a temporary repo

If a PatchHarbor runner smoke fails inside a temporary test repository:

1. confirm that the failure marker is inside the temporary repository
2. confirm RepoDossier source status is unchanged
3. confirm PatchHarbor runtime code was not changed by the acceptance patch
4. run the failure-boundary or recovery acceptance test again after fixing the test or docs
5. do not run the source `c` or `r` workflows as a workaround

## Source/target rollback boundary

Rollback actions must respect the repository boundary:

| Area | Allowed action |
| --- | --- |
| PatchHarbor target docs/tests | fix by target-only patch |
| PatchHarbor runtime code | fix only when the plan scope allows runtime changes |
| RepoDossier source wrappers | read or syntax-check only unless the plan explicitly says source-side patch |
| RepoDossier alias files | do not rewrite in target-only rollback |
| shell rc files | do not edit from migration patches |
| temporary test repositories | safe to delete after smoke runs |

## Commands to inspect state

Useful read-only checks:

- `git status --short`
- `git log -1 --oneline`
- `git diff --stat`
- `git diff --name-only`
- `python -m unittest tests.test_dual_repo_private_value_audit`

These commands must be run in the correct repository. Target-only checks run in PatchHarbor. Source status checks run in RepoDossier.

## What not to do

Do not:

- start the next milestone after a red patch
- silently skip a failed test
- rewrite the operative plan from PatchHarbor
- remove green evidence just because the patch id was repaired later
- edit RepoDossier from a PatchHarbor target-only fix
- run downloaded patches to recover from a docs/test failure
- change commit messages away from the operative plan

## Handoff

After these rollback notes are green, the next plan-repair patch is PATCHHARBOR.16b2-fix1 – Migration Completion Checklist.


## PATCHHARBOR.16b2-fix1 applied

- Plan repair: PATCHHARBOR.16b2-fix1 adds the plan-correct Migration Completion Checklist in `docs/migration-completion-checklist.md` and `tests/test_migration_completion_checklist.py`.


## PATCHHARBOR.16b3-fix1 applied

- Plan repair: PATCHHARBOR.16b3-fix1 adds `docs/final-migration-acceptance.md` and `tests/test_final_migration_acceptance.py`; rollback notes remain supporting evidence.
