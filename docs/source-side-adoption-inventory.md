# PatchHarbor.08 source-side adoption inventory

PatchHarbor.08 starts the adoption phase for source repositories.

This step is inventory-only. It does not edit RepoDossier, does not create wrapper files, does not install aliases, does not replace existing source runners, and does not commit to the source repository.

## Purpose

PatchHarbor.06 created the generic explicit runner foundation.

PatchHarbor.07 created the generic compatibility configuration, planning, and rendering foundation.

PatchHarbor.08 decides how a source repository can adopt those target-side contracts without losing the existing local workflow. The first step is to inventory the adoption candidates and the risks before writing any source-side patch.

## Adoption candidates

| Source file | Current role | Adoption status | Proposed direction |
| --- | --- | --- | --- |
| `scripts/dev/run_latest_download_patch.sh` | local download patch runner used by the convenience workflow | candidate, high risk | preserve behavior first; later make it a thin wrapper or replace it only after dry-run parity checks |
| `scripts/dev/install_aliases.sh` | local shell alias installer | candidate, medium risk | later point aliases to source wrappers or PatchHarbor commands without storing machine-local paths in tracked files |
| `scripts/dev/r.sh` | short export runner entry point | defer | keep unchanged until export runner migration is explicitly planned |
| `scripts/dev/run_repodossier_exports.sh` | source-specific export runner | defer | split source-specific export defaults from any future generic export helper |
| `scripts/dev/repo_patch_helper.py` | helper behavior for local patch execution | reference only | compare behavior against PatchHarbor runner APIs before deleting or wrapping anything |
| `scripts/dev/show_progress_context.py` | progress and footer display behavior | reference only | compare output expectations against PatchHarbor display APIs |
| `scripts/dev/validate_patch_metadata.py` | source-side metadata validation | reference only | PatchHarbor metadata and preflight APIs are the generic target-side contract |
| `scripts/dev/lint_patch_script.py` | source-side lint wrapper | reference only | PatchHarbor lint APIs are the generic target-side contract |
| `scripts/dev/patch-rules.md` | human workflow and patch rules | reference only | keep as source workflow documentation unless a later documentation migration is planned |

## Readiness classification

Ready for dry-run planning:

- source-side runner wrapper draft
- alias compatibility update plan
- adoption acceptance documentation

Not ready for mutation yet:

- replacing the current download runner
- deleting source helper scripts
- changing the export runner
- installing aliases automatically
- changing shell rc files
- committing source repository changes without focused source-side tests

Deferred:

- export runner migration
- public audit helper migration
- development-environment helper migration
- full source cleanup after wrappers prove parity

## Risk checklist

Before any source-side patch is allowed, the adoption patch must answer:

- Which source files are touched?
- Is the patch reversible?
- Does the old convenience workflow still work?
- Are download success and failure paths preserved?
- Does repeat detection still stop accidental re-runs?
- Is the displayed current, next, and problem context preserved?
- Does the patch avoid private paths, workstation names, and email addresses?
- Does the patch keep source-specific defaults outside generic target modules?
- Does the patch run focused source-side tests before a full suite?

## Proposed PATCHHARBOR.08 sequence

1. Source-side adoption inventory.
2. Source-side runner wrapper draft with no alias installation.
3. Source-side alias compatibility update plan.
4. Source-side runner compatibility tests.
5. Source-side adoption acceptance documentation.

Only after those steps should deletion or replacement of old source scripts be considered.

## Non-goals for this step

- no RepoDossier file changes
- no source repository commits
- no wrapper file writes
- no alias installation
- no shell rc-file changes
- no download-folder mutation
- no export runner migration
- no deletion of old source scripts
- no compatibility command adoption
- no automatic replacement of local workflows

## Acceptance

This inventory is accepted when PatchHarbor documents the adoption candidates, readiness classification, risk checklist, proposed sequence, and non-goals.

The next patch may prepare a source-side runner wrapper draft, but it must still avoid broad source repository migration.
