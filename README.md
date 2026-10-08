# PatchHarbor 1.3.0

PatchHarbor transfers work between a development environment and a local Git
repository using verified ZIP packages. A **Result Bundle** describes the actual
repository state. A **Patch package** is bound to that repository and exact state;
Apply checks the binding before writing its payloads and running its entrypoint.

- `bundle` captures a repository; `apply` applies an explicitly prepared package.
- `pack` builds a patch from chosen contents and a Result reference.
- `inspect` and `validate` check packages without executing their code.
- The optional watcher runs Apply after filesystem changes in Exchange have
  settled for five seconds.
- Results normally carry an installation-free **Core-PYZ, without the watcher**.
  CLI and Python callers use the same public API.

This source tree uses version **1.3.0**. The version string, an installed version,
and a published release are different facts. Implementation and acceptance
evidence, including outstanding platform gates, are recorded in the
[PYZ/PACK plan](planning/pyz-pack/commit-plan.md) and
[test matrix](planning/pyz-pack/test-matrix.md); a development checkout is not
itself a release announcement.

## Requirements and installation

Python **3.12 or newer** is required. Repository operations also require Git;
executing a patch requires its declared Bash or PowerShell interpreter.
Static `pack`, `inspect` and reference-based `validate` need neither Git nor
the target shell. The Core has no third-party runtime dependencies.

For the normal CLI **and watcher**, install a reviewed wheel or source checkout.
For example, with an existing Python 3.12+ and pipx:

```bash
pipx install --python python3 /absolute/path/patchharbor-1.3.0-py3-none-any.whl
patchharbor --version
patchharbor --help
```

The wheel path is an artifact you obtain and verify; this command does not assume
that version 1.3.0 has been published on a package index. **pipx is optional**:
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
   patchharbor apply --dry-run
   patchharbor apply
   ```

5. Read the new Result and execution log. A Dry Run checks the package; it does
   not prove a successful actual Apply. A failed Apply may leave changed files
   or completed commits, which become the basis of the next patch.

The entrypoint defines the target project's tests, commits and optional push.
The watcher does not invent that policy. Do not run a second watcher or another
Apply orchestrator for the same repositories.

## Build and check a patch

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
explicitly apply. `patch.json` and `PATCHHARBOR_META` are generated/reserved.
Pack validates the final ZIP and its complete Result binding, but does not prove
shell syntax, target tests, replay eligibility or a future Apply.

The same operation is available to Python callers:

```python
from patchharbor import api

packed = api.pack_patch(
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

New Results use **Format 3**. When runtime embedding succeeds, they contain
exactly one `runtime/patchharbor-<version>.pyz`. A valid `unavailable` status
instead contains runtime metadata and a warning, with no executable artifact.
Legacy Format-1/2 Results remain readable.

Use the executable bootstrap from the trusted Result's handoff, or a separately
reviewed copy of `scripts/pyz_bootstrap.py`, to assess and prepare its exact PYZ.
After source trust and integrity checks, Python 3.12+ can run it directly:

```bash
python -I -S -B /private/runtime/patchharbor-VERSION.pyz inspect /work/patch.zip --json
python -I -S -B /private/runtime/patchharbor-VERSION.pyz validate /work/patch.zip \
  --reference-bundle /work/result.zip --json
python -I -S -B /private/runtime/patchharbor-VERSION.pyz pack /work/contents \
  --reference-bundle /work/result.zip --entrypoint run.sh --output-dir /work/ready
```

Use the actual prepared path/version, not an arbitrary neighboring archive.
This requires no pip, venv, network or host installation. The PYZ contains Core
operations, **no watcher or service installer**. Git/apply operations still have
their normal repository and interpreter requirements.

If the runtime is absent or technically unusable, use the
[documented previous handoff procedure](docs/runtime-bootstrap.md#mandatory-previous-procedure)
with trusted compatible tools and record the reason. A semantic validation
failure or invalid binding remains an error; fallback is not a bypass.
The [bootstrap guide](docs/runtime-bootstrap.md) covers trust, extraction,
Python-only API use and legacy wheels.

## Manual operation and watcher

Manual `patchharbor apply` selects an eligible patch only for the registered
repository containing the current working directory. An explicit path,
`patchharbor apply /path/to/patch.zip`, selects the repository from its manifest
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
one-second polling; `--poll-interval` is obsolete. Results may trigger a scan
but are never executed as patches. Repeated identical `no_candidate` messages
are suppressed. Failed unchanged packages are not automatically retried.

Native event delivery on network/virtual filesystems depends on that filesystem;
there is no silent polling fallback. See [watcher behavior](docs/watcher-events.md).
Termux/Android should use manual Apply; a reliable Android background service
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

Result names follow `<Repository>_Result_<HHMMSS>_<MMDD>_<ID6>.zip`; patch names
follow `<Repository>_Patch_<HHMMSS>_<MMDD>_<ID6>.zip` (UTC). Filenames are not
repository-binding evidence. To use a transport suffix such as `.zip.txt`:

```bash
patchharbor configure bundle-suffix .txt
patchharbor configure bundle-suffix --clear
```

These are alternative settings, applied from the registered repository. The
`bundle_suffix` is naming metadata in a fresh Result's `context.json`, not a field
in `patch.json`. Content remains ZIP. Old and new names may coexist.

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

These limits apply together: 250,000 files does not allow unlimited total bytes.
Outer Result ZIP64 is supported. The larger outer limit does not enlarge pack's
scan budget or the runtime archive budget. See [pack limits](docs/pack.md#grenzen-und-nachweise)
and [runtime limits](docs/runtime-bootstrap.md).

For a failed Apply, inspect `logs/run.json` and `logs/execution.log` when present.
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
does not replace repository-bound Apply.

## Documentation and development

- [Installation and updates](docs/install-and-update.md)
- [Repository configuration, archives, retries and permissions](docs/repository-workflow.md)
- [Troubleshooting](docs/troubleshooting.md)
- [Pack](docs/pack.md), [examples](docs/pack-examples.md), [Python API](docs/python-api.md)
- [Runtime bootstrap](docs/runtime-bootstrap.md), [Result 3](docs/result-format-3.md)
- [Watcher](docs/watcher-events.md), [CIFS publication](docs/result-publication-cifs.md)
- [Development tests and manual CI policy](docs/test-parallelism.md)
- Joint requirements: [main specification](spec/SPECIFICATION.md) and
  [PYZ/PACK extension, revision 3](spec/SPECIFICATION_EXTENSION_PYZ_PACK.md)
- [Implementation and acceptance record](planning/pyz-pack/commit-plan.md)

For development, install `.[dev]` in a dedicated environment and run
`python tools/run_tests.py --suite all`. Development and Apply use full parallel
gates. GitHub CI is manual and started only by the project owner. Local tests
do not substitute for native Windows acceptance or release publication.
For available options, use `patchharbor --help`, `patchharbor COMMAND --help`
and `patchharbor-watcher --help`.
