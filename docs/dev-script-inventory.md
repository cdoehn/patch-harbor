<!-- PATCHHARBOR.15b4 historical-migration-doc -->

> Historical migration document.
>
> This file records PatchHarbor extraction and adoption history. It is retained for traceability, but it is not the current public command contract.
> Current public runner docs live in `docs/runner.md`; compatibility docs live in `docs/compatibility.md`; CLI docs live in `docs/cli.md`.

# PatchHarbor Dev-Script migration inventory

This inventory tracks the reusable Dev-Script candidates that should be extracted into PatchHarbor.

The source repository remains unchanged during this step. PatchHarbor records only repository-relative source paths and migration notes.

## Migration rules

- Extract behavior in small commits.
- Keep source-repository wrappers until PatchHarbor behavior is tested.
- Generalize project names, paths, and command assumptions before adoption.
- Do not store contributor-specific local paths, private email addresses, user names, or workstation names in tracked files.
- Do not migrate the full patch runner before metadata, workflow rules, and safety checks are covered in PatchHarbor tests.

## Candidate inventory

| Source file | Role | Migration note |
| --- | --- | --- |
| `scripts/dev/audit_public_repo.py` | audit | public-repository audit; extract after private-value and safety policy is generic |
| `scripts/dev/check_dev_environment.py` | diagnostic | environment checks; extract after target configuration shape is known |
| `scripts/dev/install_aliases.sh` | installer | local alias installer; keep local-path writes out of tracked files |
| `scripts/dev/lint_patch_script.py` | validator | patch-script linting; good candidate after metadata model is generic |
| `scripts/dev/patch-rules.md` | docs | human patch-contract documentation; migrate after generic contract stabilizes |
| `scripts/dev/patch-workflow-rules.json` | rules | current workflow policy data; generalize names and project assumptions |
| `scripts/dev/patch-workflow-rules.schema.json` | schema | JSON schema for workflow policy data; keep close to rule validator |
| `scripts/dev/r.sh` | wrapper | current export runner entry wrapper; keep compatibility until PatchHarbor runner is stable |
| `scripts/dev/repo_patch_helper.py` | utility | patch helper functions; extract reusable file, git, footer, and process helpers incrementally |
| `scripts/dev/run_latest_download_patch.sh` | runner | current c/download patch runner; extract late after metadata and safety rules exist |
| `scripts/dev/run_repodossier_exports.sh` | runner | RepoDossier export runner; split generic runner behavior from RepoDossier commands |
| `scripts/dev/show_progress_context.py` | display | progress/context renderer; extract after metadata records are generic |
| `scripts/dev/validate_patch_metadata.py` | validator | metadata parser and validator; key early extraction candidate |
| `scripts/dev/validate_patch_workflow_rules.py` | validator | workflow-rule validator; extract after rules schema is generalized |

## Suggested extraction order

1. Shared color, footer, command-running, and repository-path helpers.
2. Patch metadata parsing and validation.
3. Generic workflow-rule schema and rule validation.
4. Patch-script linting independent of RepoDossier wording.
5. Progress/context display helpers.
6. Runner wrappers for c and r after the generic components are tested.

## Not migrated yet

No source Dev-Script files are copied in this step. This keeps PatchHarbor.03a as an inventory-only baseline before the first reusable utility extraction.
