# PatchHarbor workflow rules migration inventory

PatchHarbor.04 starts the migration of patch workflow rules from source-repository-specific development tooling into generic PatchHarbor components.

This step is inventory-only.

No workflow-rules JSON, schema file, validator, runner, or source-repository wrapper is copied in this patch.

## Source-side candidates

| Source file | Future PatchHarbor role | Migration note |
| --- | --- | --- |
| `scripts/dev/patch-workflow-rules.json` | rule data | Convert project-specific policy wording into generic PatchHarbor defaults or fixtures. |
| `scripts/dev/patch-workflow-rules.schema.json` | JSON schema | Generalize schema names and keep project-specific rule packs external. |
| `scripts/dev/validate_patch_workflow_rules.py` | validator | Extract loading and validation behavior after the data model is covered by tests. |
| `tests/test_patch_workflow_rules_schema.py` | regression tests | Rebuild as target-side tests with neutral fixtures and no source-repository assumptions. |
| `scripts/dev/lint_patch_script.py` | consumer | Wire to generic workflow rules only after metadata and rules validation are stable. |
| `scripts/dev/run_latest_download_patch.sh` | consumer | Keep runner migration later; it depends on metadata, linting, safety, and workflow rules. |

## Target-side phases

1. Inventory and boundary documentation.
2. Generic workflow-rules data model.
3. Unit tests with neutral in-memory rule fixtures.
4. Generic JSON schema in the target repository.
5. Rule validator API and CLI-facing smoke tests.
6. Linter integration after the rule contract is stable.
7. Runner integration only after validator and linter behavior is proven.

## Boundaries

PatchHarbor workflow rules must stay repository-agnostic.

RepoDossier-specific file names may appear only as source inventory references during migration. Generic rule APIs should not require RepoDossier, local shell aliases, private paths, private email addresses, workstation names, or a specific contributor environment.

Current patch scripts can keep using the legacy metadata marker while PatchHarbor builds generic support. The workflow-rules migration must not break the existing source runner before compatibility wrappers are planned and tested.

## Non-goals for this step

- no schema copy
- no JSON rules copy
- no validator copy
- no linter integration
- no runner integration
- no source repository changes
