# PatchHarbor.08d source-side runner compatibility tests plan

PatchHarbor.08d defines the source-side runner compatibility tests that must exist before a source repository adopts a PatchHarbor-backed wrapper.

This step is a test plan only. It does not edit RepoDossier, does not create wrapper files, does not install aliases, does not edit shell rc files, and does not commit to the source repository.

## Test plan purpose

The later source-side adoption patch must prove that adding a PatchHarbor-backed runner wrapper is additive, reversible, and does not break the existing local convenience workflow.

PatchHarbor already has target-side APIs for configuration, planning, rendering, runner execution, and CLI display. The source repository must later add focused tests that verify those APIs are wired safely through the source wrapper.

## Required future source-side tests

A later source repository patch should include focused tests for:

| Test area | Required assertion |
| --- | --- |
| existing runner preservation | `scripts/dev/run_latest_download_patch.sh` still exists |
| additive wrapper file | `scripts/dev/run_patchharbor_patch.sh` exists only after the source patch |
| wrapper syntax | the wrapper passes `bash -n` |
| wrapper delegation | the wrapper contains `patchharbor run-script` |
| argument forwarding | the wrapper forwards caller arguments |
| no alias side effect | the wrapper patch does not edit shell rc files |
| no lifecycle mutation | wrapper creation does not move files into done or failed directories |
| export isolation | export scripts remain untouched |
| private-value guard | tracked source files do not store local paths, workstation names, or private addresses |

## Suggested future source-side focused commands

The later source patch should run checks equivalent to:

    test -f scripts/dev/run_latest_download_patch.sh
    test -f scripts/dev/run_patchharbor_patch.sh
    bash -n scripts/dev/run_patchharbor_patch.sh
    grep -q "patchharbor run-script" scripts/dev/run_patchharbor_patch.sh
    grep -q '"$@"' scripts/dev/run_patchharbor_patch.sh

The exact command set belongs in the future source repository patch.

## Compatibility expectations

The wrapper should be a thin, explicit bridge:

    exec patchharbor run-script "$@"

It should not perform download discovery, repeat tracking, done or failed movement, alias installation, export execution, or shell configuration edits.

Those behaviors either remain in the existing local runner until a later parity-tested migration or belong to explicit user-invoked installation commands.

## Target-side proof available now

PatchHarbor can already model the future source wrapper with:

- `CompatibilityConfig`
- `WrapperSpec`
- `AliasSpec`
- `plan_compatibility`
- `render_wrapper_script`
- `render_alias_line`

This target-side proof does not replace the future source-side tests. It only makes the later source patch smaller and easier to verify.

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

This plan is accepted when PatchHarbor documents the future focused tests, command checks, compatibility expectations, target-side proof, and non-goals.

The next patch should add source-side adoption acceptance documentation. It should still avoid modifying source repositories.
