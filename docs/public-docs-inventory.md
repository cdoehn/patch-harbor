# PATCHHARBOR.15a2 – Public docs inventory

This inventory identifies PatchHarbor documentation that should remain public-facing after the migration cleanup.

The inventory is target-only. It does not edit RepoDossier, source wrappers, aliases, shell rc files, or runtime behavior.

## Purpose

PATCHHARBOR.15a2 prepares the 15b documentation consolidation series.

It separates:

- public entry documentation
- public CLI and API contracts
- active compatibility documentation
- acceptance documentation
- historical migration documentation
- consolidation targets
- documents that should remain internal or historical

## Public documentation classes

| Class | Meaning | Action in 15b |
| --- | --- | --- |
| public entry point | first document a user or contributor should read | keep and reduce duplication |
| public CLI contract | command names, help behavior, and exit-code expectations | consolidate into CLI docs |
| public runner contract | documented patch runner behavior | consolidate into runner docs |
| public lint contract | documented patch linting behavior | keep as public CLI behavior |
| public compatibility contract | compatibility behavior still required by source adoption | keep until deprecation is planned |
| packaging contract | install, metadata, and smoke acceptance | keep as public install docs |
| historical migration document | migration narrative, inventory, draft, or bridge plan | mark historical or move out of public path later |
| public-readiness inventory | temporary inventory used by 15a/15c | keep until public-readiness acceptance is complete |

## Consolidation order anchor

This anchor records the first explicit 15b milestone references in intended order before per-document tables mention individual consolidation targets.

1. PATCHHARBOR.15b1 consolidates runner docs.
2. PATCHHARBOR.15b2 consolidates compatibility docs.
3. PATCHHARBOR.15b3 consolidates CLI docs.
4. PATCHHARBOR.15b4 marks migration docs historical.

## Public docs inventory

| Path | Class | Public-readiness action |
| --- | --- | --- |
| `README.md` | public entry point | keep; remove duplicated installation content in a later docs consolidation patch |
| `docs/bootstrap.md` | public entry point | keep or merge into README once migration history is summarized |
| `docs/cli-command-inventory.md` | public CLI contract | consolidate with exit-code and help docs in PATCHHARBOR.15b3 |
| `docs/cli-exit-code-contract.md` | public CLI contract | consolidate with CLI inventory in PATCHHARBOR.15b3 |
| `docs/patch-linting-acceptance.md` | public lint contract | keep current lint-script behavior; link from consolidated CLI docs |
| `docs/runner-compatibility-acceptance.md` | public runner contract | consolidate with runner docs in PATCHHARBOR.15b1 |
| `docs/source-wrapper-compatibility-acceptance.md` | public compatibility contract | consolidate with compatibility docs in PATCHHARBOR.15b2 |
| `docs/source-side-adoption-acceptance.md` | public compatibility contract | consolidate with compatibility docs in PATCHHARBOR.15b2 |
| `docs/workflow-rules-acceptance.md` | public compatibility contract | keep until workflow-rule API is stable or explicitly deprecated |
| `docs/packaging-acceptance.md` | packaging contract | keep as packaging acceptance; link from installation docs |
| `docs/download-runner-api-inventory.md` | public runner contract | consolidate with runner docs in PATCHHARBOR.15b1 |
| `docs/download-runner-lifecycle-plan-acceptance.md` | public runner contract | consolidate with runner docs in PATCHHARBOR.15b1 |
| `docs/cli-command-inventory.md` | public CLI contract | keep as source for command-surface consolidation |
| `docs/migration-artifact-inventory.md` | public-readiness inventory | keep through 15c; then mark as historical |
| `docs/public-docs-inventory.md` | public-readiness inventory | keep through 15c; then mark as historical |

## Historical docs inventory

| Path | Historical reason | Future action |
| --- | --- | --- |
| `docs/migration.md` | extraction narrative and migration boundary | mark historical in PATCHHARBOR.15b4 |
| `docs/dev-script-inventory.md` | early source helper inventory | mark historical in PATCHHARBOR.15b4 |
| `docs/workflow-rules-migration.md` | workflow rules extraction notes | mark historical in PATCHHARBOR.15b4 |
| `docs/patch-linting-migration.md` | lint extraction notes | mark historical in PATCHHARBOR.15b4 |
| `docs/runner-compatibility-migration.md` | runner extraction notes | mark historical in PATCHHARBOR.15b4 |
| `docs/source-wrapper-compatibility-migration.md` | source wrapper extraction notes | mark historical in PATCHHARBOR.15b4 |
| `docs/source-side-adoption-inventory.md` | adoption planning inventory | mark historical in PATCHHARBOR.15b4 |
| `docs/source-side-adoption-preflight-inventory.md` | adoption preflight planning | mark historical in PATCHHARBOR.15b4 |
| `docs/source-side-alias-compatibility-plan.md` | alias compatibility planning bridge | mark historical after compatibility docs are consolidated |
| `docs/source-side-runner-compatibility-tests.md` | test-planning bridge | mark historical after runner docs are consolidated |
| `docs/source-side-runner-wrapper-draft.md` | draft wrapper document | mark historical in PATCHHARBOR.15b4 |

## Consolidation plan

PATCHHARBOR.15b should consolidate the public docs in the order already recorded by the consolidation order anchor above.

## Public docs acceptance gates

Public documentation is ready when:

1. README is the public entry point and does not duplicate large install blocks.
2. CLI command names and exit codes are documented in one public CLI area.
3. runner behavior is documented in one public runner area.
4. compatibility behavior is documented in one public compatibility area.
5. packaging and installation are documented without local-machine assumptions.
6. migration documents are clearly historical.
7. public docs do not store contributor-specific paths, names, emails, or workstation names.
8. public docs do not require RepoDossier source checkout details except where compatibility history is explicitly discussed.
9. tests cover the public docs inventory before consolidation.
10. target-only docs patches leave the source repository unchanged.

## Non-goals

PATCHHARBOR.15a2 does not:

- rewrite README
- delete migration docs
- change CLI behavior
- change runner behavior
- change package metadata
- change source wrappers
- modify RepoDossier
- mark docs historical

Those changes happen in later 15b and 15c patches.


## PATCHHARBOR.15b1 applied

- Consolidated runner documentation now lives in `docs/runner.md`.
- `docs/download-runner-api-inventory.md`, `docs/download-runner-lifecycle-plan-acceptance.md`, `docs/runner-compatibility-acceptance.md`, and `docs/runner-compatibility-migration.md` remain as inputs and acceptance history.
- No migration artifact is deleted by PATCHHARBOR.15b1.


## PATCHHARBOR.15b2 applied

- Consolidated compatibility documentation now lives in `docs/compatibility.md`.
- `docs/source-wrapper-compatibility-acceptance.md`, `docs/source-side-adoption-acceptance.md`, `docs/workflow-rules-acceptance.md`, and `docs/source-side-alias-compatibility-plan.md` remain as inputs and acceptance history.
- No migration artifact is deleted by PATCHHARBOR.15b2.
