# PatchHarbor 1.9.1 release

Explicit user requests on 11 November 2026: merge dev into main and push main,
then tag the newest commit as 1.9.1 and push the tag, and publish the GitHub
release including its PYZ. This authorizes the necessary version preparation,
workflow dispatches, branch integration, tag and publication. Earlier manual-CI
restrictions do not prohibit these expressly requested release actions.

## Confirmed baseline

- Dev/Apply: `d02ed6d6c836723aa634be3b398be65f75d70b34`, clean.
- Polling implemented through Bundle 084 and successful recovery Bundle 085.
- Actual Result `eb2e761c-0af0-43fc-876f-11fb595b495f`; full parallel Apply:
  3722 passed, 15 skipped, four workers; normal dev push verified.
- Main currently `9643cdf442853e248c6a4d5d16b74af9ff7f0763`, an ancestor.
- Package metadata still says 1.9.0. The 1.9.1 artifacts must actually identify
  themselves as 1.9.1; the existing v1.9.0 tag and assets remain historical.

## One version commit through Apply

Bundle 086, OFF-PLAN `REL-191-VERSION`:
`chore(release): prepare version 1.9.1 [REL-191-VERSION]`.

Change the package version and independent packaging expectation, current
installation/export examples, release procedure and current specification
header/plan. Preserve historical contracts and release evidence. No runtime
behavior, workflow implementation, dependency, service or installation change.

Development runs a focused parallel selection for packaging, public export,
consumer proofs and release verification. Apply runs the full parallel suite
before its one commit and one normal push to dev. No serial gate. The Apply
entrypoint does not dispatch CI, update main, tag or publish.

## Authorized release sequence

1. Verify the actual successful Apply Result, clean target and exact dev push.
2. Dispatch `prepare` in the existing acceptance workflow on dev, bound to the
   full confirmed commit, version 1.9.1 and a unique handoff ID. Download and
   verify the exact candidate PYZ, wheel, built sdist, manifest and checksums,
   including distribution and clean/dirty consumer evidence.
3. Dispatch the existing `none` acceptance action on the same full commit.
   Require all 13 native Python/Linux/Windows/shell and Docker lanes and their
   complete evidence. Compare every canonical PYZ hash with the candidate.
4. Follow the requested order: recheck dev and main, merge dev into main using
   a normal fast-forward where possible, and push main. Never force or discard
   concurrent changes. Main must contain the exact approved release commit.
5. Create and push annotated `v1.9.1` at that newest approved commit. Never move
   a preexisting or conflicting tag. Record full tag object and peeled commit.
6. Dispatch `publish` with the exact prepare and acceptance Run-IDs. Use the
   existing checked draft publisher and original prepared bytes; no rebuild,
   clobber or automatic retry of an unexamined failure.
7. Download all five published assets again and verify bytes, hashes, manifest,
   tag, version, source commit and native CI. Confirm main/dev/tag bindings and
   retain durable provenance and downstream handoff in Exchange reports.

The release is complete only after actual publication, downloaded-byte proof
and confirmed main integration. A transient user task may execute these exact
authorized steps so that a chat interruption does not terminate Apply. It must
stop on a failed gate, conflicting ref, mismatched artifact or changed dev head.
