# PATCHHARBOR.17b2 – PatchHarbor release build smoke

This document records the PatchHarbor release build smoke for the migration-stabilization release candidate.

It is target-only. It builds a local wheel artifact in a temporary directory and inspects the wheel metadata without publishing, tagging, or changing version metadata.

## Plan contract

| Field | Value |
| --- | --- |
| Patch id | PATCHHARBOR.17b2 |
| Plan title | PatchHarbor Release Build Smoke |
| Commit | Add PatchHarbor release build smoke |
| Package | `patchharbor` |
| Version | `0.1.0` |
| Related RepoDossier version | `1.0.0` |

## Smoke behavior

The smoke uses the current Python interpreter and runs a local wheel build with:

    python -m pip wheel --no-deps --no-build-isolation --wheel-dir TEMP_DIR TARGET_REPO

The smoke then inspects the wheel as a zip archive and verifies:

- exactly one wheel is produced
- wheel filename starts with `patchharbor-`
- wheel metadata name is `patchharbor`
- wheel metadata version equals `0.1.0`
- wheel contains `patchharbor/cli.py`
- wheel contains `patchharbor/__main__.py`
- wheel entry points expose `patchharbor = patchharbor.cli:main`
- the build output stays in a temporary directory

## Release boundary

PATCHHARBOR.17b2 is a build smoke only.

It does not:

- publish a release
- upload to PyPI
- create or push git tags
- change `pyproject.toml`
- change version metadata
- edit RepoDossier source files
- edit shell aliases
- edit shell rc files
- clean local branches
- clean remote branches

## Failure handling

If the build smoke fails:

1. do not publish anything
2. inspect the build output and test log
3. fix the build smoke or packaging metadata in the next patch
4. keep the same commit contract unless the operative plan changes
5. verify RepoDossier source status remains unchanged

## Relationship to release notes

PATCHHARBOR.17b1 added release notes.

PATCHHARBOR.17b2 verifies that the package described by those release notes can produce an inspectable wheel artifact.

## Next step

The next operative plan step is:

    PATCHHARBOR.17b3 – RepoDossier Follow-up Release Notes


## PATCHHARBOR.17b3 applied

- PATCHHARBOR.17b3 adds RepoDossier follow-up release notes in `docs/repodossier-follow-up-release-notes.md` and `tests/test_repodossier_follow_up_release_notes.py`; PatchHarbor build-smoke evidence remains unchanged.
