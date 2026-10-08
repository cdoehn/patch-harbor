# PatchHarbor – public Python API

Use `from patchharbor import api`. This is the only supported public Python
namespace; implementation modules remain internal. The documented names and
value fields form the supported compatibility surface introduced in 1.2.0 and
extended by the joint PYZ/PACK specification. Within the 1.x series, fixes and
compatible additions preserve documented calls and result
semantics. Exception: this explicitly approved repository-local configuration
revision of the 1.2.0 development line supersedes the earlier global-setting
semantics. It has no migration or compatibility fallback; the method names stay,
but configuration calls now require a registered target repository.
Additional enum values or diagnostic event wording must not be treated as an
exhaustive state machine. Private modules and undocumented helpers remain free
to evolve.
There are no new runtime dependencies. For an ordinary import, install PatchHarbor
into the calling program's Python environment; installing the CLI with a tool
manager does not install it into every other environment. Alternatively, the
[verified PYZ bootstrap](runtime-bootstrap.md) supplies `import_api(prepared)`
without installation. Both routes expose the same public API.

```python
from pathlib import Path
from patchharbor import api

repo = Path.home() / "Projekte" / "patch-harbor"
context = api.context(repo)
print(str(context.repo_id), str(context.base_commit), context.state_fingerprint)
bundle = api.bundle(repo)
print(bundle.path)
report = api.dry_run(repository=repo)
print(report.success, report.result_bundle.status)
```

## Operations and CLI correspondence

| Python | CLI operation | Returned value |
| --- | --- | --- |
| `configuration(repository=".", revalidate=False)` | `configure show` | `ConfigurationResult` |
| `configure_exchange_directory(directory, repository=".")` | `configure exchange-directory` | `ConfigurationResult` |
| `configure_bundle_suffix(suffix, repository=".")` | `configure bundle-suffix` | `ConfigurationResult` |
| `configure_archive_directory(name, repository=".")` | `configure archive-dir` | `ConfigurationResult` |
| `register(repository=".", new_id=False)` | `register` | `RepositoryContext` |
| `unregister(selector, cwd=".")` | `unregister` | `UnregisterResult` |
| `repositories()` | `registry list` | `RegistryListResult` |
| `context(repository=".")` | `context` | `RepositoryContext` |
| `inspect_patch(patch)` | `inspect PATCH_ZIP` | `PatchInspection` |
| `validate_patch(patch, repository=None, reference_bundle=None)` | `validate PATCH_ZIP` | `PatchValidationResult` |
| `pack_patch(content_directory, reference_bundle=..., entrypoint=..., output=None, output_directory=None, modes=None)` | `pack CONTENT_DIRECTORY` | `PatchPackResult` |
| `bundle(repository=".", output_directory=None)` | `bundle` | `BundleResult` |
| `apply(patch=None, repository=None, dry_run=False, ...)` | manual `apply` | `RunReport` |
| `dry_run(patch=None, repository=None, ...)` | `apply --dry-run` | `RunReport` |
| `apply_next(dry_run=False, ...)` | automatic global Apply | `RunReport` |
| `watch_targets()` | validated Exchange roots and control paths, without bundle scanning | `WatchTargets` |
| `watch_control_paths()` | registry/local config paths even with invalid local config | `WatchControlPaths` |
| `apply_readiness(lock)` | probe and release a known technical lock conflict | `ApplyReadiness` |
| `run(source, cwd=".", ...)` | `fs run` | `ScriptResult` |

All operations accept `observer=None`. Execution operations accept
`output=None`; `apply`, `apply_next`, and `run` accept `timeout=10800.0` seconds.
Timeouts must be finite and positive; booleans and numeric strings are invalid.
The public default is `api.DEFAULT_TIMEOUT_SECONDS`.

Path parameters accept `str` and `os.PathLike[str]`. Tildes are expanded; bytes,
empty paths and NUL are rejected. Symlinks are not resolved away by the facade:
the existing Core file checks decide whether a link is permitted. Most relative
paths use the caller's current working directory. A relative `run(source)` path
is relative to its explicit `cwd`, which is also the child's working directory.
The library never changes the process-wide current directory or environment.
For concurrent callers use explicit absolute paths and do not change shared
process environment/working directory while another call is active.

An empty suffix clears it; an empty archive name disables archival for the
selected repository. Registry operations use the user-global registry, not an
independent API store. API calls do not install a watcher or implicitly register
repositories.

## Static package inspection (RIV development addition)

This development line implements package/binding validation, portable offline
runtime, `pack_patch` and Result Format 3; no release is implied. The existing
`dry_run` keeps its Apply semantics and still creates a Result Bundle.

```python
from patchharbor import api

info = api.inspect_patch("patch.zip")
print(info.package_sha256, info.package_size, info.entrypoint)
for entry in info.entries:
    print(entry.path, entry.role.value, entry.size, entry.sha256, entry.unix_mode)
report = api.validate_patch("patch.zip")
assert report.scope is api.PatchValidationScope.PACKAGE
assert report.binding_matches is None
```

Both calls require one explicit `str` or `PathLike[str]` file path. A relative
path is anchored once to the caller's directory; this does not select a
repository. The existing stable file/ZIP, manifest, reserved handoff and script
parsers apply. Unsafe input never returns partial successful facts. Interpreter
syntax is checked without requiring the shell to be installed. No Git, registry,
Exchange scan, locks, payload writes, script execution, temporary script, runtime
provider or Result publication occurs in package/reference mode. Repository mode
uses the existing registration, bounded lock effects and controlled Git queries.
The request-local `observer=None` has
the usual silent-library and best-effort observation semantics.

`PatchInspection` is frozen and contains `package_sha256` (full lowercase SHA-256),
`package_size` (archive bytes), typed `manifest`, normalized `entrypoint`, and
tuples `entries`, `messages`, `warnings`. Every frozen `PatchEntry` has `path`,
`role` (`PatchEntryRole`: `manifest`, `entrypoint`, `payload`, `handoff`), `size`
(uncompressed bytes), full content `sha256`, and `unix_mode` (integer permission
bits, or `None` if absent). Entries are sorted by normalized path; explicit ZIP
directories are checked but omitted. The frozen `PatchManifest` retains all
seven manifest fields, with typed repository and Git IDs. `PatchMessage` has
`name` and `text`. No payload bytes are retained in these public facts.

`PatchValidationResult` is frozen and contains `inspection`, `scope`,
`binding_matches`, `context`, `reference_sha256`, `checked_at`, and `not_checked`.
For `package` scope, binding/context/reference are `None`.
`checked_at` is an aware UTC `datetime`; `not_checked` is a tuple of identifiers:
`repository_binding`, `repository_state`, `authenticity`, `execution`,
`interpreter_availability`, `tests`, `ci`, `replay`. Successful static validity
does not establish sender trust or approve a later Apply. Content hashes are
computed observations, not new declared hashes in format-1 `patch.json`.

`validate_patch(patch, reference_bundle="result.zip")` returns scope `reference`,
`binding_matches=True`, the full SHA-256 of the captured reference bytes and a
frozen `ReferenceContext`. Its fields are `repo_id`, `base_commit` (the existing
typed IDs), `state_fingerprint`, `fingerprint_algorithm`, `dirty` and
`repository_path` (recorded text, including foreign Windows paths; never resolved
on this machine). This reader checks the complete format-1/2/3 inventory, blob IDs,
untracked SHA-256 and metadata consistency, accepting consistent dirty, failure
and dry-run Results. It uses actual context, never the previous expected binding.
Repository snapshot paths retain the existing portable UTF-8 repository rules;
patch package paths still use the stricter ASCII contract.

The shared Result reader supplies integrity-checked facts to reference validation
and to archival/recovery policy. A valid reference does not itself prove a
successful Apply: those consumers still require a clean, completed success,
no warnings or dry run, the appropriate expected binding and, for recovery,
the existing receipt, local digest and Git evidence. Their conservative ZIP
path policy is unchanged. Current writers emit format 3 with one verified Core-PYZ
or a declared runtime-only restriction; readers also accept formats 1 and 2.
Full reference validation rejects a corrupt declared runtime. The separately
reviewed [bootstrap and previous handoff procedure](runtime-bootstrap.md) can
check repository evidence independently when only that optional addition fails.
Such a receipt is explicitly distinct from native full reference validation.

`validate_patch(patch, repository="/workspace/repository")` returns scope
`repository`, `binding_matches=True`, the existing `RepositoryContext` and no
reference SHA. The explicit repository must already be registered. Both keywords
together raise `ValueError`; there is no implicit CWD, registry or Exchange target.
All relative input paths are anchored to one calling directory before observation.
The operations do not reserve a Result target or change registry, index, replay,
attempts or repository contents. Later Apply always checks its inputs/state again.
Repository validation rechecks the existing identity and registry mapping after
the consistent state capture, while retaining its repository lock. Read queries
disable Git fsmonitor helpers; optional Git locks remain disabled. A missing
registration does not create configuration directories or identity files. Only
the existing bounded lock directories/files may be created by this mode.
Read-only validation compares parsed index entries and stable raw file bytes,
without Git's racy-index filter execution. Ambiguous content conversions fail
with unsupported-state error 13: selected filters/working-tree encoding, expanded
ident values, or CRLF bytes subject to Git text/EOL conversion. Ordinary LF text
changes remain validatable even with text/eol attributes. Normal context, Apply
and bundle retain the existing state-v1 Git comparison and fingerprint contract,
including `core.fileMode=false`; validation does not emulate conversion helpers.

Both binding scopes retain `authenticity`, `execution`, `interpreter_availability`,
`tests`, `ci`, `replay` in `not_checked`. Reference additionally reports
`live_repository_state`, `local_registration`, `reconstructed_state_fingerprint`,
`legacy_delta_log_hashes`: format 1 has no independent cryptographic hashes for
every delta/log, and no deltas are applied here. Repository additionally reports
`future_repository_state`. This is a point-in-time comparison, not an execution,
replay or sender-trust authorization. Any binding mismatch raises error 9;
invalid/unreadable/unsupported references raise input error 4. Repository errors
retain existing codes (8, busy 12, unsupported state 13).

CLI binding options are mutually exclusive:
`patchharbor validate patch.zip --reference-bundle result.zip --json` or
`patchharbor validate patch.zip --repository /workspace/repository --json`.
The JSON `context` object uses the same six fields as `context --json`, with
complete string IDs and a boolean `dirty`. Reference paths remain foreign text.

CLI examples: `patchharbor inspect patch.zip --json` and
`patchharbor validate patch.zip --json`. Both also accept `--help`, `--verbose`
(`-v`), `--no-color` and `--plain`. Their JSON envelope has `output_version: 2`,
`command: "inspect"` or `"validate"`, and the existing `success`, `result`,
`error`, `process_exit_code` fields. After successful argument parsing stdout
contains exactly one JSON object, including known error outcomes; JSON never
contains progress output. Older commands keep output version 1.

The inspect `result` has exactly the inspection fields above. `manifest` uses
the seven patch.json field names and complete string identifiers; `entries` use
the five PatchEntry field names; `messages` use `name` and `text`. Tuples become
arrays and enums become their string values. The validate `result` has exactly
the validation fields above, with nested `inspection`, null optional values,
and a UTC ISO-8601 `checked_at` ending in `Z`. A failure has `result: null` and
the unchanged structured tool `error`. Argument types/values fail as
`TypeError`/`ValueError`; known package failures raise `PatchHarborError` in the
API. CLI codes remain 2 (usage), 3 (invalid script/marker), 4 (unsafe/unreadable
input), 5 (unsupported interpreter syntax), 10 (invalid package/manifest), and
0 (successful static check). Existing resource limits remain in force.

For these calls, path type/value validation precedes observer validation; both
precede anchoring the path and Core file I/O. Invalid observers do not cause a
filesystem lookup. Recognized ZIP decompressor failures and filesystem encoding
errors are input errors (4); a JSON decoder recursion limit is a manifest error
(10). Unexpected programming exceptions and interruption signals propagate.
Each request binds its own observer and restores the enclosing scope even on
failure; a nested call with `observer=None` does not inherit its caller's
observer. A replaced filename after capture cannot change the returned digest
or facts; a later Apply must independently read and validate its own bytes.

## Repository-local configuration

`configuration(repository=".", *, revalidate=False, observer=None)` accepts the
repository as its first argument. The three setters accept `repository="."`
as a **keyword-only** argument after their value; `observer` is also keyword-only.
Omitting the repository resolves the caller's current working directory,
including subdirectories, to one registered Git root. No process-wide `chdir`
is needed. Outside a registered repository or with conflicting/missing local
identity/configuration, calls raise `PatchHarborError`; none creates defaults.

```python
from pathlib import Path
from patchharbor import api

repo = Path("/absolute/path/to/repository")
api.register(repo)  # genuine first registration, not a missing-config repair
api.configure_bundle_suffix(".txt", repository=repo)
api.configure_archive_directory("Archive-A", repository=repo)
api.configure_exchange_directory(Path.home() / "Downloads", repository=repo)
settings = api.configuration(repo, revalidate=True)
print(settings.path, settings.exchange_directory)
```

`ConfigurationResult` has `path: Path`, `exchange_directory: Path | None`,
`bundle_suffix: str`, and `archive_directory: str`. `path` is the selected
repository's `.patchharbor/config.json`. Fresh registration creates the closed
four-field local Format 1 (`format_version`, `exchange_directory`, `bundle_suffix`,
`archive_directory`); Exchange is initially `None`, suffix empty and archive
`PatchHarbor-Archive`. ID binding comes from `.patchharbor/id` plus the registry,
not a duplicated `repo_id` field inside the config.

Ordinary `configuration()` validates identity and the JSON schema but does not
probe whether the stored Exchange directory is currently available. It can
return `None` or an unavailable absolute Exchange path without changing it.
`revalidate=True` additionally requires an existing physical Exchange directory
and the separation policy against registered repositories. It does not create
one or reserve it for later operations. Setters hold the registry lock before
the target repository lock and publish the complete local document atomically.
All other settings are preserved. Suffix/archive can be set before Exchange;
when an Exchange value is present it is revalidated on writes. Only an explicit
Exchange setter creates/replaces the requested directory setting.

Multiple repositories may use the same Exchange directory while retaining
different suffix/archive preferences. Bundle, Apply, Result publication and
archival use the resolved target's settings. `output_directory` overrides only
the result destination: unset/unavailable Exchange is permitted, but a missing
or corrupt config is never bypassed. `environment.json` describes this target,
not user-global preferences; `bundle_suffix` in Result `context.json` is filename
metadata, not part of the state fingerprint or patch manifest.

`unregister()` preserves ID, config and Git's local exclusion. Re-registering an
intact instance reuses them; a real move requires the previous path to be absent.
A normal Git clone lacks these ignored files and needs fresh registration plus
configuration. Existing registered instances from the old version need manual
local JSON setup as described in the README. No API call reads/imports the old
global `config.json`, repairs missing metadata, or resets the replay ledger.

## Apply selection and safety

With no explicit patch, `apply(repository=...)` selects for that registered
repository (subdirectories are allowed). Omitting repository means current
directory, exactly like manual CLI Apply. A failed identity is retryable only
under the same existing state rules. An explicit patch selects by its manifest
repo_id, not by cwd. Combining `patch` with `repository` is rejected: the latter
is a discovery scope, not an extra target constraint that could be ignored.

`apply_next()` performs exactly one global automatic poll across the registered
repositories' locally configured Exchange directories. It reloads their settings
and scans each distinct physical directory once. A package in another repository's
Exchange is not eligible unless its own target uses that same directory. Only
then do state/replay validation and newest-`mtime_ns` selection apply across all
eligible candidates. It never retries a failed identity; Core owns selection,
replay, lock, revalidation, recovery and publication together. No separate select-then-apply token or stale
validated package is exposed. The watcher uses this operation in a separate
worker process for each event-triggered scan; the library never starts a loop.

The optional `exchanges` argument accepts a tuple of `ExchangeWatchTarget`
snapshots from `watch_targets()`. `None` retains global discovery; `()` scans
nothing. Each target contains the canonical directory, device/inode identity and
registered owner IDs. Duplicate roots are scanned once. Core reloads configuration
and rejects foreign, reconfigured or physically replaced targets before scanning.
It rechecks physical identity during discovery and immediately before consuming
the replay identity. Only selected roots undergo bundle reads, recovery and
archive maintenance; an active download in another Exchange is not scanned.
These snapshots grant no authority and reserve no candidate or repository lock.

`watch_targets()` reads registry and local configuration without enumerating
Exchanges, hashing bundles or capturing Git state. Unset Exchanges and missing
repositories contribute no Exchange root; invalid live configuration/identity or
a missing configured Exchange fails closed. `registry_path` and
`configuration_paths` identify control files, including unset/missing repositories.
Clients must observe their parents/ancestors for atomic replacement/restoration.
`watch_control_paths()` supplies those registry-derived paths independently of
local configuration validity, so a suspended client can observe a repair. Its
`exchange_paths` also carries advisory paths from valid documents without
requiring those directories to exist. Clients may watch their existing parents
for restoration. These are never validated scan scopes; `watch_targets()` and
Apply still reject missing or invalid destinations.

Automatic calls set `report.automatic` to immutable `AutomaticApplyResult`:

| `AutomaticApplyStatus` | Scheduling meaning |
| --- | --- |
| `NO_CANDIDATE` | Valid discovery finished without an eligible candidate; stop draining. |
| `ATTEMPTED` | The replay boundary consumed a candidate; execution may still have failed. Further candidates may be checked subject to the caller's quiet-period rules. |
| `LOCKED` | No attempt was consumed; `blocked_on` identifies the technical lock. |
| `DRY_RUN` | Successful validation only; no consumption or progress-driven drain. |
| `ERROR` | No confirmed progress; await an external change/repair, without blind retry. |

For a known pending lock conflict, `apply_readiness(report.automatic.blocked_on)`
probes the registry, repository or Exchange-state lock and releases it before
returning. `ready` is momentary; `blocked_on` identifies a remaining conflict
(possibly the registry needed to resolve a repository lock). No Exchange scan,
bundle hashing, replay-state read or reservation occurs. Unregistered repository
IDs and lock-operation errors raise `PatchHarborError`; they are not readiness.
Apply must still reenter all normal gates after a successful probe. Do not call
readiness periodically when idle.

Scheduling status is in-process API data, not persisted Apply-success evidence;
existing CLI/Result JSON schemas are unchanged. Manual Apply has `automatic=None`.
The CLI watcher uses native events and five quiet seconds per Exchange. WE-3
passes the selected scope and structured progress through a versioned private
worker protocol; the public CLI/Result envelope is unchanged.

Dry-run still produces a Result Bundle when a repository can be safely resolved;
it neither writes payload files nor executes, consumes replay or archives. API
Apply still attempts the automatic Result Bundle on failures. There is no
rollback: trusted scripts can commit, mutate files or fail after partial work.
PatchHarbor remains a controlled runner, not a sandbox.

## Results and errors

`apply`, `apply_next`, and `dry_run` always return the existing immutable
`RunReport` for known Core outcomes, including failures. Read `report.success`,
`report.primary_result`, `report.completion_tool_error`, and
`report.result_bundle`. Do not infer success merely from an existing bundle.
`report.context`, when available, is the captured resulting repository state;
`report.primary_result.entrypoint_exit_code` belongs to the child. A script exit
124 or 130 is **not** reclassified as a tool timeout/interruption.

```python
report = api.apply(repository=repo)
if not report.success:
    error = report.completion_tool_error
    if error is not None:
        print(error.kind, error.reason, error.message)
    else:
        print("Script failed:", report.primary_result.entrypoint_exit_code)
    print("Diagnostics:", report.result_bundle.path)
```

Other operations raise `api.PatchHarborError` for known tool failures. Its
`reason: FailureReason` and `error_kind: ErrorKind` are machine-readable; its
optional `run_report` and emergency-diagnostics fields retain diagnostic data.
No string-parsed console output is needed. Normal nonzero `run()` exits instead
return `ScriptResult(success=False, exit_code=...)` (success is a property).
Invalid Python arguments raise `TypeError`/`ValueError` before Core work. Native
I/O failures and unexpected exceptions are not broadly caught/disguised. An
interrupt during execution is handled by Core's process-tree cleanup; a
`KeyboardInterrupt` outside that boundary can propagate. No API function calls
`sys.exit` or installs/replaces signal handlers.

`RunReport.process_exit_code` and its JSON/document serializers retain the old
wire contracts for CLI/adapters; application code should prefer semantic facts.
No new error-class hierarchy reinterprets existing categories.

## Output and observation

No output is sent to `sys.stdout` or `sys.stderr` by default. No implicit stdin
is read. Raw execution logs in Apply Result Bundles remain complete even without
an output consumer. Callers request streaming explicitly:

```python
import sys
from patchharbor import api

with open("entrypoint.bin", "wb") as raw_log:
    report = api.apply(
        repository=repo,
        output=api.OutputStreams(text=sys.stdout, raw=raw_log),
    )
```

`text` receives decoded, newline-normalized **merged** stdout/stderr from the
child. Separate child stdout/stderr are not available from the current Core.
`raw` receives the exact merged bytes. `warnings` is a separate text sink;
`on_warning` receives warning strings. Sinks stay caller-owned and are not closed.
They are flushed as data arrives; text/raw delivery can occur on the reader
thread. Sink failures are reported under the existing execution-failure priority:
a prior timeout, interruption or nonzero child exit keeps its primary status.
A failed optional raw mirror cannot stop the mandatory Apply log from being
recorded. No automatic unbounded
`StringIO` buffer is allocated by the facade. Existing Core capture of Apply
logs for the Result Bundle remains unchanged, so this is not a bounded-memory
guarantee for an entire Apply. Explicit sink contents are not console-sanitized.

`observer` receives `ActivityEvent`, `RequestStarted`, `RepositoryResolved`, and
`ScriptPrepared`. Full identifiers are retained. `ScriptPrepared.messages`
contains the complete parsed MESSAGE pairs, not runtime program output. Event
records are immutable. Activity phase/message wording is diagnostic and may
evolve; do not use it to authorize work or implement a state machine. Observation
is request-local; a nested API call must explicitly supply its own observer and
the previous scope is restored. Observer `Exception`s are best effort and do not
replace an operation; `BaseException` is not swallowed. Observers must not mutate
the repositories, files, or configuration they are observing.

## Explicit script runner

```python
from io import StringIO
from patchharbor import api

# On Ubuntu/Bash. Windows source must be a valid native PowerShell script.
result = api.run(StringIO("# PATCHHARBOR\nprintf 'hello\\n'\n"), cwd=repo)
assert result.success
```

`source` can also be a script/ZIP file or a directory. Multiple valid directory
candidates require `select_candidate(candidates)` returning one of the supplied
`DirectoryCandidate` objects; no input prompt is created by the library. The
Core still validates the selection and input. `run` retains the legacy fs-run
contract: no automatic repository Result Bundle and no registration requirement.
The CLI owns human directory selection, `--log` formatting and temporary log
lifecycle; a Python caller uses explicit `OutputStreams` instead.

## Public types

Import all documented types from `patchharbor.api`, including `RepositoryId`,
`RepositoryPath`, `GitObjectId`, `GitObjectFormat`, `RepositoryContext`,
`RegistryListResult`, `RegistryRepository`, `RegistryStatus`, `ConfigurationResult`,
`UnregisterResult`, `BundleResult`, `ScriptResult`, `OutputStreams`, `RunReport`,
`RunTiming`, `RunOperation`, `PrimaryResult`, `PrimaryResultKind`, `RunToolError`,
`ResultBundleResult`, `ResultBundleStatus`, `DirectoryCandidate`, `PackageFile`,
and the events/callback aliases. Construct configuration/repository/run results
only by calling operations; read their documented facts. Implementation imports
and undocumented construction/serializer helpers are not an additional public
extension surface. GUI, async, transport and plugin frameworks are out of scope.


## CLI and Watcher integration

The main `patchharbor` CLI now calls this API for every operation, including
configuration, registry, context, bundles, Apply/Dry-Run, automatic Apply and
fs-run. It passes its observer and sinks explicitly. JSON serializers,
exit-code mapping, terminal styling, interactive selection and temporary `--log`
files remain adapter concerns. The separate watcher calls `repositories()` at
startup and runs a private worker that calls `apply_next()` directly, preserving
its process and stop semantics. It never requests a global configuration or
resolves configuration against the service's current working directory.


## Watcher process boundary

Startup checks the registry and subscribes to Core's targets and control paths.
Existing bundles receive the same initial five-second quiet period as later
changes. Each worker starts the current installation's Python interpreter with
`-m patchharbor_watcher.worker`. Its bounded, versioned stdin request contains
full physical Exchange observations, never an explicit candidate path. The
worker calls `api.apply_next(exchanges=...)` and preserves automatic no-retry
semantics. Empty scope remains empty. Malformed requests fail before Core.

The private response adds `watcher_progress` to a copy of the Apply envelope.
The parent uses its structured status and lock, never a guessed error message,
to drain consumed work or await readiness. Raw script output remains in the
Result Bundle. Public CLI and persisted Result schemas remain unchanged.

The main thread receives events while one helper thread waits for the existing
worker process. The stop controller wakes an idle native wait. Once stopped,
no further worker starts; an active worker is awaited. Existing OS/group/service
signal delivery and Core process-tree cleanup retain their interruption role.
No extra process groups, services or dependencies are introduced. This remains
a synchronous Core API. Native backend failure is explicit, without polling
fallback; configuration repair and root restoration are driven by filtered events.


## Installation and scope of support

Use Python 3.12 or newer. For a normally installed API, install the repository or
built wheel into that application's own environment, for example:

```bash
python -m venv .venv
.venv/bin/python -m pip install /path/to/patch-harbor
.venv/bin/python -c "from patchharbor import api; print(api.DEFAULT_TIMEOUT_SECONDS)"
```

On Windows, use `.venv\Scripts\python.exe` instead. A `uv tool` or `pipx`
installation isolates CLI applications; it does not make their imports available
in an unrelated Python interpreter. No import-time registration, configuration
write, console initialization or network access is performed by the API.

The distribution includes inline annotations (`patchharbor/py.typed`) and a copy
of this document at `share/patchharbor/python-api.md`. Import public types from
`patchharbor.api`, even when their defining module is internal. New optional
parameters and additional result fields may be added compatibly. The stable
contract does not promise diagnostic prose, event ordering, concurrent mutations
of the same repository, or an asynchronous cancellation interface. Existing Core
locks and safety checks remain authoritative.

Release verification covers direct Python calls, CLI/API parity, the separate
Watcher worker, actual script output and Result Bundles, plus installed-wheel
imports and execution. The full platform release gates still determine whether
a particular release commit is ready to use; this document is not a CI receipt.

Weitere Betriebs- und Abnahmedetails: [Ereignis-Watcher](watcher-events.md).

## Packing explicit prepared contents

```python
from patchharbor import api

packed = api.pack_patch(
    "prepared-contents", reference_bundle="received-result.zip",
    entrypoint="run.sh", output_directory="existing-output",
    modes={"scripts/new-tool.sh": 0o755},
)
print(packed.path, packed.package_sha256, packed.reference_sha256)
```

Exactly one of `output` and `output_directory` is required; an explicit filename
must end in `.zip` plus the verified reference suffix. The output directory must
already exist outside the content tree. Existing targets are never replaced,
including targets created by concurrent requests. No registry, Git, shell,
build, installation, tests or network is used by this operation.

`PatchPackResult` is frozen and contains an absolute `path`, a request-local
UUID-v4 `package_id`, UTC `created_at`, complete `validation` with reference scope
and matching binding, and an immutable `warnings` tuple. `package_sha256`,
`package_size` and `reference_sha256` derive from that same validation evidence.
The source and reference are captured and checked for known changes. The actual
written archive is validated before exclusive publication. There are no automatic
stability retries. An error before publication preserves its shared failure
category; formal argument errors remain `TypeError`/`ValueError`.

After confirmed publication, optional cleanup failures retain the entire result
with warnings naming any remaining owned path. Success does not require reopening
the final file: an external watcher may already have moved it. This evidence does
not assert shell syntax, executed tests, authenticity or unchanged target state
at a later Apply. See [pack details](pack.md).


## Python-only PYZ access

The public API is shared with the built Core-only PYZ. Before importing it,
perform the stdlib descriptor/trust precheck described in
[runtime bootstrap](runtime-bootstrap.md) and privately prepare the selected
artifact. `scripts/pyz_bootstrap.py` supplies the reviewed example
`import_api(prepared)`: it retains the checked path, rejects preloaded foreign
PatchHarbor modules, and never clears module caches to fake a version switch.
Afterwards use the returned `api.inspect_patch`, `api.validate_patch` and
`api.pack_patch` normally. Full native reference validation remains separate
from bootstrap checks; no installation or subprocess is needed for these calls.
Result-3 production uses the same shared Core and request-local resource capture.


## Reader-first Result 3 (PP-05A)

`validate_patch(..., reference_bundle=...)` and `pack_patch` now use the same
full reader for Result formats 1, 2 and 3. The new format verifies its PYZ as
strict data, without importing it. Public signatures/scopes are unchanged;
corrupt references retain source-error category 4. A private repository-only
diagnostic fallback is never a successful full reference or a `pack` input.
See [Result format 3](result-format-3.md). Production uses this format from PP-06B;
legacy reader schemas and public validation scopes remain unchanged.
