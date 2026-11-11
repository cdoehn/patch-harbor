# Source-safe reference integration – PatchHarbor 1.7.0

The implementation targets SpecRoad's separate 15.n.W integration. It does not
complete that downstream step. The normative contract is §43 of
[the specification](../spec/SPECIFICATION.md), together with both existing
extensions. Exact signatures, operating boundaries and semantic errors are in
[the public API documentation](python-api.md#source-safe-reference-export-contract-1).

Use the new, externally verified 1.7.0 Core-PYZ or wheel. Preserve historical
1.6.0 artifacts and hashes. For the Core-PYZ, place the verified PYZ path on
`sys.path` in a fresh process. For wheel-based production, use its verified
installed module layout or a privately extracted copy of that trusted wheel;
put that directory on `sys.path`. Direct wheel ZIP imports are for read-only
inspection and do not provide the resource layout needed for Result production.
Use only `from patchharbor import api`. Require the exact integer
`safe_reference_contract_version == 1` before source/export calls. The existing
`contract_version`, `snapshot_contract_version` and `guarded_execute_contract_version`
remain 1; a version string alone is insufficient.

[safe_reference_export.py](examples/safe_reference_export.py) is a complete
public-only example. It calls safe context, read-only bound preparation, the
host's explicit authorization callback, safe bundle and externally SHA-bound
native snapshot reading. The authorization callback must check the selected
repository, output/diagnostic and lock paths against the host's own policy.
There is no automatic registration or unsafe fallback. Configuration and source
changes require a new independently authorized plan.

[create_safe_reference_fixture.py](examples/create_safe_reference_fixture.py)
creates reproducible synthetic clean/dirty projects in a **new empty root** in a
dedicated process. It deliberately isolates HOME/XDG/Git, creates a fixture commit
and registration, and supplies independently expected file inventories. These
fixture setup mutations are separate from the source-safe export. Never point
it at an existing user project. The dirty fixture covers simultaneous staged and
unstaged bytes, binary/empty files, deletion/rename, executable mode and untracked
bytes; an ignored witness must remain absent from the Result.

The delivery includes native clean and dirty Result ZIPs made from this fixture
with the exact new runtime, plus wheel, sdist, Core-PYZ and a SHA-256/provenance
manifest. The embedded descriptor/runtime and all five file layers are checked
through the public reader. The source inventory is bound before Execute and must
match the actual confirmed Execute commit. A recipe's own metadata is not a trusted
substitute for this external provenance.

On success use `BundleResult.path`, `context`, `report`, `run_id` and
`publication_durability`; retain the complete external Result SHA-256. Handle
`SafeExportError.code`, `emergency_diagnostics_path`,
`emergency_diagnostics_failed` and `published_path`. A late cleanup/interrupt
error can report an already complete published Result. It remains an error;
inspect that actual partial outcome before retrying. A killed process may leave
private hidden staging/diagnostic bytes, never an incomplete final ZIP.

The new producer capability is Linux x86-64 / CPython 3.10–3.14, with local Git,
`/proc/self/fd`, existing owned directories and exclusive hardlink support.
Active filter/encoding/ident conversions, ambiguous EOL normalization and
previously unsupported Git states are refused. Default CLI, watcher and API
calls retain their previous behavior. The safe mode does no Exchange maintenance,
recovery, archive, replay write or Execute.

Local evidence is CPython 3.14.4 / Linux x86-64 only. The manual CI catalogue now
also includes native Linux 3.13 and requires the real wheel/PYZ safe-export
proofs on every Linux lane. CPython 3.10/3.11/3.12/3.13, Windows compatibility and
Docker evidence for this exact source remain open until Christian runs CI.
POSIX-root lanes explicitly skip permission-bit denial witnesses because root
bypasses those bits; ordinary native user lanes exercise actual I/O denial.
CI, tagging, release publication, installation and SpecRoad adoption are separate.

Bundle 073 confirmed SAFE-01 and stopped at stale SAFE-02 packaging assertions.
Correction bundle 074 preserves that actual partial progress and completes
SAFE-02 and SAFE-03, with a full parallel gate before each remaining commit
and one normal final push to dev. Local Development gates are selected
parallel tests only. The actual outcome, commits, complete hashes, artifact paths
and per-requirement status are recorded externally in
`exchange/reports/patchharbor-safe-reference-074-result-review.json` and
`exchange/reports/patchharbor-safe-reference-074-integration-delivery.json`.
Before these records confirm Execute, this document describes a prepared delivery.
