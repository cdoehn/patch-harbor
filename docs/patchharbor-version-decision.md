# PATCHHARBOR.17a1 – PatchHarbor version decision

This document records the PatchHarbor release version decision for Milestone 17.

It is target-only. It documents the current PatchHarbor package version from `pyproject.toml` and does not edit package metadata.

## Plan contract

| Field | Value |
| --- | --- |
| Patch id | PATCHHARBOR.17a1 |
| Plan title | PatchHarbor Version Decision |
| Commit | Document PatchHarbor release version |
| Operative plan | `planning/milestones_migration.md` |

## Decision

PatchHarbor keeps the current package version for the migration release decision:

| Item | Decision |
| --- | --- |
| Package name | `patchharbor` |
| Current package version | `0.1.0` |
| Release decision | use `0.1.0` for the PatchHarbor migration-stabilization release candidate |
| Metadata change in this patch | none |

This patch intentionally does not change `pyproject.toml`.

The purpose of PATCHHARBOR.17a1 is to record the version decision before release notes, release build smoke, and branch hygiene work begin.

## Rationale

The current version already belongs to PatchHarbor package metadata.

Milestone 16 closed the dual-repository migration acceptance chain. Milestone 17 now prepares release and branch hygiene. The version decision should be explicit before release notes and release build smoke are added.

A later patch may change version metadata only if the operative plan explicitly asks for it. PATCHHARBOR.17a1 only documents the decision.

## Required follow-up

The next operative plan step is:

    PATCHHARBOR.17a2 – RepoDossier Follow-up Version Decision

PATCHHARBOR.17a2 should decide what, if anything, RepoDossier needs as a follow-up version after PatchHarbor migration.

## Non-goals

PATCHHARBOR.17a1 does not:

- change `pyproject.toml`
- change PatchHarbor runtime code
- change RepoDossier runtime code
- change source wrappers
- change aliases
- edit shell rc files
- publish a release
- create release notes
- build a release artifact
- clean local or remote branches


## PATCHHARBOR.17a2 applied

- PATCHHARBOR.17a2 documents the RepoDossier follow-up release version decision in `docs/repodossier-follow-up-version-decision.md` and `tests/test_repodossier_follow_up_version_decision.py`; source metadata is unchanged.


## PATCHHARBOR.17b1 applied

- PATCHHARBOR.17b1 adds PatchHarbor release notes in `docs/patchharbor-release-notes.md` and `tests/test_patchharbor_release_notes.py`; package metadata remains unchanged.
