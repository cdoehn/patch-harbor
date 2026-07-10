# PATCHHARBOR.17c3 – Remote branch cleanup commands

This document records remote branch cleanup commands after local branch cleanup commands.

It is target-only. It documents review-gated remote cleanup commands but does not execute them. It does not push, fetch, delete branches, create tags, publish releases, or change metadata.

## Plan contract

| Field | Value |
| --- | --- |
| Patch id | PATCHHARBOR.17c3 |
| Plan title | Remote Branch Cleanup Commands |
| Commit | Document remote branch cleanup commands |
| Operative plan | `planning/milestones_migration.md` |

## Safety rule

Remote branch cleanup is destructive for shared repositories.

Run these commands only after:

1. PATCHHARBOR.17c1 branch inventory is complete
2. PATCHHARBOR.17c2 local branch cleanup commands are reviewed
3. the local working tree is clean
4. the branch is confirmed obsolete
5. the branch is confirmed not to be `main`
6. the branch is confirmed not to be needed by another collaborator

This document does not execute any remote cleanup command.

## Read-only remote inventory commands

List remote-tracking branches:

    git branch -r --format='%(refname:short)'

Inspect remote URL names without printing sensitive URLs in committed docs:

    git remote

Inspect remote-tracking refs:

    git for-each-ref refs/remotes --format='%(refname:short)'

Check origin main:

    git show-ref --verify --quiet refs/remotes/origin/main

## Remote deletion preview checklist

Before deleting a remote branch, confirm all of these manually:

- the target remote is correct
- the target branch name is correct
- the branch is not `main`
- the branch is not `master`
- the branch is not currently used for an open review
- the branch is not needed for rollback
- local cleanup has already been considered
- the deletion command is typed explicitly with the intended branch name

## Remote branch deletion command template

After manual review, the command template is:

    git push origin --delete BRANCH_NAME

Replace `BRANCH_NAME` manually.

Do not pipe branch lists into remote deletion commands.

Do not use `xargs` for remote deletion.

Do not delete multiple remote branches in one command unless each branch has been reviewed.

## Safer dry-run style review

Git does not provide a universal dry-run for remote branch deletion that is guaranteed to match every host and permission model.

Use this safer review flow instead:

1. list remote branches
2. copy the exact branch name into a scratch note
3. verify the branch with `git ls-remote --heads origin BRANCH_NAME`
4. ask for human confirmation
5. run one explicit deletion command

The read-only verification command is:

    git ls-remote --heads origin BRANCH_NAME

## What this step must not do

PATCHHARBOR.17c3 must not:

- execute remote branch deletion
- push to a remote
- fetch from remotes
- create or push git tags
- publish a release
- change package metadata
- edit RepoDossier source files
- edit PatchHarbor runtime code
- edit shell aliases
- edit shell rc files
- store concrete private branch names in public docs
- pipe branch lists into `git push origin --delete`

## Repository boundary

Run remote cleanup commands separately in PatchHarbor and RepoDossier only after confirming the intended repository.

Do not mix source and target remotes.

Do not commit private branch names or remote URLs into public docs.

## Acceptance rules

PATCHHARBOR.17c3 is accepted when:

1. remote cleanup command templates are documented
2. tests verify the commands are documented but not executed
3. docs explicitly forbid piped remote deletion
4. docs explicitly require manual branch-name replacement
5. source status remains unchanged by the test suite
6. no private/local values are stored in docs or tests
7. the next operative step is PATCHHARBOR.17c4 – Final Repository Hygiene Acceptance

## Handoff

The next operative plan step is:

    PATCHHARBOR.17c4 – Final Repository Hygiene Acceptance

PATCHHARBOR.17c4 should aggregate branch inventory, local cleanup commands, and remote cleanup commands into final repository hygiene acceptance.
