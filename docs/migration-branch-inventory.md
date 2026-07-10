# PATCHHARBOR.17c1 – Branch inventory

This document records the migration branch inventory procedure before branch cleanup commands are documented.

It is target-only. It documents safe read-only commands for inspecting local and remote branches in the PatchHarbor target repository and RepoDossier source repository. It intentionally does not store concrete branch names because branch names can contain private contributor context and can change after cleanup.

## Plan contract

| Field | Value |
| --- | --- |
| Patch id | PATCHHARBOR.17c1 |
| Plan title | Branch Inventory |
| Commit | Document migration branch inventory |
| Operative plan | `planning/milestones_migration.md` |

## Inventory goals

The branch inventory step must answer these questions before cleanup:

1. which local branches exist in PatchHarbor
2. which remote-tracking branches exist in PatchHarbor
3. which local branches exist in RepoDossier
4. which remote-tracking branches exist in RepoDossier
5. which branch is currently checked out in each repository
6. whether `main` exists locally
7. whether `origin/main` exists as a remote-tracking branch
8. whether a branch appears merged into `main`
9. whether a branch is unmerged and needs manual review
10. whether cleanup commands would be local-only or remote-affecting

## Safe read-only commands

Run these commands in the relevant repository.

List local branches:

    git branch --format='%(refname:short)'

List remote-tracking branches:

    git branch -r --format='%(refname:short)'

Show current branch:

    git branch --show-current

Show last commit on each local branch:

    git branch -vv

Show branches merged into main:

    git branch --merged main

Show branches not merged into main:

    git branch --no-merged main

Check whether local main exists:

    git show-ref --verify --quiet refs/heads/main

Check whether origin main exists:

    git show-ref --verify --quiet refs/remotes/origin/main

## Repository boundary

The branch inventory is read-only.

It must not:

- delete local branches
- delete remote branches
- push to a remote
- fetch from a remote
- create tags
- publish releases
- rewrite history
- change `pyproject.toml`
- edit RepoDossier source files
- edit PatchHarbor runtime code
- edit shell aliases
- edit shell rc files

## Why concrete branch names are not stored

Concrete branch names are intentionally not committed into this public document.

Reasons:

- branch names are mutable
- branch names can include private task names
- branch names can include contributor-specific context
- branch cleanup will intentionally change branch inventory later
- future tests should not fail merely because cleanup succeeded

Instead, this document stores the safe inventory commands and the acceptance rules for using them.

## Acceptance rules

PATCHHARBOR.17c1 is accepted when:

1. the inventory document exists
2. the inventory test exists
3. both repositories are valid git repositories
4. both repositories expose branch inventory commands successfully
5. the operative plan defines PATCHHARBOR.17c1 as Branch Inventory
6. no branch cleanup command is documented as already executed
7. no private/local values are stored in the inventory docs or tests
8. the next operative step is PATCHHARBOR.17c2 – Local Branch Cleanup Commands

## Handoff

The next operative plan step is:

    PATCHHARBOR.17c2 – Local Branch Cleanup Commands

PATCHHARBOR.17c2 should document local branch cleanup commands, but still must not delete remote branches.


## PATCHHARBOR.17c2 applied

- PATCHHARBOR.17c2 adds local branch cleanup commands in `docs/local-branch-cleanup-commands.md` and `tests/test_local_branch_cleanup_commands.py`; this inventory remains read-only and does not execute deletion commands.


## PATCHHARBOR.17c3 applied

- PATCHHARBOR.17c3 adds remote branch cleanup command templates in `docs/remote-branch-cleanup-commands.md` and `tests/test_remote_branch_cleanup_commands.py`; no remote action is executed by tests.


## PATCHHARBOR.17c4 applied

- PATCHHARBOR.17c4 adds final repository hygiene acceptance in `docs/final-repository-hygiene-acceptance.md` and `tests/test_final_repository_hygiene_acceptance.py`; inventory remains read-only.
