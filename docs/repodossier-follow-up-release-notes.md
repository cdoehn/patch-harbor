# PATCHHARBOR.17b3 – RepoDossier follow-up release notes

These are the RepoDossier follow-up release notes for the migration-stabilization release candidate.

The notes are stored in the PatchHarbor target repository as migration coordination documentation. They read RepoDossier source metadata but do not edit RepoDossier files.

## Release identity

| Item | Value |
| --- | --- |
| Patch id | PATCHHARBOR.17b3 |
| Plan title | RepoDossier Follow-up Release Notes |
| Commit | Add RepoDossier follow-up release notes |
| Source package | `repodossier` |
| Source version | `1.0.0` |
| Related PatchHarbor version | `0.1.0` |

## Summary

RepoDossier keeps the project-specific repository analysis and export behavior after the PatchHarbor extraction.

PatchHarbor now owns the generic patch-runner and patch-lifecycle behavior. RepoDossier keeps its domain-specific source wrappers, export workflow, and follow-up release track.

## What changed through the migration

- PatchHarbor was split out as the generic patch-runner target.
- RepoDossier keeps the source-side wrapper contracts for `c` and `r`.
- RepoDossier remains the source of the operative migration plan in `planning/milestones_migration.md`.
- RepoDossier source files are not changed by this follow-up release-notes patch.
- PatchHarbor stores the migration coordination evidence and release notes for this phase.

## RepoDossier follow-up evidence

The follow-up release notes rely on these accepted artifacts:

| Area | Evidence |
| --- | --- |
| RepoDossier version decision | `docs/repodossier-follow-up-version-decision.md` |
| PatchHarbor release notes | `docs/patchharbor-release-notes.md` |
| PatchHarbor build smoke | `docs/patchharbor-release-build-smoke.md` |
| final migration acceptance | `docs/final-migration-acceptance.md` |
| rollback notes | `docs/migration-rollback-notes.md` |
| completion checklist | `docs/migration-completion-checklist.md` |

## Source-side compatibility notes

RepoDossier follow-up compatibility focuses on:

- keeping `scripts/dev/run_latest_download_patch.sh` as the source-side Download patch workflow
- keeping `scripts/dev/run_patchharbor_patch.sh` as the source-side PatchHarbor bridge
- keeping `scripts/dev/r.sh` as the source-side export workflow entry point
- keeping `scripts/dev/run_repodossier_exports.sh` as the source-side export runner
- keeping source wrappers readable and syntax-checkable by PatchHarbor dual-repo smoke tests

## Known non-goals for this patch

PATCHHARBOR.17b3 does not:

- change RepoDossier `pyproject.toml`
- change PatchHarbor `pyproject.toml`
- change package version metadata
- build a release artifact
- publish a release
- create or push git tags
- clean local branches
- clean remote branches
- change PatchHarbor runtime code
- change RepoDossier runtime code
- edit source wrappers
- edit shell aliases
- edit shell rc files

## Next step

The next operative plan step is:

    PATCHHARBOR.17c1 – Branch Inventory

PATCHHARBOR.17c1 should document the migration branch inventory before local or remote branch cleanup commands are documented.
