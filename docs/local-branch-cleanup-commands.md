# PATCHHARBOR.17c2 – Local branch cleanup commands

This document records local-only branch cleanup commands after the migration branch inventory.

It is target-only. It documents cleanup commands but does not execute them. It does not delete branches, push to remotes, fetch from remotes, create tags, or publish releases.

## Plan contract

| Field | Value |
| --- | --- |
| Patch id | PATCHHARBOR.17c2 |
| Plan title | Local Branch Cleanup Commands |
| Commit | Document local branch cleanup commands |
| Operative plan | `planning/milestones_migration.md` |

## Safety rule

Run local cleanup only after PATCHHARBOR.17c1 branch inventory is complete and after the working tree is clean.

Do not run remote cleanup from this step.

## Preflight checks

Run these checks in each repository before deleting any local branch.

Confirm current branch:

    git branch --show-current

Confirm working tree state:

    git status --short

Confirm local main exists:

    git show-ref --verify --quiet refs/heads/main

Inspect local branches:

    git branch --format='%(refname:short)'

Inspect merged branches:

    git branch --merged main --format='%(refname:short)'

Inspect unmerged branches:

    git branch --no-merged main --format='%(refname:short)'

## Preview safe local deletion candidates

Merged local branches can be previewed with:

    git branch --merged main --format='%(refname:short)' | grep -vE '^(main|master)$'

Do not delete the current branch.

Do not delete `main`.

Do not delete an unmerged branch unless it has been manually reviewed.

## Safe merged-branch cleanup command

After previewing the candidate list, switch to main:

    git switch main

Then delete only merged local branches except main and master:

    git branch --merged main --format='%(refname:short)' | grep -vE '^(main|master)$' | xargs -r git branch -d

This command is local-only. It does not delete remote branches.

## Manual unmerged-branch cleanup

Unmerged branches require explicit manual review.

Preview them first:

    git branch --no-merged main --format='%(refname:short)' | grep -vE '^(main|master)$'

If a branch is confirmed obsolete, delete it locally by replacing the placeholder:

    git branch -D BRANCH_NAME

Use forced local deletion only after manual review.

## What this step must not do

PATCHHARBOR.17c2 must not:

- delete remote branches
- push branch deletion
- fetch from remotes
- create or push git tags
- publish a release
- change package metadata
- edit RepoDossier source files
- edit PatchHarbor runtime code
- edit shell aliases
- edit shell rc files
- store concrete private branch names in public docs

## Repository boundary

Run these commands separately in PatchHarbor and RepoDossier as needed.

Do not mix source and target paths.

Do not document private branch names in committed files.

## Acceptance rules

PATCHHARBOR.17c2 is accepted when:

1. local cleanup commands are documented
2. tests verify the commands are local-only
3. tests do not execute deletion commands
4. remote cleanup is explicitly out of scope
5. source status remains unchanged by the test suite
6. no private/local values are stored in docs or tests
7. the next operative step is PATCHHARBOR.17c3 – Remote Branch Cleanup Commands

## Handoff

The next operative plan step is:

    PATCHHARBOR.17c3 – Remote Branch Cleanup Commands

PATCHHARBOR.17c3 may document remote cleanup commands, but this patch must not.


## PATCHHARBOR.17c3 applied

- PATCHHARBOR.17c3 adds remote branch cleanup command templates in `docs/remote-branch-cleanup-commands.md` and `tests/test_remote_branch_cleanup_commands.py`; local cleanup remains local-only.


## PATCHHARBOR.17c4 applied

- PATCHHARBOR.17c4 adds final repository hygiene acceptance in `docs/final-repository-hygiene-acceptance.md` and `tests/test_final_repository_hygiene_acceptance.py`; local cleanup commands remain documentation only.
