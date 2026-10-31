# REL-180 – Runtime export and GitHub releases

Explicit request: `/tmp/patchharbor-v1.8.0-runtime-release-auftrag-qzdzqm9q.txt`.
Normative contract: main specification §44 and the PYZ/PACK/CPython supplements.
Baseline: actual successful Apply 074, full commit
`299782e02bec55a7b8593bd99ee5b11f6122a432`, native Result SHA-256
`9aa4b4f6a64b900fb261bb34d8a79251c667073a98fd3eec9accbf9db8b22795`.
The older dirty development root is preserved. No direct Apply edits.

One bundle, three real successive states, no development commits:

| Phase | Deliverable | Acceptance |
| --- | --- | --- |
| REL-180-01 / W | Version 1.8.0, specification, public CLI/API, canonical export, basic tests | selected parallel export/provider/CLI/API/packaging contracts |
| REL-180-02 / R | fault and distribution proofs, generic manifest/release workflow, exact commit gates, consumer integration | selected parallel distribution/release/compatibility tests |
| REL-180-03 / C | final review, release instructions and runnable integration example | selected parallel final changed contracts and handoff audit |

Freeze each state only after its own actual development gate. Apply must run the
complete parallel suite before each commit, including the final commit. Exactly
one normal dev push after all commits. No serial gates, CI/tag/release in entrypoint,
no watcher/global installation changes. Tag only after the exact final CI and
artifact/consumer gates pass. No fictitious C behavior; documentation is a real
reviewable final delta. Local, Apply, CI and downloaded-release evidence differ.

Required evidence mapping:

| Contract | Evidence |
| --- | --- |
| Export bytes/facts/own producer | runtime export and existing provider tests |
| Missing/tampered/swapped resources, paths, races, permissions, interruption | export failures plus native pack publication/resource tests |
| Wheel, sdist, PYZ, offline no-Git API/CLI | actual distribution export processes |
| Result byte equality and old API contracts | safe-reference distribution/roundtrip, frozen compatibility, pack/apply/snapshot tests |
| Version/commit/tag, complete assets, manifest/checksums, replay/conflict refusal | release policy fixtures and actual workflow |
| Trusted hash before import, capability checks, safe clean/dirty reference | public consumer example with synthetic fixture |
| Final applied files, full gates, pushed commit | native Result and read-only Apply review |
| All platform lanes, published original bytes | exact-commit acceptance review and post-release downloads |

Implementation is pending until evidence is recorded externally in Exchange/reports.
Historical versions/results are preserved. SpecRoad adoption is a separate task.

W-first: 233 passed, one packaging size failure. The measured 1.8.0 wheel is
396,934 bytes, versus the old 393,216-byte transport budget. The versioned
transport-only regression bound becomes 416 KiB (425,984 bytes), with the exact
module allowlist and zero dependency checks retained. Core-PYZ/Result/resource
security budgets are unchanged. This budget change accounts for the new API and
packaged documentation; it does not hide a broken install or enlarge input limits.
