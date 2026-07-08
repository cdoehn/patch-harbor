# PatchHarbor.04 workflow rules acceptance

PatchHarbor.04 establishes a generic workflow-rules foundation in the target repository.

The phase is intentionally limited to reusable foundations. It does not migrate the patch runner, patch-script linter, shell aliases, source-repository wrappers, or project-specific rule policy.

## Accepted scope

PatchHarbor.04 is accepted when the target repository contains:

- workflow-rules migration inventory documentation
- a generic workflow-rules data model
- focused tests for the data model
- a generic workflow-rules JSON schema
- focused tests for the schema structure
- a small generic validator API
- focused tests for validator result handling

## Current target components

| Component | Path |
| --- | --- |
| migration inventory | `docs/workflow-rules-migration.md` |
| data model | `src/patchharbor/workflow_rules.py` |
| model tests | `tests/test_workflow_rules.py` |
| JSON schema | `schemas/workflow-rules.schema.json` |
| schema tests | `tests/test_workflow_rules_schema.py` |
| validator API | `src/patchharbor/workflow_validation.py` |
| validator tests | `tests/test_workflow_validation.py` |

## Acceptance behavior

The generic rules model can load neutral JSON rule documents, enforce basic model invariants, detect duplicate rule identifiers, and keep rule-specific extension fields as plain data.

The schema documents the neutral JSON shape for the same model without adding a runtime dependency on a schema validation package.

The validator API wraps model loading into an explicit validation result with stable issue rendering, summary lines, and error raising.

## Explicit non-goals

PatchHarbor.04 does not migrate:

- patch-script linting rules
- the download patch runner
- export runners
- local shell aliases
- source-repository compatibility wrappers
- project-specific workflow policy data

Those belong to later phases after the generic foundation is accepted.

## Boundary

RepoDossier remains unchanged during this phase.

PatchHarbor keeps reusable logic generic and tested before source-repository wrappers are changed.
