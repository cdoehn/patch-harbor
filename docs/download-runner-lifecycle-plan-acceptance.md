# PATCHHARBOR.10c4 – Download Runner Lifecycle Plan Acceptance

This document accepts the target-side download runner selection and lifecycle planning API for PATCHHARBOR.10c.

The 10c phase introduced target-side planning primitives only. It did not replace the RepoDossier source runner and did not switch `c`.

## Accepted target files

| Step | Area | Path |
| --- | --- | --- |
| PATCHHARBOR.10c1 | API inventory | `docs/download-runner-api-inventory.md` |
| PATCHHARBOR.10c2 | artifact selection API | `src/patchharbor/download_selection.py` |
| PATCHHARBOR.10c2 | artifact selection tests | `tests/test_download_selection.py` |
| PATCHHARBOR.10c3 | lifecycle plan API | `src/patchharbor/download_plan.py` |
| PATCHHARBOR.10c3 | lifecycle plan tests | `tests/test_download_plan.py` |
| PATCHHARBOR.10c4 | acceptance tests | `tests/test_download_plan_acceptance.py` |

## Accepted API contract

The accepted API contract includes:

- `select_download_artifact(...)` selects a script or archive artifact without executing it.
- explicit artifact paths take precedence over newest-download selection.
- archive selection records the embedded patch script name.
- `create_lifecycle_plan(...)` builds a non-executing lifecycle plan from selection.
- script plans execute the selected script directly.
- archive plans execute the embedded script after extraction.
- archive plans keep the original archive as the lifecycle input artifact.
- success destinations point into `done`.
- failure destinations point into `failed`.
- log files stay in the download directory.
- the applied ledger path is `.applied_patch_hashes.tsv` inside `done`.
- phase order preserves the current parity sequence.
- `DownloadLifecyclePlan.to_mapping()` exposes the nested selection mapping from `DownloadArtifactSelection.to_mapping()`.
- cleanup paths are planned, but cleanup is not executed by the planning API.

## Explicit non-goals

PATCHHARBOR.10c does not:

- execute patchscripts
- validate metadata
- perform repeat checks
- perform freshness checks
- run Bash syntax checks
- move files to `done` or `failed`
- write the applied ledger
- change aliases
- switch `c`
- replace the RepoDossier source runner
- mutate the RepoDossier source repository

## Readiness for PATCHHARBOR.10d

PATCHHARBOR.10d may start source-side wrapper planning after this acceptance is green.

The 10d series must treat the 10b source parity tests and the 10c target API tests as safety rails. Any implementation switch must keep the old user-facing entry point stable until parity and rollback are proven.

## Acceptance checks

This phase is accepted when the target repository passes:

    PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_*.py'
    PYTHONPATH=src python3 -m patchharbor doctor --repo "$TARGET_REPO"

Manual review should confirm that PATCHHARBOR.10c added planning APIs only and did not change execution behavior.
