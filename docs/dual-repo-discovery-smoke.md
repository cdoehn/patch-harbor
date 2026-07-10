# PATCHHARBOR.16a1 – Dual repo discovery smoke

This document records the first Milestone 16 dual-repository smoke test.

The smoke is target-only. It reads the sibling RepoDossier checkout and the PatchHarbor checkout, but it does not edit RepoDossier source files, aliases, shell rc files, `c`, or `r`.

## Purpose

Milestone 15 made PatchHarbor public-readiness accepted.

Milestone 16 starts end-to-end dual-repository acceptance.

PATCHHARBOR.16a1 proves that a PatchHarbor target checkout can discover and validate the sibling RepoDossier source checkout without mutating it.

## Discovery contract

The smoke supports these discovery inputs:

| Input | Purpose |
| --- | --- |
| `PATCHHARBOR_SOURCE_REPO` | explicit RepoDossier source checkout |
| `PATCHHARBOR_TARGET_REPO` | explicit PatchHarbor target checkout |
| sibling `repo_dossier` directory | default source discovery from the target parent directory |
| current target checkout | default PatchHarbor discovery |

The smoke verifies that the source repo is RepoDossier by checking:

- `pyproject.toml` package name
- `src/repodossier`
- `scripts/dev/run_latest_download_patch.sh`
- `scripts/dev/r.sh`
- `planning/milestones_migration.md`

The smoke verifies that the target repo is PatchHarbor by checking:

- `pyproject.toml` package name
- `src/patchharbor`
- `docs/public-readiness-acceptance.md`
- `docs/public-api-inventory.md`
- `docs/cli.md`
- `docs/runner.md`
- `docs/compatibility.md`

## Boundary contract

The smoke is read-only.

It must not:

- edit RepoDossier files
- edit PatchHarbor runtime code
- rewrite aliases
- rewrite shell rc files
- run downloaded patches
- invoke the source `c` runner
- invoke the source `r` runner
- require contributor-specific local paths

## Acceptance evidence

The smoke is accepted when:

1. `docs/dual-repo-discovery-smoke.md` exists.
2. `tests/test_dual_repo_discovery_smoke.py` exists.
3. the source checkout is identified as RepoDossier.
4. the target checkout is identified as PatchHarbor.
5. the source milestone plan contains PATCHHARBOR.16a1.
6. the target public-readiness acceptance contains PATCHHARBOR.15c3.
7. the target public API inventory contains PATCHHARBOR.15c2.
8. the target CLI, runner, and compatibility docs are present.
9. the smoke does not store private/local values.
10. target-only patches leave the source repository unchanged.

## Handoff to next smoke

PATCHHARBOR.16a2 should add the dual-repo patch-runner smoke.

That later smoke can exercise runner behavior more deeply, but PATCHHARBOR.16a1 only proves discovery and public-readiness boundary checks.


## PATCHHARBOR.16a2 applied

- Dual repo patch-runner smoke now lives in `docs/dual-repo-patch-runner-smoke.md` and `tests/test_dual_repo_patch_runner_smoke.py`.


## PATCHHARBOR.16a3 applied

- Dual repo source-wrapper smoke now lives in `docs/dual-repo-source-wrapper-smoke.md` and `tests/test_dual_repo_source_wrapper_smoke.py`.
