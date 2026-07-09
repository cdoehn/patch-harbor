# PatchHarbor.08e source-side adoption acceptance

PatchHarbor.08 accepts the non-mutating source-side adoption planning phase.

This phase prepares the first real source repository adoption step, but it does not modify RepoDossier, does not write wrapper files, does not install aliases, does not edit shell rc files, does not replace the current local runner, and does not touch export scripts.

## Accepted scope

PatchHarbor.08 is accepted when the target repository contains:

- source-side adoption inventory
- source-side runner wrapper draft
- source-side alias compatibility plan
- source-side runner compatibility tests plan
- source-side adoption acceptance documentation and tests

The migration context files used by the patch runner are maintained in the source repository under:

- `planning/roadmap_migration.md`
- `planning/milestones_migration.md`

## Current target components

| Component | Path |
| --- | --- |
| adoption inventory | `docs/source-side-adoption-inventory.md` |
| runner wrapper draft | `docs/source-side-runner-wrapper-draft.md` |
| alias compatibility plan | `docs/source-side-alias-compatibility-plan.md` |
| runner compatibility tests plan | `docs/source-side-runner-compatibility-tests.md` |
| adoption acceptance | `docs/source-side-adoption-acceptance.md` |
| adoption inventory tests | `tests/test_source_side_adoption_inventory.py` |
| runner wrapper draft tests | `tests/test_source_side_runner_wrapper_draft.py` |
| alias compatibility plan tests | `tests/test_source_side_alias_compatibility_plan.py` |
| runner compatibility test plan tests | `tests/test_source_side_runner_compatibility_tests.py` |
| adoption acceptance tests | `tests/test_source_side_adoption_acceptance.py` |

## Accepted behavior

PatchHarbor.08 establishes the plan for a later additive RepoDossier wrapper.

The planned wrapper target is:

    scripts/dev/run_patchharbor_patch.sh

The planned wrapper behavior is intentionally thin:

    exec patchharbor run-script "$@"

The planned alias work is separated from wrapper creation. Existing convenience aliases should not be silently changed in the first source-side adoption patch.

The planned source-side tests must prove that the old local runner is preserved, the new wrapper is additive, the wrapper delegates to `patchharbor run-script`, arguments are forwarded, export scripts stay untouched, aliases are not installed by wrapper creation, and private values are not introduced.

## Explicit non-goals

PatchHarbor.08 does not introduce:

- RepoDossier file changes
- source repository commits
- wrapper file writes
- alias installation
- shell rc-file changes
- download-folder mutation
- export runner migration
- replacement of the current local runner
- deletion of old source scripts
- automatic adoption of compatibility commands

## Readiness for PATCHHARBOR.09

PATCHHARBOR.09 may begin only after this acceptance is green.

PATCHHARBOR.09 should start with a source-side adoption preflight inventory before adding any wrapper.

The first real source-side wrapper patch should be additive and should not change the old convenience runner or export workflow.

## Required guardrails for the next phase

Every PATCHHARBOR.09 source-side patch must state:

- which repository is modified
- which source files are touched
- how rollback works
- which focused tests cover the change
- whether aliases are changed
- whether old runners are preserved
- whether export scripts are untouched
- how private and source-specific values are guarded

## Acceptance checks

This phase is accepted when the target repository passes:

    python3 -m compileall src tests
    PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_*.py'
    PYTHONPATH=src python3 -m patchharbor doctor --repo .

Manual review should confirm that PATCHHARBOR.08 created planning and acceptance artifacts only. No RepoDossier file should have been changed by this phase.
