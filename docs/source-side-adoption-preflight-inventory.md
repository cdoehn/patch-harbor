<!-- PATCHHARBOR.15b4 historical-migration-doc -->

> Historical migration document.
>
> This file records PatchHarbor extraction and adoption history. It is retained for traceability, but it is not the current public command contract.
> Current public runner docs live in `docs/runner.md`; compatibility docs live in `docs/compatibility.md`; CLI docs live in `docs/cli.md`.

# PatchHarbor.09a source-side adoption preflight inventory

PatchHarbor.09a prepares the first real source-side adoption patch.

This step is still non-mutating. It does not edit RepoDossier, does not write wrapper files, does not install aliases, does not edit shell rc files, and does not commit to the source repository.

## Purpose

PATCHHARBOR.09 is the first phase that may modify the source repository.

Before that happens, this preflight inventory defines the checks that must be true for both repositories and the guardrails that every source-side patch must follow.

## Repository roles

| Repository | Role in PATCHHARBOR.09 |
| --- | --- |
| PatchHarbor target repository | owns generic runner, wrapper configuration, planning, rendering, documentation, and target-side tests |
| RepoDossier source repository | may receive additive wrapper files and source-side tests after preflight is accepted |

## Required preflight before source mutation

Before PATCHHARBOR.09b may add a source-side wrapper, the patch must confirm:

- source repository path resolves to RepoDossier
- target repository path resolves to PatchHarbor
- both repositories are Git repositories
- both repositories have Git identity configured
- both repositories have no unrelated staged changes
- existing source download runner still exists
- existing source alias installer still exists
- existing export runner scripts still exist
- PatchHarbor CLI exposes `run-script`
- PatchHarbor target tests are green
- RepoDossier source tests are green or a known focused subset is justified
- migration roadmap and migration milestones are present in the source planning directory
- no private paths, workstation names, or private addresses are introduced

## Source files that must remain preserved in PATCHHARBOR.09b

The first additive wrapper patch must not remove or replace:

- `scripts/dev/run_latest_download_patch.sh`
- `scripts/dev/install_aliases.sh`
- `scripts/dev/r.sh`
- `scripts/dev/run_repodossier_exports.sh`
- `scripts/dev/repo_patch_helper.py`
- `scripts/dev/show_progress_context.py`

## Expected PATCHHARBOR.09b source addition

The intended new source-side wrapper is:

    scripts/dev/run_patchharbor_patch.sh

The intended command is:

    exec patchharbor run-script "$@"

The wrapper must be additive and reversible. It must not change the current local download runner, the current convenience alias, or export scripts.

## Required focused checks for PATCHHARBOR.09b

The later wrapper patch should run checks equivalent to:

    test -f scripts/dev/run_latest_download_patch.sh
    test -f scripts/dev/install_aliases.sh
    test -f scripts/dev/r.sh
    test -f scripts/dev/run_repodossier_exports.sh
    test -f scripts/dev/run_patchharbor_patch.sh
    bash -n scripts/dev/run_patchharbor_patch.sh
    grep -q "patchharbor run-script" scripts/dev/run_patchharbor_patch.sh
    grep -q '"$@"' scripts/dev/run_patchharbor_patch.sh

## Guardrails for source-side patches

Every PATCHHARBOR.09 source-side patch must explicitly state:

- which repository is modified
- which source files are touched
- whether the patch is additive or replacing behavior
- how rollback works
- which focused tests prove the change
- whether aliases are changed
- whether export scripts are untouched
- whether the old local runner is preserved
- how private and source-specific values are guarded

## Non-goals for this step

- no RepoDossier file changes
- no source repository commits
- no wrapper file writes
- no alias installation
- no shell rc-file changes
- no download-folder mutation
- no export runner migration
- no replacement of the current local runner
- no deletion of old source scripts

## Acceptance

This preflight inventory is accepted when PatchHarbor documents the repository roles, preflight checks, preserved source files, expected wrapper addition, focused checks, guardrails, and non-goals.

The next patch may be the first additive source-side wrapper patch, but it must remain narrow and reversible.
