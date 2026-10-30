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
| SRI-01 `docs(spec): define public snapshot and guarded apply contracts` | Targeted norm updates, this plan, behavior matrix; no product claims | Prepared; selected parallel gate passed; Apply pending |
| SRI-02 `feat(api): expose verified result snapshots` | Reuse one capture; immutable public layers, strict text/binary reconstruction, budgets/errors/capability; real fixtures and independent oracle | Locally checked: 471 selected tests; Apply pending |
| SRI-03 `feat(api): bind host admission to the applied package and target` | Explicit SHA/target, full immutable admission inside existing lock/core, failures and exchange/replay regressions | Locally checked; full selected report outside source; Apply pending |
| SRI-04 `test(integration): verify and document the delivered transport contracts` | Built 1.6.0 PYZ public-only roundtrip, frozen1.4, version/docs/example and delivery record | Implemented; final selected gate/build and Apply pending |

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

## SRI-02 implementation record

The shared reader now exposes request-local captured payloads internally; existing
reference consumers keep their prior contract. The public reader reconstructs
text and both binary block forms in memory, with strict paths/IDs/ranges/budgets.
The producer pins diff prefixes/full paths. No second Result validator or Git
consumer is introduced. Preliminary selected run `snapshot-reviewed` passed
234 tests on CPython3.14.4/Linux; the final SRI-02 source has its own selected
parallel gate and includes additional frozen1.4 tests. Apply and native CI remain
unconfirmed. Capability version1 announces snapshots; guarded Apply remains None
until SRI-03. Preserved 1.5.0 acceptance is unaffected.

## SRI-03 implementation record

The existing Apply application now accepts an internal admission policy through
a narrow public `apply_guarded` facade. Static inspection is projected from the
already captured package. Target checks and one mandatory callback run within
the existing lock and private-input lifetime; existing mutation/replay/Result
logic remains responsible for execution. 157 preliminary selected tests passed
on CPython3.14.4/Linux; the final stage has its own report.

An observed schema constraint required one explicit clarification of §42.4:
Result3 represents INTERRUPTED only for an actually started entrypoint. Therefore
a callback KeyboardInterrupt/SystemExit is a pre-execution admission rejection
(SOURCE_ERROR), with no false execution flag. A separate actual child-interrupt
test preserves exit130 and the ordinary execution/Result facts. The independent
Exchange identity recheck still refuses a package swapped during admission;
explicit external files use their captured approved bytes. No fallback bypass
was added. Both facts are covered by real Apply tests.

## SRI-04 delivery state

Source version1.6.0 adds a public-only executable transport example and a fresh
`-I -S -B` process proof against both the real built wheel resources and Core-PYZ.
The process has no Git/shell PATH, rejects process/network use and checkout reads,
checks every independently expected layer and verifies snapshot-derived package
contents through public pack/inspect/validate. Frozen1.4 inputs are byte-pinned.

The final source inventory and each selected Development report are bound in
Bundle071's external delivery record. Each of the four genuine states receives
its own full parallel Apply gate and commit later. No actual SRI commit or native
CI result is claimed by these prepared source documents. Full review details and
remaining acceptance are in [delivery.md](delivery.md).
