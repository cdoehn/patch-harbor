# PatchHarbor

[![Latest GitHub release](https://img.shields.io/github/v/release/cdoehn/patch-harbor)](https://github.com/cdoehn/patch-harbor/releases/latest)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue)](docs/install-and-update.md)
[![MIT license](https://img.shields.io/badge/license-MIT-green)](LICENSE)
[![Platforms: Linux and Windows](https://img.shields.io/badge/platforms-Linux%20%7C%20Windows-lightgrey)](docs/install-and-update.md)

**Let an AI coding assistant work on your local Git repository through verified ZIP bundles.**

PatchHarbor connects an assistant running elsewhere with a repository on your
Linux or Windows machine. Send the assistant a repository snapshot as a
**Result Bundle**; receive a **Task Bundle** containing code changes and an
entrypoint. PatchHarbor checks the bundle against the intended repository state,
executes it locally, and returns updated files and execution logs for the next
iteration.

Use it when your coding assistant cannot access the repository directly, or when
you want an explicit, reviewable handoff between development and execution.
The entrypoint defines the project's tests, commits and optional push.

[Install](#requirements-and-installation) · [Quick start](#quick-start) ·
[Monitor](docs/monitor.md) · [Python API](docs/python-api.md)

## How it works

1. **Export:** Run `patchharbor bundle` to capture the repository in a Result Bundle.
2. **Develop:** Give that bundle to the assistant so it can inspect the actual files and prepare changes.
3. **Transfer:** Pack a Task Bundle bound to that Result and place the verified ZIP in the local Exchange directory.
4. **Execute:** Run `patchharbor execute`, or let the watcher validate the bundle, write its payloads and run its entrypoint.
5. **Review:** Read the new Result Bundle and execution log before starting the next iteration.

## What you get

- **Verified handoffs:** `pack`, `inspect` and `validate` check package integrity and repository binding before execution.
- **Useful feedback:** Result Bundles contain repository snapshots, changes and execution diagnostics.
- **Manual or watched execution:** Use filesystem notifications or explicit polling for CIFS and other mounts without reliable notifications.
- **Live visibility:** `patchharbor monitor` displays repository and Exchange activity, a five-line event history, active entrypoints and bundle numbers in a read-only terminal UI.
- **Portable runtime:** Results normally include a Core-PYZ that compatible Python environments can use without installing PatchHarbor. The watcher comes with the full installation.
- **Python integration:** The public API supports verified snapshot reading, bundle creation and guarded execution for host applications.

### Version and compatibility

This checkout contains the **unpublished 2.0.0 release candidate**. The release
badge links to the latest published GitHub release; it is not a test-status badge
for this checkout. See the [2.0 integration guide](docs/version-2-integration.md)
before upgrading: Task and Result formats and the Python API have changed.

PatchHarbor requires **CPython 3.10+**. Official builds provide a wheel, sdist and
Core-PYZ, with a runtime manifest and checksums for complete releases. See
[runtime export](docs/runtime-export.md) and the [release procedure](docs/release-runtime.md).
The specialized [safe reference export](docs/safe-reference-integration.md)
supports Linux x86-64 with CPython 3.10–3.14.

## Requirements and installation

This development source requires Python **3.10 or newer**. Repository operations also require Git;
executing a patch requires its declared Bash or PowerShell interpreter.
Static `pack`, `inspect`, reference-based `validate` and the public snapshot
reader need neither Git nor the target shell. The Core has no third-party runtime dependencies.

For the normal CLI **and watcher**, install a reviewed wheel or source checkout.
For example, with an existing Python 3.10+ and pipx:

```bash
pipx install --python python3 /absolute/path/patchharbor-VERSION-py3-none-any.whl
patchharbor --version
patchharbor --help
```

The wheel path is an artifact you obtain and verify; this command does not assume
that any version has been published on a package index. **pipx is optional**:
a dedicated virtual environment is another installation route. Wheel and sdist
remain supported for normal installations; the PYZ replaces the runtime embedded
in new Results, not the installed watcher. See
[installation and safe updates](docs/install-and-update.md), especially if a
watcher is already running. Updating repository files alone does not upgrade it.

## Quick start

Use a local Git repository with an existing committed `HEAD`. Choose an Exchange
directory outside every registered repository. In a POSIX shell:

```bash
cd /absolute/path/to/repository
patchharbor register
patchharbor configure exchange-directory /absolute/path/to/exchange
patchharbor configure show
patchharbor bundle
```

Registration is needed once per local repository instance. Settings belong to
`.patchharbor/config.json` in that instance; there is no global Exchange fallback.
An existing registered repository with valid settings can start at `bundle`.
See [repository setup](docs/repository-workflow.md) for clones, moves, shared
Exchanges, old configuration migration and automatic archival.

1. Give the resulting ZIP to the developer or chat. Its `CHAT_INSTRUCTIONS.md`,
   `context.json` and `environment.json` contain the handoff and full binding.
2. Develop and test from that actual state. Prepare the payload files and an
   entrypoint, then use `pack` as below. A bundle may have zero commits for
   diagnosis, one commit, or several genuine sequential commit states.
3. Inspect the finished patch and publish exactly one complete ZIP in Exchange.
4. Let the existing watcher process it, **or**, in manual mode, run:

   ```bash
   patchharbor execute --dry-run
   patchharbor execute
   ```

5. Read the new Result and execution log. A Dry Run checks the package; it does
   not prove a successful actual Execute. A failed Execute may leave changed files
   or completed commits, which become the basis of the next patch.

The entrypoint defines the target project's tests, commits and optional push.
The watcher does not invent that policy. Do not run a second watcher or another
Execute orchestrator for the same repositories.

## Build and check a Task Bundle

Prepare an explicit contents directory containing only the desired payloads and
the entrypoint. The output directory must already exist outside that contents
tree. For example:

```bash
patchharbor pack /work/contents --reference-bundle /work/result.zip \
  --entrypoint run.sh --output-dir /work/ready --json
patchharbor inspect /work/ready/NAME.zip --json
patchharbor validate /work/ready/NAME.zip \
  --reference-bundle /work/result.zip --json
```

Replace `NAME.zip` with the path returned by `pack`. Windows targets may use a
PowerShell entrypoint such as `run.ps1`. The entrypoint must satisfy the existing
Bash/PowerShell marker contract; pack neither writes nor executes it.

Pack copies all permitted files in the chosen directory; it does not use
`.gitignore` to select a diff. Ordinary payloads are written into the repository
**before** the entrypoint runs. A diff is a payload that the entrypoint must
explicitly execute. `task.json` and `PATCHHARBOR_META` are generated/reserved.
Pack validates the final ZIP and its complete Result binding, but does not prove
shell syntax, target tests, replay eligibility or a future Execute.

The same operation is available to Python callers:

```python
from patchharbor import api

packed = api.pack_task(
    "/work/contents",
    reference_bundle="/work/result.zip",
    entrypoint="run.sh",
    output_directory="/work/ready",
)
print(packed.path, packed.package_sha256)
```

See the [pack contract](docs/pack.md), [working examples](docs/pack-examples.md)
and [public Python API](docs/python-api.md). A normal import uses the calling
interpreter's installation; an isolated CLI installation is not automatically
visible to a different Python environment. The verified PYZ bootstrap also
provides `import_api(prepared)` for API use without installing PatchHarbor.

## Use the runtime supplied in a Result

New Results use **format 4**, Task Bundles use **format 2**, and Execute JSON
uses **version 2**. When runtime embedding succeeds, a Result contains exactly
one `runtime/patchharbor-<version>.pyz` with runtime metadata format 3. A valid
`unavailable` status contains metadata and a reason, without executable bytes.

Version 2 rejects old Patch/Result formats and removed Python API names.
Generate a fresh Result from the actual repository after a deliberate upgrade;
do not relabel an old archive. `apply` remains a deprecated CLI alias for
`execute`. The independent `ScriptBundle` / `api.run_scripts` and `fs run` path
is deprecated and has no repository-state binding. See the
[protocol](docs/protocol-2.md) and [integration upgrade](docs/version-2-integration.md).

Use the executable bootstrap from the trusted Result's handoff, or a separately
reviewed copy of `scripts/pyz_bootstrap.py`, to assess and prepare its exact PYZ.
After source trust and integrity checks, Python 3.10+ can run it directly:

```bash
python -I -S -B /private/runtime/patchharbor-VERSION.pyz inspect /work/patch.zip --json
python -I -S -B /private/runtime/patchharbor-VERSION.pyz validate /work/patch.zip \
  --reference-bundle /work/result.zip --json
python -I -S -B /private/runtime/patchharbor-VERSION.pyz pack /work/contents \
  --reference-bundle /work/result.zip --entrypoint run.sh --output-dir /work/ready
```

Use the actual prepared path/version, not an arbitrary neighboring archive.
This requires no pip, venv, network or host installation. The PYZ contains Core
operations, **no watcher or service installer**. Git/execute operations still have
their normal repository and interpreter requirements.

If the runtime is absent or technically unusable, use the
[documented previous handoff procedure](docs/runtime-bootstrap.md#mandatory-previous-procedure)
with trusted compatible tools and record the reason. A semantic validation
failure or invalid binding remains an error; fallback is not a bypass.
The [bootstrap guide](docs/runtime-bootstrap.md) covers trust, extraction,
Python-only API use and the safe runtime-unavailable fallback. Its old wheel
procedure is retained as historical documentation.

## Manual operation and watcher

Manual `patchharbor execute` selects an eligible patch only for the registered
repository containing the current working directory. An explicit path,
`patchharbor execute /path/to/patch.zip`, selects the repository from its manifest
and still checks the full binding. `--output-dir` changes only the Result
destination. See [selection, retries and recovery](docs/repository-workflow.md#manual-workflow).

The watcher observes **all configured Exchanges of registered repositories**;
its working directory is not a repository filter. It has no Exchange argument.
Linux uses inotify and Windows uses ReadDirectoryChangesW. Start it in the
foreground with `patchharbor-watcher`, or install the optional Linux user unit:

```bash
patchharbor-watcher --install-systemd-user-unit
systemctl --user daemon-reload
systemctl --user enable --now patchharbor-watcher.service
```

Each Exchange root is scanned after five seconds without a relevant change.
Existing files receive an initial quiet period on startup. Reads and changes
inside existing subdirectories do not trigger scans. There is no idle
one-second polling in event mode; its old bare `--poll-interval` option remains invalid. Results may trigger a scan
but are never executed as patches. Repeated identical `no_candidate` messages
are suppressed. Failed unchanged packages are not automatically retried.

Native event delivery on network/virtual filesystems depends on that filesystem;
select polling explicitly for CIFS or other mounts without reliable notifications:

```bash
patchharbor watcher poll                 # default: 4 seconds
patchharbor watcher poll --interval 10   # custom interval, in seconds
patchharbor watcher poll --interval 0.5  # fractions are supported
```

The equivalent standalone command is `patchharbor-watcher poll`. Polling checks
immediately, then waits the configured interval after each completed check or
Execute. It refreshes registered Exchanges every cycle, runs one worker at a time,
and retains Core's binding, integrity, locking and replay checks. Stop it with
Ctrl+C. The monitor shows polling mode, interval and the next planned scan.
Use one watcher mode for a deployment; stop an existing watcher after its active
Execute finishes before switching. Polling needs the full wheel/source installation;
the Core-PYZ still excludes the watcher. There is no silent polling fallback.
See [watcher behavior](docs/watcher-events.md).
Termux/Android should use manual Execute; a reliable Android background service
is not part of the supported watcher contract. Windows supports the foreground
watcher; the systemd unit is Linux-specific.

### Publish only complete ZIPs

Five seconds of quiet is not proof that a download finished. Build and validate
the ZIP outside the watched root. If copying across filesystems, copy into a
staging subdirectory on the **Exchange filesystem**, finish and verify that copy,
then publish it with a same-filesystem atomic operation without overwriting an
existing file. An ordinary cross-filesystem move can become a partial copy.

`pack` performs its own exclusive, verified publication into an explicitly
chosen output directory. If its safe filesystem primitives are unsupported,
it fails instead of falling back to an unsafe copy. Choose one canonical final
ZIP and preserve its bytes and full SHA-256 during handoff.

Result names follow `<Repository>_Result_Bundle_<HHMMSS>_<MMDD>_<ID6>.zip`; patch names
follow `<Repository>_Task_Bundle_<HHMMSS>_<MMDD>_<ID6>.zip` (UTC). Filenames are not
repository-binding evidence. To use a transport suffix such as `.zip.txt`:

```bash
patchharbor configure bundle-suffix .txt
patchharbor configure bundle-suffix --clear
```

These are alternative settings, applied from the registered repository. The
`bundle_suffix` is naming metadata in a fresh Result's `context.json`, not a field
in `task.json`. Content remains ZIP. Old and new names may coexist.

## Snapshots, limits and errors

Results contain a full base snapshot **without Git history**, staged/unstaged
deltas and non-ignored untracked regular files. `.git`, local `.patchharbor`
metadata and ignored untracked files are excluded. Review Results before sharing:
there is no general secret detector.

| Resource | Limit |
| --- | --- |
| Stored repository files in one Result (base + untracked) | 250,000 |
| Outer ZIP entries, including auxiliary data | 250,010 |
| Input ZIP and each expanded outer member | 256 MiB each |
| Total expanded content, including inspected inner runtime content | 512 MiB |
| Pack contents scan (files and directories) | 10,000 nodes |
| Inner runtime archive | 1,000 entries; separate artifact/profile byte limits |

These limits execute together: 250,000 files does not allow unlimited total bytes.
Outer Result ZIP64 is supported. The larger outer limit does not enlarge pack's
scan budget or the runtime archive budget. See [pack limits](docs/pack.md#grenzen-und-nachweise)
and [runtime limits](docs/runtime-bootstrap.md).

For a failed Execute, inspect `logs/run.json` and `logs/execution.log` when present.
If Result creation itself fails, preserve the reported emergency diagnostics
directory. An entrypoint may already have committed or pushed: **missing Result
does not mean rollback**. Check the actual repository and logs before retrying;
after fixing the publication problem, `patchharbor bundle` captures its current
state. See [error codes and recovery](docs/troubleshooting.md), including
[Linux-to-Windows CIFS publication](docs/result-publication-cifs.md).

## Security and responsibility

PatchHarbor is not a sandbox. Entrypoints run with the current user's rights.
Hashes, repository ID, base commit and fingerprint check integrity and state;
they do not authenticate the package's author. Execute only trusted packages.
Payload replacement is atomic per file, not a package transaction: earlier
successful writes are not automatically rolled back.

PatchHarbor does not run target-project tests or create Git commits as an
independent Core policy. An authorized entrypoint can run tests, make zero or
several commits, and push according to that project's workflow. Static checks
and successful pack creation do not establish those execution results.
The explicit legacy `patchharbor fs run` script runner remains available; it
does not replace repository-bound Execute.

## Documentation and development

- [Installation and updates](docs/install-and-update.md)
- [Repository configuration, archives, retries and permissions](docs/repository-workflow.md)
- [Troubleshooting](docs/troubleshooting.md)
- [Pack](docs/pack.md), [examples](docs/pack-examples.md), [Python API](docs/python-api.md)
- [Runtime bootstrap](docs/runtime-bootstrap.md), [Task / Execute / Result protocol](docs/protocol-2.md)
- [Monitor](docs/monitor.md), [watcher](docs/watcher-events.md), [CIFS publication](docs/result-publication-cifs.md)
- [2.0 integration and upgrade](docs/version-2-integration.md), [release procedure](docs/release-runtime.md)
- [Development tests and manual CI policy](docs/test-parallelism.md)
- Joint requirements: [main specification](spec/SPECIFICATION.md),
  [PYZ/PACK extension](spec/SPECIFICATION_EXTENSION_PYZ_PACK.md) and
  [CPython extension](spec/SPECIFICATION_EXTENSION_CPYTHON_310_311.md)
- [Implementation and acceptance record](planning/pyz-pack/commit-plan.md)

For development, install `.[dev]` in a dedicated environment and run only a
change-focused parallel selection, for example
`python tools/run_tests.py -- tests/test_runtime_pyz.py`. Document the selection
and its results. Execute runs the full parallel suite before every commit with
`python tools/run_tests.py --suite all`, including the final commit of a bundle.
GitHub CI is manual and started only by the project owner. Local tests
do not substitute for native Windows acceptance or release publication.
For available options, use `patchharbor --help`, `patchharbor COMMAND --help`
and `patchharbor-watcher --help`.

Current [1.6.0 integration plan](planning/specroad-integration/commit-plan.md),
[behavior matrix](planning/specroad-integration/test-matrix.md) and
[delivery record](planning/specroad-integration/delivery.md) separate prepared
source, actual Execute and external acceptance.


## Export the installed Core runtime

```sh
patchharbor runtime export --output-dir /absolute/existing/output --json
python -I -S -B patchharbor-VERSION.pyz runtime export --output-dir /another/existing/output --json
```

This exports the running distribution's canonical PYZ without Git, a Result,
registration, network or build tools. It never replaces an existing file.
Unprepared source/editable trees report unavailable; build with
`python scripts/build_release.py --outdir dist` and install the wheel normally.
The public Python API is `api.export_runtime(output_directory)`.
Every release from 1.8.0 requires PYZ, wheel, built sdist, runtime-manifest.json
and SHA256SUMS. Version strings alone are not a publication or platform proof.
See [the release plan](planning/runtime-release/commit-plan.md) and main spec §44.

The read-only [Monitor](docs/monitor.md) observes registered repositories and Exchanges; run `patchharbor monitor`.

## Local test measurements

Start collection explicitly from a development checkout with the development
dependencies installed:

```bash
python tools/profile_tests.py run --modes baseline -- tests/test_selected.py
python tools/profile_tests.py report --phase setup --format markdown
python tools/profile_tests.py report --phase call --format markdown
python tools/profile_tests.py report --phase teardown --format markdown
```

Replace the selection with your actual test path or node ID. Worker selection
defaults to `auto`. Add `cprofile`, `memory` or Linux-only `strace` to `--modes`
only when you want that diagnostic overhead. The SQLite history and raw data
stay local under `build/test-profile/`; `--database` selects another local path.
No collector runs on import, during a normal user command, or in a separate
CI profiling job. Reports distinguish preparation, test body, cleanup,
measurement modes and unknown coverage. See [test diagnostics](docs/test-diagnostics.md).
