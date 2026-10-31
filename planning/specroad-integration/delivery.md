# 1.6.0 integration delivery / Bundle071

This file describes the prepared delivery, not an executed Apply or a release.
The confirmed baseline is 1.5.0 commit
`312e8a3c003c0f9421587b92941ecea7917b5d3f` from Result SHA
`63573accec1ba6f1b917d0494210ff5d32617a9cce38a0912f69d13f0ccf905e`.
Four SRI stages are prepared on that exact repository/state binding. Actual new
commit SHAs can only be confirmed from the watcher's subsequent Result. The old
1.5.0 external release acceptance remains open and is not retroactively changed.

## Delivered contracts

`api.integration_capabilities()` contract 1 advertises snapshot 1 and guarded Apply 1.
`api.read_result_snapshot(result, *, expected_sha256=None, observer=None)`
returns immutable `ResultSnapshot`/`SnapshotLayer`/`SnapshotFile`/`SnapshotRuntime`.
`api.apply_guarded(patch, *, expected_sha256, expected_repository, admission,
output_directory=None, timeout=DEFAULT_TIMEOUT_SECONDS, output=None, observer=None)`
returns the unchanged RunReport and supplies immutable `PatchAdmission` to the
trusted callback. Public details, error codes and limitations: [Python API](../../docs/python-api.md).

The snapshot prerequisite for SpecRoad 15.m.R and guarded host adoption are
implemented and locally testable independently. Full acceptance requires the
corresponding actual Apply and platform evidence. No SpecRoad files were changed
and no SpecRoad end-to-end roundtrip is claimed. The [public-only example](../../docs/examples/snapshot_transport.py)
constructs transport contents from the verified snapshot and compares the pack
reference digest before exposing a deliverable. Host policy remains external.

## Artifacts and evidence

The final local delivery report is
`exchange/reports/patchharbor-integration-071-delivery.json`. It records selected
source-bound parallel reports for all four stages, exact built wheel/sdist/PYZ
paths, full SHA-256, sizes, source inventory, profile
`patchharbor-core-no-watcher-v1`, contract versions, interpreter and platform.
The immutable sources are preserved in the Development build workspace. Hashes
are recorded externally to avoid embedding an artifact's hash in its own inputs.
The Core-PYZ contains no watcher; ordinary wheel/sdist retain it. Nothing is
installed globally and no service or local configuration is changed.

Snapshot fixtures are reproducible through `tests/snapshot_support.py`; original
1.4.0 fixtures and pinned provenance remain under `tests/fixtures/compatibility_140`.
Integrity, content identities and exact changes are checked; authenticity,
historical Git commit/tree provenance and independent dirty-fingerprint
recomputation are not asserted from incomplete Result 3 data.

## Open acceptance

- Four actual Apply commits and their own complete parallel test evidence.
- Christian-started exact-commit native CI on the supported Linux/Windows and
  CPython 3.10/3.11/3.12/3.14 lanes, including existing PowerShell/Docker proofs.
- Controlled SpecRoad runtime-hash adoption and its own integration/approval tests.
- Separate release review, optional tag/publication and explicit installation.

Local Development tests are selected tests, never represented as a full suite.
The unchanged manual CI matrix collects the new e2e/packaging tests; no automatic
CI or additional serial test gate is introduced.
