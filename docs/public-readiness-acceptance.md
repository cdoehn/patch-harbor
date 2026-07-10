# PATCHHARBOR.15c3 – Public readiness acceptance

This document records the PatchHarbor public-readiness acceptance state at the end of Milestone 15.

It is target-only. It does not edit RepoDossier, source wrappers, aliases, shell rc files, `c`, or `r`.

## Acceptance summary

PatchHarbor is public-readiness accepted for the next migration phase when all of these statements are true:

1. public runner documentation exists in `docs/runner.md`
2. public compatibility documentation exists in `docs/compatibility.md`
3. public CLI documentation exists in `docs/cli.md`
4. public API inventory exists in `docs/public-api-inventory.md`
5. public API stability tests exist in `tests/test_public_api_stability.py`
6. historical migration documents are marked with `PATCHHARBOR.15b4 historical-migration-doc`
7. public docs inventory exists in `docs/public-docs-inventory.md`
8. migration artifact inventory exists in `docs/migration-artifact-inventory.md`
9. packaging acceptance remains covered by `tests/test_packaging_acceptance.py`
10. target-only public readiness patches leave the RepoDossier source repository unchanged

## Public documentation set

Current public-facing PatchHarbor documentation is:

| Path | Role |
| --- | --- |
| `README.md` | repository entry point |
| `docs/bootstrap.md` | bootstrap and setup notes |
| `docs/runner.md` | public runner behavior |
| `docs/compatibility.md` | public compatibility behavior |
| `docs/cli.md` | public CLI command contract |
| `docs/public-api-inventory.md` | public CLI and Python API surface |
| `docs/public-readiness-acceptance.md` | final Milestone 15 public-readiness acceptance |

Supporting inventories:

| Path | Role |
| --- | --- |
| `docs/public-docs-inventory.md` | public documentation inventory |
| `docs/migration-artifact-inventory.md` | migration artifact inventory |

## Public API acceptance

Public API acceptance is based on:

| Area | Acceptance evidence |
| --- | --- |
| command-line commands | `docs/cli.md` and `tests/test_cli_docs_consolidation.py` |
| Python public API inventory | `docs/public-api-inventory.md` and `tests/test_public_api_inventory.py` |
| Python public API stability | `tests/test_public_api_stability.py` |
| runner behavior | `docs/runner.md` and `tests/test_runner_docs_consolidation.py` |
| compatibility behavior | `docs/compatibility.md` and `tests/test_compatibility_docs_consolidation.py` |
| historical migration boundary | `tests/test_historical_migration_docs.py` |
| packaging/install behavior | `tests/test_packaging_acceptance.py` |

## Public CLI commands

The public CLI command surface remains:

| Command | Status |
| --- | --- |
| `patchharbor --help` | public |
| `patchharbor --version` | public |
| `patchharbor doctor --repo` | public |
| `patchharbor lint-script` | public |
| `patchharbor run-script` | public |
| `patchharbor audit-public` | public |
| `patchharbor check-env` | public |

## Historical migration boundary

Historical migration documents are retained for traceability, but are not the current public command contract.

The current public contracts are:

- `docs/runner.md`
- `docs/compatibility.md`
- `docs/cli.md`
- `docs/public-api-inventory.md`

Migration history remains available through the historical migration marker:

    PATCHHARBOR.15b4 historical-migration-doc

No migration artifact is deleted by PATCHHARBOR.15c3.

## Acceptance test matrix

The public-readiness acceptance matrix is:

| Test module | Acceptance area |
| --- | --- |
| `tests/test_public_readiness_acceptance.py` | final public-readiness acceptance |
| `tests/test_public_api_stability.py` | public API stability |
| `tests/test_public_api_inventory.py` | public API inventory |
| `tests/test_cli_docs_consolidation.py` | CLI docs consolidation |
| `tests/test_compatibility_docs_consolidation.py` | compatibility docs consolidation |
| `tests/test_runner_docs_consolidation.py` | runner docs consolidation |
| `tests/test_historical_migration_docs.py` | historical migration boundary |
| `tests/test_public_docs_inventory.py` | public docs inventory |
| `tests/test_migration_artifact_inventory.py` | migration artifact inventory |
| `tests/test_packaging_acceptance.py` | packaging acceptance |

## Handoff to Milestone 16

PATCHHARBOR.15c3 closes the public-readiness documentation and API stabilization series.

The next milestone begins dual-repository end-to-end acceptance:

    PATCHHARBOR.16a1 – Dual Repo Discovery Smoke

Milestone 16 should prove that PatchHarbor and RepoDossier work together from fresh dual-repo checkouts and that target-only/source-only boundaries remain correct.

## Non-goals

PATCHHARBOR.15c3 does not:

- change runtime code
- change CLI behavior
- change runner behavior
- change compatibility behavior
- change package metadata
- edit RepoDossier
- edit source wrappers
- edit source aliases
- delete migration artifacts
- change release versioning

Release and branch hygiene are handled by later milestones.


## PATCHHARBOR.16a1 applied

- Dual repo discovery smoke now lives in `docs/dual-repo-discovery-smoke.md` and `tests/test_dual_repo_discovery_smoke.py`; it starts Milestone 16 E2E validation without mutating RepoDossier.


## PATCHHARBOR.16a2 applied

- Dual repo patch-runner smoke now lives in `docs/dual-repo-patch-runner-smoke.md` and `tests/test_dual_repo_patch_runner_smoke.py`; it validates PatchHarbor runner execution in a temporary repository while RepoDossier remains unchanged.
