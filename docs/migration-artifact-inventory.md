# PATCHHARBOR.15a1 – Migration artifact inventory

This inventory identifies PatchHarbor documents and tests that were created to support the RepoDossier-to-PatchHarbor migration.

The inventory is target-only. It does not edit RepoDossier, does not change source wrappers, and does not remove any migration files.

## Purpose

PatchHarbor is moving from migration construction to public-readiness cleanup.

Before consolidating or marking migration documents historical, the target repository needs an explicit inventory of:

- active public-facing documents
- active compatibility contracts
- historical migration planning records
- adoption bridge documents
- acceptance tests that still guard public behavior
- tests that only protect historical migration artifacts

## Classification rules

Use these classifications for cleanup decisions:

| Classification | Meaning | Cleanup rule |
| --- | --- | --- |
| active public contract | user- or contributor-facing behavior that remains current | keep and consolidate into public docs |
| active compatibility contract | behavior that preserves source adoption or CLI stability | keep until compatibility deprecation is explicitly planned |
| historical migration record | useful migration history that is not a public command contract | mark historical, then move or consolidate later |
| bridge artifact | document or test that helped transition between source and target behavior | keep only while it guards a still-needed adoption risk |
| acceptance guard | test or document that proves a current public behavior | keep and rename only with an equivalent replacement |
| removal candidate | item that can be deleted only after an explicit deletion-gate test proves no active dependency | do not delete in 15a1 |

## Document inventory

| Path | Classification | Notes |
| --- | --- | --- |
| `docs/migration.md` | historical migration record | overview of the extraction project; keep as history until public docs are consolidated |
| `docs/dev-script-inventory.md` | historical migration record | early RepoDossier helper inventory; superseded by extracted target APIs |
| `docs/download-runner-api-inventory.md` | active compatibility contract | documents runner API surfaces used by target tests |
| `docs/download-runner-lifecycle-plan-acceptance.md` | acceptance guard | lifecycle acceptance for download runner behavior |
| `docs/workflow-rules-migration.md` | historical migration record | migration notes for workflow rules extraction |
| `docs/workflow-rules-acceptance.md` | acceptance guard | current workflow-rule behavior proof |
| `docs/patch-linting-migration.md` | historical migration record | migration notes for patch linting extraction |
| `docs/patch-linting-acceptance.md` | active public contract | current lint-script behavior proof |
| `docs/runner-compatibility-migration.md` | historical migration record | migration notes for runner compatibility extraction |
| `docs/runner-compatibility-acceptance.md` | active compatibility contract | current runner compatibility proof |
| `docs/source-side-adoption-inventory.md` | historical migration record | inventory for source adoption planning |
| `docs/source-side-adoption-preflight-inventory.md` | bridge artifact | preflight adoption planning bridge |
| `docs/source-side-adoption-acceptance.md` | active compatibility contract | proves source-side adoption constraints |
| `docs/source-side-alias-compatibility-plan.md` | bridge artifact | alias plan; keep until source alias docs are fully public-ready |
| `docs/source-side-runner-compatibility-tests.md` | bridge artifact | runner compatibility planning notes |
| `docs/source-side-runner-wrapper-draft.md` | historical migration record | draft source wrapper; not a current command contract |
| `docs/source-wrapper-compatibility-migration.md` | historical migration record | migration notes for source wrapper compatibility |
| `docs/source-wrapper-compatibility-acceptance.md` | active compatibility contract | current source wrapper compatibility proof |
| `docs/cli-command-inventory.md` | active public contract | CLI inventory for public-readiness docs |
| `docs/cli-exit-code-contract.md` | active public contract | CLI exit-code contract |
| `docs/packaging-acceptance.md` | acceptance guard | packaging and pipx acceptance |
| `docs/bootstrap.md` | active public contract | bootstrap and project setup documentation |

## Test inventory

| Path | Classification | Notes |
| --- | --- | --- |
| `tests/test_dev_script_inventory.py` | historical migration guard | protects early inventory document only |
| `tests/test_workflow_rules_inventory.py` | historical migration guard | protects migration inventory of workflow rules |
| `tests/test_workflow_rules_acceptance.py` | acceptance guard | current workflow-rules acceptance |
| `tests/test_patch_linting_inventory.py` | historical migration guard | protects patch-linting inventory |
| `tests/test_patch_linting_acceptance.py` | acceptance guard | current patch-linting behavior |
| `tests/test_runner_compatibility_inventory.py` | historical migration guard | protects runner compatibility inventory |
| `tests/test_runner_compatibility_acceptance.py` | acceptance guard | current runner compatibility behavior |
| `tests/test_source_side_adoption_inventory.py` | historical migration guard | source-side adoption inventory |
| `tests/test_source_side_adoption_preflight_inventory.py` | bridge artifact guard | source adoption preflight bridge |
| `tests/test_source_side_adoption_acceptance.py` | acceptance guard | source-side adoption acceptance |
| `tests/test_source_side_alias_compatibility_plan.py` | bridge artifact guard | alias compatibility bridge |
| `tests/test_source_side_runner_compatibility_tests.py` | bridge artifact guard | source runner compatibility planning |
| `tests/test_source_side_runner_wrapper_draft.py` | historical migration guard | wrapper draft document |
| `tests/test_source_wrapper_compatibility_inventory.py` | historical migration guard | source wrapper inventory |
| `tests/test_source_wrapper_compatibility_acceptance.py` | acceptance guard | source wrapper compatibility behavior |
| `tests/test_cli_help_snapshots.py` | active public contract guard | public CLI help output |
| `tests/test_cli.py` | active public contract guard | CLI command behavior |
| `tests/test_packaging_acceptance.py` | acceptance guard | package and command acceptance |

## Current public-readiness boundary

Keep these areas active for public readiness:

- CLI command inventory and help snapshots
- exit-code contract
- patch linting acceptance
- runner compatibility acceptance
- source wrapper compatibility acceptance
- packaging acceptance
- public audit behavior
- environment check behavior

Treat these areas as historical unless a later patch proves they still define current behavior:

- early extraction inventories
- source-side adoption planning drafts
- migration narrative documents
- wrapper draft documents
- preflight planning documents

## Deletion gate

No migration artifact is deleted by PATCHHARBOR.15a1.

Before any later deletion, the cleanup patch must prove all of the following:

1. the artifact is listed in this inventory
2. the artifact is classified as a removal candidate or historical migration record
3. no active public contract links to the artifact as a current command contract
4. no active test imports or reads the artifact except a deletion-gate or historical-doc test
5. an equivalent current public document exists when the artifact described active behavior
6. focused target tests pass before commit
7. source repository state remains unchanged for target-only cleanup patches

## Next steps

PATCHHARBOR.15a2 inventories public docs.

PATCHHARBOR.15b consolidates runner, compatibility, and CLI docs.

PATCHHARBOR.15c records public API and public-readiness acceptance.
