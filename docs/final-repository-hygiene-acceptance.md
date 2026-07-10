# PATCHHARBOR.17c4 – Final repository hygiene acceptance

This document records final repository hygiene acceptance for the migration release and branch-hygiene phase.

It is target-only. It aggregates branch inventory, local branch cleanup command documentation, and remote branch cleanup command documentation. It does not execute cleanup commands.

## Plan contract

| Field | Value |
| --- | --- |
| Patch id | PATCHHARBOR.17c4 |
| Plan title | Final Repository Hygiene Acceptance |
| Commit | Add final repository hygiene acceptance |
| Operative plan | `planning/milestones_migration.md` |

## Accepted evidence

The final repository hygiene acceptance depends on:

| Patch | Evidence |
| --- | --- |
| PATCHHARBOR.17c1 | `docs/migration-branch-inventory.md` and `tests/test_migration_branch_inventory.py` |
| PATCHHARBOR.17c2 | `docs/local-branch-cleanup-commands.md` and `tests/test_local_branch_cleanup_commands.py` |
| PATCHHARBOR.17c3 | `docs/remote-branch-cleanup-commands.md` and `tests/test_remote_branch_cleanup_commands.py` |
| PATCHHARBOR.17c4 | `docs/final-repository-hygiene-acceptance.md` and `tests/test_final_repository_hygiene_acceptance.py` |

## Acceptance contract

Repository hygiene is accepted when:

1. branch inventory commands are documented
2. local branch cleanup commands are documented
3. remote branch cleanup command templates are documented
4. local cleanup is explicitly separated from remote cleanup
5. remote cleanup requires manual branch-name replacement
6. remote cleanup forbids piped deletion
7. tests execute only read-only git inventory commands
8. tests do not execute branch deletion commands
9. tests do not push, fetch, tag, or publish
10. source status remains unchanged by the acceptance test suite
11. no private/local values are stored in public docs or tests
12. literal Markdown fences are absent from public docs and tests

## Explicitly not executed

PATCHHARBOR.17c4 does not execute:

- `git branch -d`
- `git branch -D`
- `git push origin --delete`
- `git fetch`
- `git push`
- `git tag`
- package publish commands
- release upload commands

The cleanup documents are command references. They are not evidence that cleanup has already been performed.

## Repository boundary

PatchHarbor and RepoDossier must be inspected separately.

Do not mix source and target repositories.

Do not store concrete private branch names in committed docs.

Do not store remote URLs in committed docs.

## Final hygiene summary

Milestone 17 branch hygiene is documentation-complete when:

- PATCHHARBOR.17c1 branch inventory is green
- PATCHHARBOR.17c2 local branch cleanup commands are green
- PATCHHARBOR.17c3 remote branch cleanup commands are green
- PATCHHARBOR.17c4 final repository hygiene acceptance is green

Any real branch deletion remains a human-controlled operation outside these documentation patches.

## Handoff

After this patch is green, inspect `planning/milestones_migration.md` for the next operative patch slot.

Do not infer a next milestone from roadmap text alone.
