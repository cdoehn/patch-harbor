# PatchHarbor 1.6.0 – Public integration contracts

Plan ID: **SRI-1.6.0** · 30 October 2026 · target version **1.6.0**.
Normative set: [main specification](../../spec/SPECIFICATION.md),
[PYZ/PACK](../../spec/SPECIFICATION_EXTENSION_PYZ_PACK.md),
[CPython](../../spec/SPECIFICATION_EXTENSION_CPYTHON_310_311.md).
This is a new feature task, separate from the historical 1.5.0 refactoring.

## Verified baseline and gaps

Result `patchharbor-apply_Result_185758_1030_64091f.zip`, SHA-256
`63573accec1ba6f1b917d0494210ff5d32617a9cce38a0912f69d13f0ccf905e`, proves
actual RF-13 Apply at `312e8a3c003c0f9421587b92941ecea7917b5d3f` on dev,
clean, pushed, 3281 passed / 15 skips in the full parallel gate. All 15 planned
1.5.0 implementation commits are confirmed. Manual final-commit CI, applicable
CIFS evidence/mapping and final release review remain open. Historical records
are preserved; this plan does not certify or release 1.5.0.

Binding: repo_id `e7a93d72-62dc-4759-97e8-6bf6cdf10e90`, base as above,
state `7c9d2a24e397e0e5`, algorithm `patchharbor-state-v1`.
Development uses a verified reconstruction of this Result; its older dirty Git
checkout is preserved. Commits occur exclusively through the Apply entrypoint.

Existing result_reader validates Result 3/runtime/inventories and owns a stable
capture. Its public consumers only expose reference facts; none reconstruct
staged/unstaged layers. Existing producer emits full-index binary Git diffs with
renames disabled. Existing tests reconstruct with Git, which is unsuitable for
the requested Python-only consumer. Existing immutable package capture, static
inspection and locked Apply core are reusable. Public apply rejects an explicit
patch together with repository; it has no binding host admission callback.
These are confirmed gaps, not replacements for the existing reader or core.

## Genuine stages and gates

| Stage / intended commit | Scope and acceptance | Status |
| --- | --- | --- |
| SRI-01 `docs(spec): define public snapshot and guarded apply contracts` | Targeted norm updates, this plan, behavior matrix; no product claims | Prepared; own selected gate and Apply pending |
| SRI-02 `feat(api): expose verified result snapshots` | Reuse one capture; immutable public layers, strict text/binary reconstruction, budgets/errors/capability; real fixtures and independent oracle | Specified |
| SRI-03 `feat(api): bind host admission to the applied package and target` | Explicit SHA/target, full immutable admission inside existing lock/core, failures and exchange/replay regressions | Specified |
| SRI-04 `test(integration): verify and document the delivered transport contracts` | Built 1.6.0 PYZ public-only roundtrip, frozen1.4, version/docs/example and delivery record | Specified |

Target is one bundle with four sequential states, no extra artificial W/R/C
stages. Only a demonstrated blocker justifies splitting into two coherent parts.
Each prepared state has an independent source-bound selected parallel Development
report. Apply materializes that state, runs `python tools/run_tests.py --suite
all` with positive workers and its own report, verifies the complete evidence,
then creates its commit. No serial gate, no redundant final full test. A failure
stops with completed commits retained. Existing authorized handoff policy allows
one ordinary final push only after all commit gates; no direct Development push,
release, tag, CI dispatch, installation or watcher/service change.

## Readiness and completion

Snapshot availability for SpecRoad 15.m.R and guarded host adoption are separate
acceptance items. Normal API + actual isolated built PYZ, raw content oracle,
malformed input/security and frozen compatibility are mandatory local checks.
The matrix names evidence and unresolved platform checks. Full suite is only
Apply; manual native CI only Christian. A returned RunReport is evaluated for
actual execution and publication independently. A valid failed/dirty/dry-run
Result is not upgraded to successful Apply by reading it.

No SpecRoad code/configuration is changed. Its independent runtime-hash adoption,
approved entrypoint/closure policy and own end-to-end roundtrip remain external.
This plan ends after confirmed four stages and required acceptance; no new
follow-up plan is silently created.
