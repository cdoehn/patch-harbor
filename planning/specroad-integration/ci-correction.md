# CI-072: corrections after the first 1.6.0 integration CI

The manually dispatched [run 41220319490](https://github.com/cdoehn/patch-harbor/actions/runs/41220319490)
tested main at `d6c3450da8f3bc6731911141acfec62449e06a96`: six jobs passed and
six failed. That merge has the same tracked tree as SRI-04
`29c9cfdc095517e7c4cfd4a4c0588cd90655f0b9`; dev currently has the same merge
commit. The failures are not changes introduced by the merge.

## Causes and bounded corrections

1. Windows core lanes on CPython 3.10, 3.11 and 3.12 each failed 42 frozen
   compatibility checks. Git's CRLF checkout changed `provenance.json`; the
   capture program is also byte-pinned and would fail the next check. Targeted
   LF attributes preserve both files. The historical ZIPs, expected digests
   and generator stay unchanged. A real `core.autocrlf=true` checkout test
   compares their bytes and verifies that an ordinary control file gets CRLF.
2. Ubuntu 24.04/26.04 installed-distribution lanes exposed a missing
   `RuntimeLimitError` mapping in snapshot capture. The inner PYZ limit was
   enforced but surfaced as `invalid_result` instead of `resource_limit`.
   Typed cause classification now preserves the documented category. Separate
   tests cover outer limits, the exact embedded-content boundary using an
   actual built producer, and reconstruction exhaustion after complete archive
   verification, with both embedded and unavailable runtimes. No limit rises.
3. Windows PowerShell 7 / CPython 3.12 exceeded the neighboring-Exchange
   test's 20-second completion deadline with no watcher exception recorded.
   The evidence supports a runner-time allowance correction; it does not prove
   a scheduler defect. Use the existing Windows real-Apply budget of 120 seconds,
   retain 20 seconds on POSIX, and report worker starts/completions, exit codes,
   writer progress and watcher logs on timeout. Real Apply success, Exchange
   isolation and the five-second quiet period remain mandatory. No product
   watcher change, retry or skip is introduced.

## Evidence and handoff

Before the production corrections, both new focused regression checks failed
for the diagnosed reasons: CRLF provenance bytes and the incorrect error code.
Development uses selected parallel tests, including the affected compatibility,
snapshot, runtime/transport and native event-loop behavior. Source-bound reports,
collection replacement mapping and entrypoint fault checks are external handoff
evidence; this document does not preclaim their final results.

Bundle 072 proposes one correction commit on dev after its complete parallel
Apply gate. It binds to the fresh clean Result
`patchharbor-apply_Result_183139_1031_89ef56.zip` (SHA-256
`45f080b79aefbeb873dba6502c0cec1b75343d2d3a0cc9d269855bdbb9da6151`),
base `d6c3450da8f3bc6731911141acfec62449e06a96`. That Result is a capture,
not proof of applying this correction. The watcher performs the actual Apply;
the entrypoint commits only after its full parallel gate and pushes dev once.

Version remains 1.6.0. No CI dispatch, main update, tag, release or installation
is performed by this correction. Christian must manually run the native CI
matrix on the resulting dev commit. Windows timing and installed-distribution
acceptance remain open until those results are reviewed, as does the independent
SpecRoad adoption check. Historical 1.5.0 acceptance is unaffected.
