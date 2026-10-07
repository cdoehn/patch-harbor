# Result format 3: PYZ runtime metadata 2

PP-05A adds the full data reader before any production writer switch. The normal
writer still emits Result 2. Synthetic format-3 fixtures prove the new reference
reader; they are not evidence of a successful new producer or installed upgrade.

The normative contract is the joint main specification and
[PYZ/PACK extension](../spec/SPECIFICATION_EXTENSION_PYZ_PACK.md), especially
FMT-01–05 and MIG-01–06. Patch format 1, Environment/Handoff format 1, and public
inspection/validation output versions are unchanged.

A Result-3 manifest has the same repository, run, snapshot and change fields as
Result 2. Its runtime object has exactly `status`, `reason`, `metadata`, `artifact`.
The metadata descriptor has exactly `path`, `size`, `sha256`, and points to
`runtime/runtime.json`. An embedded artifact descriptor also has `type: pyz` and
points to `runtime/patchharbor-<version>.pyz`. No `wheel` field is repurposed.

The runtime document is marker `patch-harbor-runtime`, integer `format_version: 2`,
distribution `patchharbor`. Its closed fields additionally describe `status`,
`reason`, `version`, `requires_python`, `profile`, `content_id`,
`content_id_algorithm`, `artifact`, `runtime_dependencies`, `provenance`,
`capabilities`. Embedded values require:

- Profile `patchharbor-core-no-watcher-v1`, algorithm `patchharbor-pyz-content-v1`.
- One nonempty PYZ, exact size/SHA and descriptor equality with the manifest.
- No runtime dependencies, no wheel tags or additional runtime files.
- Provenance `canonical_resources`, full source commit or null matching the recipe,
  recipe version 1 (an integer, not a boolean).
- Chat-tool operations `inspect_patch`, `validate_patch`, `pack_patch`, patch
  formats `[1]`, result formats `[1, 2, 3]`. These capabilities do not restrict
  the other normal Core operations; the PYZ deliberately excludes the Watcher.

The reader verifies the entire canonical PYZ profile as data: recipe and producer
identity, inventory, every file size/hash, version/provenance agreement, and exact
canonical archive bytes. It never imports or executes described runtime code.
Outer expanded bytes plus inner contents share the existing Result budget.
PYZ size, member count, recipe size and per-file limits apply before unbounded
metadata allocation or expansion. No independent unlimited inner budget exists.

`unavailable` retains only its metadata file, with no artifact, profile, content
ID/algorithm, dependencies, provenance or capabilities. The established reasons
are retained: `source_not_prepared`, `source_changed`, `artifact_missing`,
`artifact_mismatch`, `artifact_corrupt`, `artifact_unsupported`, `resource_limit`,
`read_error`. Known version/Python facts may be present, otherwise null. The run
must contain a warning. This never permits deleting mandatory snapshot or log data.

The new immutable internal Result-PYZ facts have `artifact`, while legacy facts
keep `wheel`. Public `validate_patch` signatures, scopes and categories are
unchanged. Corrupt full references still fail with source error 4. The deliberately
private repository-only diagnostic reader can exclude only the reserved runtime
namespace; it retains all other integrity checks and is never used by `pack` or
full native reference validation. No downgrade or repaired reference is invented.

PP-05B verifies Format-3 Exchange/archive/recovery integration using real consumer
processes, including frozen Format-1 and complete Format-2 runtimes. A standalone
PYZ remains a non-patch artifact. Unavailable, corrupt and future Results cannot
become archival/recovery success proofs. The canonical handoff includes the
reviewed executable bootstrap before the PP-06 writer gate. Existing
Result ownership, sync, finite typed CIFS retries, shared wait budget and final
verified hash binding remain unchanged; `pack` retains its separate no-retry policy.
