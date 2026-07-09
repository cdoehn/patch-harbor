# PatchHarbor.10c1 target download runner API inventory

This document inventories the target-side APIs needed before PatchHarbor can model the current RepoDossier download patch runner workflow.

This step is target-only and inventory-only. It does not change runner behavior, does not change source wrappers, does not switch `c`, does not install aliases, and does not migrate export scripts.

## Source-side safety net

PATCHHARBOR.10b accepted source-side parity tests for:

- metadata validation
- freshness checks
- repeat detection
- syntax failure handling
- success lifecycle
- failure lifecycle
- footer and completion output

Target-side download runner APIs must be designed against those parity tests. If a later target API intentionally changes current behavior, the change must be documented explicitly before source adoption.

## Current PatchHarbor target capabilities

PatchHarbor already has generic pieces that can be reused:

| Capability | Current target module |
| --- | --- |
| explicit script execution | `src/patchharbor/runner_core.py` |
| runner preflight checks | `src/patchharbor/runner_preflight.py` |
| runner lifecycle model | `src/patchharbor/runner_lifecycle.py` |
| runner output rendering | `src/patchharbor/runner_display.py` |
| metadata parsing and validation | `src/patchharbor/metadata.py` |
| explicit CLI command | `src/patchharbor/cli.py` |

The current target command is explicit-path oriented: `patchharbor run-script <path>`. It does not yet own download-folder selection, archive extraction, applied-ledger lookup, done/failed moves for downloaded artifacts, or download-runner log naming.

## Missing generic target APIs

PatchHarbor still needs generic APIs for the download-runner workflow.

### 1. Download artifact selection

A selection API should decide which input artifact to process.

It should support:

- explicit path selection
- newest eligible artifact selection inside a download directory
- `.sh` patch scripts
- `.zip` archives containing exactly one `.sh` patch script
- ignoring `done`, `failed`, logs, hidden temp directories, and applied-ledger files
- deterministic tie-breaking
- clear errors for no candidate and ambiguous archive contents

### 2. Archive extraction planning

A ZIP planning API should describe extraction without hiding lifecycle ownership.

It should expose:

- original archive path
- extracted script path
- temporary extraction directory
- cleanup responsibility
- validation error when the archive does not contain exactly one script

The lifecycle artifact remains the original `.zip` archive, not the extracted temporary script.

### 3. Download lifecycle planning

A lifecycle plan API should compute paths before execution.

It should include:

- input artifact path
- executable script path
- download directory
- done directory
- failed directory
- log path
- applied ledger path
- whether the input was a direct script or archive

### 4. Repeat detection inputs

Repeat detection must support both current source-side mechanisms:

- applied ledger lookup by SHA256 digest
- existing done-file lookup

The digest must be calculated from the lifecycle artifact. For ZIP input, that means the original archive.

### 5. Freshness inputs

Freshness checking should operate on the selected lifecycle artifact while still reporting the executable script clearly in output.

It should support:

- configurable maximum age
- explicit confirmation behavior outside non-interactive child mode
- non-interactive refusal in child mode
- unchanged exit-code semantics

### 6. Execution handoff

Execution should reuse explicit script execution where possible, but the download-runner API must keep lifecycle ownership for:

- pre-execution validation order
- log capture
- success moves to `done`
- failure moves to `failed`
- applied-ledger update only after successful execution
- final output rendering

## Non-goals for 10c1

This inventory does not introduce:

- `src/patchharbor/download_selection.py`
- `src/patchharbor/download_runner.py`
- new CLI flags
- source-repository wrapper changes
- alias changes
- local download path defaults
- export runner behavior
- deletion of any RepoDossier script

## Proposed next steps

The next target-side steps can stay small:

1. `PATCHHARBOR.10c2` adds a download artifact selection API and tests.
2. `PATCHHARBOR.10c3` adds lifecycle execution APIs in smaller substeps if needed.
3. Source-side wrapper work waits until target APIs are tested and accepted.

## Acceptance

This inventory is accepted when PatchHarbor documents the missing generic target APIs, keeps the source-side parity suite as the behavior contract, and makes clear that no runner behavior is changed by this step.
