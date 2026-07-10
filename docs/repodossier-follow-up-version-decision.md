# PATCHHARBOR.17a2 – RepoDossier follow-up version decision

This document records the RepoDossier follow-up release version decision for Milestone 17.

It is target-only. It reads the current RepoDossier package version from the source repository `pyproject.toml` and does not edit source package metadata.

## Plan contract

| Field | Value |
| --- | --- |
| Patch id | PATCHHARBOR.17a2 |
| Plan title | RepoDossier Follow-up Version Decision |
| Commit | Document RepoDossier follow-up release version |
| Operative plan | `planning/milestones_migration.md` |

## Decision

RepoDossier keeps the current source package version for the follow-up release decision:

| Item | Decision |
| --- | --- |
| Source package name | `repodossier` |
| Current source package version | `1.0.0` |
| PatchHarbor release candidate version | `0.1.0` |
| Follow-up release decision | use `1.0.0` as the RepoDossier follow-up release candidate unless a later RepoDossier-specific plan changes metadata |
| Source metadata change in this patch | none |
| Target package metadata change in this patch | none |

This patch intentionally does not change RepoDossier `pyproject.toml` or PatchHarbor `pyproject.toml`.

The purpose of PATCHHARBOR.17a2 is to record the RepoDossier follow-up version decision before release notes and release build smoke work begin.

## Rationale

Milestone 16 closed the migration acceptance chain. PATCHHARBOR.17a1 documented the PatchHarbor release version. PATCHHARBOR.17a2 records the corresponding RepoDossier follow-up version decision.

RepoDossier remains the source repository for domain-specific wrappers and follow-up behavior. PatchHarbor remains the target repository for the generic patch runner.

A later patch may change RepoDossier version metadata only if the operative plan explicitly asks for source-side version metadata changes. PATCHHARBOR.17a2 only documents the decision.

## Required follow-up

The next operative plan step is:

    PATCHHARBOR.17b1 – PatchHarbor Release Notes

PATCHHARBOR.17b1 should add PatchHarbor release notes for the migration-stabilization release candidate.

## Non-goals

PATCHHARBOR.17a2 does not:

- change RepoDossier `pyproject.toml`
- change PatchHarbor `pyproject.toml`
- change PatchHarbor runtime code
- change RepoDossier runtime code
- change source wrappers
- change aliases
- edit shell rc files
- publish a release
- create release notes
- build a release artifact
- clean local or remote branches


## PATCHHARBOR.17b1 applied

- PATCHHARBOR.17b1 adds PatchHarbor release notes in `docs/patchharbor-release-notes.md` and `tests/test_patchharbor_release_notes.py`; RepoDossier follow-up metadata remains unchanged.
