# SRI behavior and evidence matrix

The following rows are implemented and covered by selected local tests as of
SRI-04; actual Apply, final built-artifact evidence and external acceptance are
recorded separately in the delivery record. Tests assert behavior,
security and structured values, not documentation wording or console styling.

| Requirement | Independent check | Planned evidence |
| --- | --- | --- |
| SRI-SNAPSHOT capture/status | Producer Results; optional SHA; one read, replacement and failure/dirty/dry-run facts | snapshot API tests |
| SRI-DELTA layers | Real Git producer, independent HEAD/index/worktree bytes; additions/deletions/mode/text/no-LF/non-UTF8 contents, Unicode/spaces, both object formats | snapshot reconstruction tests |
| SRI-DELTA binary | Real literal/delta, forward/reverse IDs and size, corrupt/truncated program, bounded decompression | binary reconstruction tests |
| SRI-TRUST | Invalid ZIP, duplicate/link/special/traversal, shape/case collisions, invalid hunk/object IDs, total/per-file budgets, runtime tampering without execution | snapshot negative tests + existing reader/ZIP/security contracts |
| SRI-ADMISSION | Actual registered fixture apply, exact package SHA/target/contents under lock, reject/exception/missing approval, swapped package/target, occupied staging/extra payload/changed script | guarded Apply tests |
| SRI-ADMISSION lifecycle | Existing actual failure/interruption/publication failure and replay, unchanged ordinary API and watcher | guarded Apply + existing Apply/exchange/watcher tests |
| SRI-RUNTIME | Built wheel/sdist/PYZ; isolated Python-only public snapshot → pack → validate; no source checkout/Git/shell/network/third parties; frozen original1.4 | artifact integration test + compatibility fixtures |
| Platform contract | Existing manual Linux/Windows/PowerShell/Docker matrix, CPython3.10/3.11/3.12/3.14 | Open until Christian supplies exact-commit CI evidence |

Every stage records its selected tests and source-bound report outside the source
tree. Apply supplies a separate full parallel report before each commit. The
new tests do not replace or loosen existing assertions. Source/fixture review
separates the new reconstructed snapshot from unchanged declared repo/commit/
dirty-fingerprint identity and from unauthenticated runtime provenance.

Final concrete selected-test mapping:

- SRI-SNAPSHOT/DELTA/TRUST: `test_result_snapshot.py`,
  `test_snapshot_security.py`, `test_snapshot_binary.py`, existing reader,
  reference, producer, archive and compatibility tests. Real cases are produced
  by `tests/snapshot_support.py`; Git is used only by that host-side oracle.
- SRI-ADMISSION: `test_guarded_apply.py` plus existing Apply, mutation, API,
  Exchange/recovery and watcher-worker tests. Covers actual child interruption
  and publication failure separately from pre-execution callback cancellation.
- SRI-RUNTIME: `test_snapshot_transport.py` exercises the actual public-only
  example from trusted build artifacts; existing packaging and frozen1.4 tests
  remain. No old assertion is disabled and no CI job is started.

These new marked e2e/packaging tests are automatically collected by the existing
manual full-suite Linux/Windows/CPython lanes. The CI workflow's triggers, lanes
and previous mandatory proofs are unchanged. Native results are still required.
