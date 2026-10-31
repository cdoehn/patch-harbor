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
no watcher/global installation changes. Build and local artifact/consumer gates
precede tagging; exact-commit CI precedes publication. No fictitious C behavior; documentation is a real
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


Aktuelle Nutzerentscheidung im REL-180-Auftrag: Nach Apply-Abschluss, lokalen
Abnahmen und geprüftem Build darf Codex das neue v1.8.0-Tag am vollständigen
Abschlusscommit anlegen; danach folgt die exakte CI. Bei fehlgeschlagener CI
wird ausschließlich dieses selbst neu angelegte und weiterhin unveränderte
Tag entfernt. Bestehende fremde oder abweichende Tags werden nicht verändert.
Der Release bleibt bis zu grüner CI und allen Asset-/Downloadprüfungen
unveröffentlicht. Diese Entscheidung ersetzt die frühere manuelle Taganlage
und den zwischenzeitlich erlaubten Abschluss ohne GitHub-Veröffentlichung.


Every official build always emits wheel, sdist and Core-PYZ, regardless of tags.
Release preparation is tag-independent. After candidate verification, create the
new exact-commit tag and dispatch acceptance. On CI failure remove only our own
unchanged new tag; preserve conflicting or preexisting tags. Publication requires
the complete green exact-commit matrix and byte identity with its builds. The
original prepared assets are uploaded without rebuilding and downloaded again.
Durable evidence in Exchange/reports supplements the actual GitHub Release.

W-final: 234 passed on 12 workers, Linux CPython 3.14.4, selected contracts only.
R-first had a nonexistent selected test path and ran no tests (exit 5); it is
not a successful gate. The corrected selection uses test_result_snapshot.py.

R-second: 323 passed, two failures and one teardown error. Corrected the missing
dataclass import in the installed-runtime probe, compared permission-test output
against the fixture's actual inventory, and isolated build-tool processes to
prevent their import-search-path changes from leaking into test workers.

R-third: all 330 selected tests passed on 12 workers, including actual offline
wheel/sdist/PYZ exports and clean/dirty direct-consumer proofs. Final workflow
review adds the declared build/verification dependencies to the publish job so
its canonical-byte audit can import the same anchored build backend. Candidate
files are never rebuilt there. The final R gate selects release/CI/catalog and
architecture contracts affected by that workflow adjustment.

R-final: 119 selected release/CI/catalog/architecture cases passed with 12 workers.
C consolidates README, installation, runtime/API and release instructions and
links the already verified public-only consumer. No new runtime behavior.
Final Development selection covers export/distribution/release, canonical
resources, packaging, snapshots, safe-reference and existing integration paths.
The exact selection, source hash, logs and exit receipts are in Exchange/reports.
Actual Apply, candidate/tag, native CI and published downloads remain external
gates until their own evidence is recorded; no local test closes them.

Actual Apply 075 confirmed REL-180-01 at
`ded3093d4f91931b2d4e39c045d6e052033abc18` after 3,545 passed / 15 skips.
REL-180-02 stopped before commit: one stale launcher expectation omitted the
two new mandatory Windows export test files; 3,587 other cases passed, 15 skipped.
No push occurred. The native failed Result SHA-256 is
`d0d50e1b030f3c424a8c913f656bb59212ec9557ae62c812eaa19df9419d261a`.
Bundle 076 preserves the confirmed commit and exact pending R state, corrects
that expectation, then delivers the two remaining real R/C states. This second
bundle follows a demonstrated full-Apply failure; no new feature or phase.
Development remains selected parallel; Apply repeats the full parallel suite
before both remaining commits and performs one final normal push. Tag, native
CI and release publication remain open, in that explicitly authorized order.
