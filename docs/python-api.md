# PatchHarbor Python API (development toward 1.2.0)

Use `from patchharbor import api`. This is the only supported public Python
namespace; implementation modules remain internal. The documented names and
value fields form the proposed 1.2.0 compatibility surface. The package remains
1.1.1 during development; the compatibility/release gate is a separate step.
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
| `configuration()` | `configure show` | `ConfigurationResult` |
| `configure_exchange_directory(directory)` | `configure exchange-directory` | `ConfigurationResult` |
| `configure_bundle_suffix(suffix)` | `configure bundle-suffix` | `ConfigurationResult` |
| `configure_archive_directory(name)` | `configure archive-dir` | `ConfigurationResult` |
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

An empty suffix clears it; an empty archive name disables archival. Registry
operations use the existing user configuration and registry, not an independent
API store. API calls do not install a watcher or implicitly register repositories.

## Apply selection and safety

With no explicit patch, `apply(repository=...)` selects for that registered
repository (subdirectories are allowed). Omitting repository means current
directory, exactly like manual CLI Apply. A failed identity is retryable only
under the same existing state rules. An explicit patch selects by its manifest
repo_id, not by cwd. Combining `patch` with `repository` is rejected: the latter
is a discovery scope, not an extra target constraint that could be ignored.

`apply_next()` performs exactly one global automatic poll. It never retries a
failed identity; the existing Core owns selection, replay, lock, revalidation,
recovery and publication together. No separate select-then-apply token or stale
validated package is exposed. The watcher is not migrated in this package.

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


## CLI migration status

The main `patchharbor` CLI now calls this API for every operation, including
configuration, registry, context, bundles, Apply/Dry-Run, automatic Apply and
fs-run. It passes its observer and sinks explicitly. JSON serializers,
exit-code mapping, terminal styling, interactive selection and temporary `--log`
files remain adapter concerns. The separate watcher still invokes that CLI in a
subprocess until API-3; this already reaches the API indirectly without changing
its process or stop semantics in this package.
