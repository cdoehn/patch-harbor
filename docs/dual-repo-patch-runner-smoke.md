# PATCHHARBOR.16a2 – Dual repo patch runner smoke

This document records the Milestone 16 dual-repository PatchHarbor runner smoke.

The smoke is target-only. It reads the sibling RepoDossier checkout, runs PatchHarbor against a temporary test repository, and does not edit RepoDossier source files, aliases, shell rc files, `c`, or `r`.

## Purpose

PATCHHARBOR.16a1 proved dual-repo discovery.

PATCHHARBOR.16a2 proves that PatchHarbor runner behavior can execute a small patch script while the dual-repo source/target boundary remains intact.

This smoke deliberately uses a temporary git repository for execution. It does not run the RepoDossier source-side `c` runner.

## Smoke contract

The smoke verifies:

1. PatchHarbor target checkout is discoverable.
2. RepoDossier source checkout is discoverable.
3. PatchHarbor `run-script` can execute a metadata-bearing patch script.
4. PatchHarbor `run-script --no-execute` performs preflight without executing the script.
5. Execution writes only to a temporary test repository.
6. RepoDossier source status is unchanged before and after the smoke.
7. PatchHarbor public-readiness and API documents remain linked.
8. No contributor-specific local path is stored in docs or tests.

## Patch script used by the smoke

The test creates a temporary patch script with `patchharbor-meta` records for:

- patch metadata
- roadmap progress metadata
- milestone progress metadata
- display metadata

The script writes a marker file only when executed. The `--no-execute` smoke confirms that preflight can pass without writing the marker.

## Commands exercised

The smoke exercises these target commands:

    python -m patchharbor run-script ./smoke_patch.sh --workdir ./temp_repo --env PATCHHARBOR_SMOKE_FILE=./marker.txt
    python -m patchharbor run-script ./smoke_patch.sh --no-execute --workdir ./temp_repo --env PATCHHARBOR_SMOKE_FILE=./marker.txt

The tests run with `PYTHONPATH` pointing at the target `src` directory.

## Boundary contract

The smoke must not:

- call RepoDossier `c`
- call RepoDossier `r`
- edit RepoDossier source files
- edit source aliases
- edit shell rc files
- edit PatchHarbor runtime code
- use contributor-specific local paths
- require network access

## Handoff to next smoke

PATCHHARBOR.16a3 should add the dual-repo source-wrapper smoke.

That later smoke can validate source wrapper bridge behavior, but PATCHHARBOR.16a2 only validates PatchHarbor runner behavior with dual-repo discovery and a temporary execution repository.


## PATCHHARBOR.16a3 applied

- Dual repo source-wrapper smoke now lives in `docs/dual-repo-source-wrapper-smoke.md` and `tests/test_dual_repo_source_wrapper_smoke.py`; it checks source wrappers without executing `c` or `r`.


## PATCHHARBOR.16b1 applied

- Dual repo boundary acceptance now lives in `docs/dual-repo-boundary-acceptance.md` and `tests/test_dual_repo_boundary_acceptance.py`.
