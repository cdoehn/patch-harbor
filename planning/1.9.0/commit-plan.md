# PatchHarbor 1.9.0 release

Explicit user request on 10 November 2026: create and push the 1.9.0 tag,
use the existing GitHub scripts/workflows to publish the PYZ and intended
release artifacts, then merge dev into main. The user permits reordering.
This request authorizes the necessary workflow dispatches, tag, publication
and normal branch integration. Earlier CI/tag restrictions for development
tasks do not prohibit these explicitly requested release actions.

Normative contracts: `spec/SPECIFICATION.md` with its PYZ/PACK and CPython
supplements, `planning/viewer/specification.md`, `docs/release-runtime.md`.
Existing format, capability and compatibility contracts remain unchanged.

## Confirmed baseline

- Dev/Apply: `2c49be61d12340056b59be590f6fbf5e0a5f45fd`, Bundle 082, clean.
- Full parallel Apply: 3669 passed, 15 skipped; actual successful Result.
- Native baseline CI: run 42800107893, completed successfully on that commit.
- Current source metadata is 1.8.0; the new release must actually report 1.9.0.
- Existing v1.8.0 release and its five original assets remain unchanged.

## One version commit through Apply

Bundle 083, OFF-PLAN `REL-190-VERSION`:
`chore(release): prepare version 1.9.0 [REL-190-VERSION]`.

Change package version and its independent packaging expectation; update current
installation/export examples, release instructions and the current specification
header. Describe the already implemented monitor in README. Historical versions,
release evidence and fixtures retain their actual values. No runtime behavior,
workflow implementation, dependency, service or installation change is included.

Development runs a focused parallel selection covering packaging, public export,
distribution/consumer proofs and release gates. Apply runs the complete parallel
suite before the single commit, verifies the exact file scope and performs one
normal push to dev. No tag, GitHub CI, release or main update in the entrypoint.
Failures preserve the working state and evidence; no reset or force push.

## Publication sequence

1. Verify the real Apply Result, clean repository and pushed complete commit.
2. Dispatch existing `acceptance-tests.yml` with `release_action=prepare`,
   `release_version=1.9.0`, the exact commit and a unique handoff identity.
3. Download and verify the exact prepared five files and consumer evidence.
4. Dispatch `release_action=none` on that same commit, wait for all 13 native
   lanes and validate their complete evidence. Baseline CI cannot replace this
   new exact-commit gate. Do not automatically retry unexamined failures.
5. Create and push `v1.9.0` only after successful acceptance. Never replace a
   preexisting/conflicting tag. Record its full object and peeled commit.
6. Dispatch `release_action=publish` with the exact preparation and acceptance
   Run-IDs. The existing publisher uploads the original prepared bytes through
   its checked draft flow; no rebuild or clobber.
7. Verify the published PYZ, wheel, built sdist, runtime-manifest.json and
   SHA256SUMS by downloading them and comparing all full hashes and bindings.
8. Integrate the released dev into main with a normal fast-forward if possible,
   otherwise a reviewed merge. Preserve concurrent changes and the tested tag.

The release is complete only after actual publication, downloaded-byte proof
and confirmed main integration. Durable records belong in Exchange/reports;
planned gates above do not assert that they have already happened.
