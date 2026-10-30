# SRI behavior and evidence matrix

All rows are **specified, not yet confirmed** at SRI-01. Tests assert behavior,
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
