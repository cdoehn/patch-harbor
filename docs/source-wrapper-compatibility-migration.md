<!-- PATCHHARBOR.15b4 historical-migration-doc -->

> Historical migration document.
>
> This file records PatchHarbor extraction and adoption history. It is retained for traceability, but it is not the current public command contract.
> Current public runner docs live in `docs/runner.md`; compatibility docs live in `docs/compatibility.md`; CLI docs live in `docs/cli.md`.

# PatchHarbor source-wrapper compatibility migration inventory

PatchHarbor.07 starts the source-wrapper compatibility layer.

This step is inventory-only.

No wrapper source code, alias installation, shell rc-file edit, source-repository patch, automatic download runner replacement, export runner replacement, or source-repository commit is introduced in this patch.

## Purpose

PatchHarbor.06 established generic target-side runner primitives and an explicit `patchharbor run-script <file>` command.

PatchHarbor.07 plans the next boundary: how source repositories can later keep thin compatibility wrappers while delegating reusable behavior to PatchHarbor.

The goal is to avoid copying old project-specific scripts into the generic package and to avoid changing source repositories before the wrapper contract is tested.

## Source-side candidates

| Source file | Current role | Future wrapper direction |
| --- | --- | --- |
| `scripts/dev/run_latest_download_patch.sh` | local download patch runner behind the `c` workflow | later keep a thin source-side wrapper or config that delegates to PatchHarbor runner primitives |
| `scripts/dev/install_aliases.sh` | local alias installer | later install aliases that call source wrappers or PatchHarbor commands without storing private paths in tracked files |
| `scripts/dev/r.sh` | short export runner entry wrapper | later keep as a source-specific compatibility wrapper for export workflows |
| `scripts/dev/run_repodossier_exports.sh` | source-specific export runner | later split generic export-runner behavior from source-specific commands and defaults |
| `scripts/dev/repo_patch_helper.py` | patch helper and process utilities | use only as behavior reference where target primitives do not already exist |
| `scripts/dev/show_progress_context.py` | progress, context, milestone, and footer display | source behavior reference; generic display now belongs in PatchHarbor runner display components |
| `scripts/dev/validate_patch_metadata.py` | source metadata validator | compatibility reference only; target metadata and preflight APIs are the canonical generic path |
| `scripts/dev/lint_patch_script.py` | source patch linting wrapper | compatibility reference only; target patch-lint APIs are the canonical generic path |
| `scripts/dev/patch-rules.md` | human workflow contract | source-specific guidance reference, not generic runtime code |

## Wrapper boundaries

Future wrapper work must keep these layers separate:

1. Generic PatchHarbor APIs and CLI commands.
2. Source-repository wrapper scripts that map local workflows to those APIs.
3. Local alias or shell integration that lives in a user's shell configuration, not in tracked generic code.
4. Source-specific defaults and safety rules that stay outside generic target modules.

PatchHarbor should not assume a contributor home directory, workstation name, private email address, local checkout path, or a specific alias such as `c` or `r`.

Source repositories should not copy generic runner, lint, lifecycle, or display logic after PatchHarbor owns those contracts.

## Candidate target-side phases

1. Source-wrapper compatibility inventory.
2. Compatibility configuration model for source-specific wrapper defaults.
3. Wrapper planning API that returns intended wrapper actions without writing files.
4. Wrapper rendering API for thin shell or Python entry wrappers.
5. Acceptance documentation before any source repository is changed.

## Behavior to preserve later

Later wrapper adoption should preserve the useful user-facing behavior without baking it into generic APIs:

- local patch-runner convenience can remain available through source-side wrappers
- repeat detection must prevent accidental re-runs
- freshness and metadata checks remain explicit
- failed patches must tell the user to repair the current patch before continuing
- display output should include done, current, next, and problem sections
- source-specific export commands remain source-specific until export-runner migration is planned
- alias installation must write only to local shell configuration, not to tracked files

## Non-goals for this step

- no wrapper code generation
- no wrapper file writes
- no alias installation
- no shell rc-file changes
- no replacement of current source runner
- no download-folder mutation
- no export runner migration
- no source repository changes
- no compatibility command adoption
- no source-repository commits

## Acceptance

This inventory is accepted when PatchHarbor documents the wrapper boundary and tests that the planned source candidates, target phases, and non-goals are present.

The next patch should add a generic compatibility configuration model. It should still avoid writing source wrapper files.
