# PATCHHARBOR.17b1 – PatchHarbor release notes

These are the PatchHarbor release notes for the migration-stabilization release candidate.

## Release identity

| Item | Value |
| --- | --- |
| Patch id | PATCHHARBOR.17b1 |
| Plan title | PatchHarbor Release Notes |
| Commit | Add PatchHarbor release notes |
| Package | `patchharbor` |
| Version | `0.1.0` |
| Related RepoDossier follow-up version | `1.0.0` |

## Summary

PatchHarbor is the extracted generic patch-runner and patch-lifecycle tool that was migrated out of RepoDossier.

This release candidate documents the post-migration state after the dual-repository acceptance series and the version-decision series.

## Highlights

- PatchHarbor has its own target repository, package, CLI, docs, and tests.
- Public CLI behavior is documented in `docs/cli.md`.
- Runner behavior is documented in `docs/runner.md`.
- Compatibility behavior is documented in `docs/compatibility.md`.
- Public API surfaces are inventoried in `docs/public-api-inventory.md`.
- Public readiness is documented in `docs/public-readiness-acceptance.md`.
- Final migration acceptance is documented in `docs/final-migration-acceptance.md`.
- PatchHarbor version decision is documented in `docs/patchharbor-version-decision.md`.
- RepoDossier follow-up version decision is documented in `docs/repodossier-follow-up-version-decision.md`.

## Migration acceptance evidence

The release notes rely on these accepted milestone artifacts:

| Area | Evidence |
| --- | --- |
| final migration acceptance | `docs/final-migration-acceptance.md` |
| private value audit | `docs/dual-repo-private-value-audit.md` |
| rollback notes | `docs/migration-rollback-notes.md` |
| completion checklist | `docs/migration-completion-checklist.md` |
| PatchHarbor version decision | `docs/patchharbor-version-decision.md` |
| RepoDossier follow-up version decision | `docs/repodossier-follow-up-version-decision.md` |

## Public command surface

The release candidate keeps the existing public command surface:

- `patchharbor --help`
- `patchharbor --version`
- `patchharbor doctor --repo`
- `patchharbor lint-script`
- `patchharbor run-script`
- `patchharbor audit-public`
- `patchharbor check-env`

## Compatibility notes

PatchHarbor keeps compatibility with the migrated RepoDossier workflows through documented source wrapper contracts.

RepoDossier remains the source repository for its domain-specific wrapper behavior. PatchHarbor remains the target repository for the generic patch runner.

## Known non-goals for this patch

PATCHHARBOR.17b1 does not:

- change `pyproject.toml`
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

    PATCHHARBOR.17b2 – PatchHarbor Release Build Smoke

PATCHHARBOR.17b2 should prove that the release candidate can be built and inspected without publishing it.


## PATCHHARBOR.17b2 applied

- PATCHHARBOR.17b2 adds the PatchHarbor release build smoke in `docs/patchharbor-release-build-smoke.md` and `tests/test_patchharbor_release_build_smoke.py`; the smoke builds a local wheel without publishing.


## PATCHHARBOR.17b3 applied

- PATCHHARBOR.17b3 adds RepoDossier follow-up release notes in `docs/repodossier-follow-up-release-notes.md` and `tests/test_repodossier_follow_up_release_notes.py`.
