# PatchHarbor 1.2.0 – public Python API

Use `from patchharbor import api`. This is the only supported public Python
namespace; implementation modules remain internal. The documented names and
value fields form the supported 1.2.0 compatibility surface. Within the 1.x
series, fixes and compatible additions preserve documented calls and result
semantics. Exception: this explicitly approved repository-local configuration
revision of the 1.2.0 development line supersedes the earlier global-setting
semantics. It has no migration or compatibility fallback; the method names stay,
but configuration calls now require a registered target repository.
Additional enum values or diagnostic event wording must not be treated as an
exhaustive state machine. Private modules and undocumented helpers remain free
to evolve.
There are no new runtime dependencies. Install PatchHarbor into the Python
environment of the calling program; installing the CLI with a tool manager does
not install it into every other Python environment.

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
| `bundle(repository=".", output_directory=None)` | `bundle` | `BundleResult` |
| `apply(patch=None, repository=None, dry_run=False, ...)` | manual `apply` | `RunReport` |
| `dry_run(patch=None, repository=None, ...)` | `apply --dry-run` | `RunReport` |
| `apply_next(dry_run=False, ...)` | automatic global Apply | `RunReport` |
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
worker process for each poll; the library itself never starts a polling loop.

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

Startup checks the registry only. Every `apply_next()` reloads local settings
inside Core. Existing repositories with valid config and unset Exchange are
skipped, as are missing registered repository paths. Invalid/missing local config
in a live repository, conflicting identity, or an unavailable configured Exchange
makes the poll fail before execution, without repair. A later poll sees deliberate
manual corrections. An empty registry has no candidates, not a setup error.
Revalidation is no reservation: automatic Apply rechecks configuration, state,
locks and filesystem objects at its existing mutation boundary.

Each watcher poll starts the current installation's Python interpreter with
`-m patchharbor_watcher.worker`. That private worker calls `api.apply_next()`
without visible output sinks or observers and serializes the returned report
using the existing Apply JSON envelope. The operational log schema, deduplication
of idle/error records, global repository scope and automatic no-retry policy
are unchanged. Raw script output remains in the Result Bundle, not in the JSON
pipe. There are no new services, runtime dependencies, CLI flags, process groups,
or signal handlers. The parent still stops between polls and waits for an active
poll; existing OS/group/service signal delivery and Core process-tree cleanup
remain responsible for interruption of that poll. This is not an in-process
asynchronous or cancellable API.


## Installation and scope of support

Use Python 3.12 or newer. For an application that imports PatchHarbor, install the
repository or built wheel into that application's own environment, for example:

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
