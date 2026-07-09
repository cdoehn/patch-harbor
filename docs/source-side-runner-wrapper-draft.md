# PatchHarbor.08b source-side runner wrapper draft

PatchHarbor.08b drafts the source-side runner wrapper contract before any source repository is changed.

This step is a draft only. It does not edit RepoDossier, does not create wrapper files, does not install aliases, does not replace the current local download runner, and does not commit to the source repository.

## Draft purpose

The later source-side runner wrapper should keep the existing convenience workflow available while delegating generic runner behavior to PatchHarbor.

The draft exists to make the future source patch small and reviewable. It describes the intended file, command shape, safeguards, and acceptance checks before mutation begins.

## Candidate source file

The preferred first adoption target is a new, thin wrapper file instead of immediately replacing the existing local runner:

| Candidate | Status | Reason |
| --- | --- | --- |
| `scripts/dev/run_patchharbor_patch.sh` | draft candidate | can be added without deleting the current runner |
| `scripts/dev/run_latest_download_patch.sh` | preserve initially | high-risk local workflow; replace only after parity checks |
| `scripts/dev/install_aliases.sh` | later alias phase | alias changes should be planned separately |
| `scripts/dev/r.sh` | deferred | export workflow should stay untouched in this phase |

## Draft wrapper command shape

The first wrapper should be a thin source-side entry point around the explicit PatchHarbor runner command.

Indented shell sketch:

    #!/usr/bin/env bash
    set -euo pipefail
    exec patchharbor run-script "$@"

That is intentionally minimal. Source-specific download discovery, done/failed movement, and alias installation are not added to this draft.

## Draft compatibility configuration

A later source patch can represent the wrapper as plain compatibility data:

    source_name: RepoDossier
    wrapper name: patchharbor-patch-runner
    wrapper kind: runner
    wrapper relative path: scripts/dev/run_patchharbor_patch.sh
    wrapper command: patchharbor run-script
    alias name: optional and deferred

The wrapper rendering API can already render this as shell text. The source patch should still write the file explicitly and test it in the source repository rather than relying on hidden mutation.

## Required safeguards for the later source patch

Before a source-side wrapper file is added, the patch must prove:

- the existing local download runner still exists
- the new wrapper is additive and reversible
- the wrapper calls `patchharbor run-script`
- the wrapper passes caller arguments through
- the wrapper does not hardcode private paths or workstation names
- the wrapper does not install aliases
- the wrapper does not move files into done or failed directories
- the wrapper does not touch export scripts
- focused source-side tests run before the full suite

## Non-goals for this draft

- no RepoDossier file changes
- no source repository commits
- no wrapper file writes
- no alias installation
- no shell rc-file changes
- no download-folder mutation
- no replacement of the current local runner
- no export runner migration
- no deletion of old source scripts

## Proposed later source-side checks

A later source-side patch should include checks equivalent to:

    test -f scripts/dev/run_latest_download_patch.sh
    test -f scripts/dev/run_patchharbor_patch.sh
    bash -n scripts/dev/run_patchharbor_patch.sh
    grep -q "patchharbor run-script" scripts/dev/run_patchharbor_patch.sh

The exact checks belong to the source repository patch, not to this target-side draft.

## Acceptance

This draft is accepted when PatchHarbor documents the wrapper candidate, the intended command shape, the required safeguards, and the non-goals.

The next patch should plan alias compatibility separately. It should not install aliases yet.
