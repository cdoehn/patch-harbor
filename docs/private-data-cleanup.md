# Private data cleanup

This document records PATCHHARBOR.PRIVACY1 for PatchHarbor.

The cleanup removes old contributor-specific examples and private local fragments from tracked text files.

## Scope

PATCHHARBOR.PRIVACY1 replaces old private/person-specific examples with neutral examples.

The cleanup covers:

- local home path examples
- old user-name fragments
- old email fragments
- old workstation-name fragments
- old local project-directory examples
- old local town-name examples

## Boundary

This cleanup does not:

- change package version metadata
- change runtime behavior
- delete branches
- push to remotes
- fetch from remotes
- create tags
- publish releases
- edit shell rc files

## Regression

The regression test is:

    tests/test_private_data_cleanup.py

It scans tracked UTF-8 text files and fails if the old private patterns reappear.
