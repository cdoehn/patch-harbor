# PatchHarbor.08c source-side alias compatibility plan

PatchHarbor.08c plans source-side alias compatibility before any alias installer is changed.

This step is a plan only. It does not edit RepoDossier, does not install aliases, does not edit shell rc files, does not create wrapper files, and does not commit to the source repository.

## Plan purpose

The later alias update should keep the user's established convenience workflow available while allowing thin source-side wrappers to delegate generic behavior to PatchHarbor.

Alias changes are intentionally separated from the runner-wrapper draft. This keeps the future source patch reversible and prevents hidden shell integration changes.

## Alias candidates

| Alias | Current meaning | Planned direction | Status |
| --- | --- | --- | --- |
| `c` | local convenience command for the download patch runner | preserve first; later point to a source-side compatibility wrapper only after source tests prove parity | high-risk |
| `r` | local convenience command for export workflow | defer until export migration is planned | deferred |
| `patchharbor-patch` | explicit new compatibility alias candidate | optional additive alias for the future source-side wrapper | safe draft candidate |

## Preferred future shape

The safest future alias plan is additive:

1. Keep the existing `c` alias behavior unchanged until parity is tested.
2. Add or document an explicit compatibility alias for the new wrapper.
3. Only after source-side tests pass, consider whether `c` should point to the new source wrapper.
4. Never write machine-local paths into tracked files.
5. Never edit shell rc files outside an explicit alias-installation command.

The draft compatibility alias can be modeled as plain data:

    alias name: patchharbor-patch
    alias command: scripts/dev/run_patchharbor_patch.sh

The existing rendering API can render that as:

    alias patchharbor-patch=scripts/dev/run_patchharbor_patch.sh

## Required safeguards for the later alias patch

Before any source-side alias installer changes are allowed, the patch must prove:

- the existing alias installer still exists
- the alias update is additive or explicitly reversible
- the old convenience command is not silently broken
- shell rc-file edits happen only when the installer is executed by the user
- tracked files do not store private paths, workstation names, or email addresses
- export aliases are not changed in the patch-runner adoption step
- focused source-side tests run before the full suite

## Non-goals for this step

- no RepoDossier file changes
- no source repository commits
- no alias installation
- no shell rc-file changes
- no wrapper file writes
- no replacement of the current convenience alias
- no export alias migration
- no download-folder mutation
- no deletion of old source scripts

## Proposed later checks

A later source-side alias patch should include checks equivalent to:

    test -f scripts/dev/install_aliases.sh
    grep -q "patchharbor-patch" scripts/dev/install_aliases.sh
    grep -q "scripts/dev/run_patchharbor_patch.sh" scripts/dev/install_aliases.sh

Those checks belong to the source repository patch, not to this target-side plan.

## Acceptance

This plan is accepted when PatchHarbor documents the alias candidates, preferred future shape, required safeguards, non-goals, and a tested in-memory alias rendering example.

The next patch should prepare source-side runner compatibility tests. It should still avoid broad source repository migration.
