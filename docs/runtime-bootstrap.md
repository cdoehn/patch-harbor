# Installation-free PYZ bootstrap and safe handoff fallback

The former wheel bootstrap and its installation commands below are historical.
RF-06B removed `scripts/runtime_bootstrap.py`; those old commands are not available in this checkout. Use the reviewed PYZ bootstrap
in `tools/pyz_bootstrap.py` and [current Result guidance](protocol-2.md).
The uv proof now installs the normal distribution wheel and uses its Core-PYZ.


## Stdlib-only PYZ bootstrap and embedded executable

`tools/pyz_bootstrap.py` is a reviewed example tool, not another Core validator
or a public application subcommand. It has no import-time PatchHarbor dependency.
Use a trusted copy of the helper and an explicitly trusted Result. A digest
copied from an unknown archive does not authenticate its sender. The current
production writer emits Format 4 with runtime metadata 3 and exactly one
Core-PYZ when embedding succeeds. A valid `unavailable` Result instead contains
metadata and a reason, without executable bytes. Old Result 1/2/3, old Patch
formats and runtime wheels are historical evidence, not accepted references.
Upgrading repository files does not restart or replace a running installation.

Result snapshots support up to 250,000 stored repository files, with ten further
outer ZIP slots for auxiliary data. The Core reader and stdlib bootstrap accept
single-disk ZIP64 Results needed above the classic 65,535-member boundary. The
bootstrap checks ZIP64 directory counts and offsets before allocating ZIP members.
All byte budgets and the 1,000-member inner runtime limit still execute. A producer
or reader entry-limit failure reports the actual count and limit without retrying.

Read-only assessment and optional single-file preparation:

```text
python -I -S -B /trusted/tools/pyz_bootstrap.py /exchange/result.zip
python -I -S -B /trusted/tools/pyz_bootstrap.py /exchange/result.zip --trusted-source-sha256 <full-trusted-result-sha256> --prepare-in /private/new-pyz-runtime
```

The precheck bounds archive metadata before `ZipFile` allocation, rejects unsafe
paths, duplicate/special members, and verifies the selected runtime metadata and
artifact descriptors, size/hash and Python requirement. It also checks the inner
PYZ inventory, recipe and producer identities, both canonical start files and
their agreement with the selected requirement before import. It never guesses the
first `.pyz`, imports archived code, installs a package or extracts the snapshot.
`scope=runtime_descriptor_precheck` and `full_reference_valid=false` distinguish
these data checks from the full native reference reader. An unavailable or
technically unusable runtime has a documented fallback for otherwise supported
repository evidence. An unsupported Result format is not a runtime-only failure
and never triggers execution of a legacy wheel. Corrupt data is not success.

Stable input capture compares the same file identity, size and write time across
path and handle observations. On Windows before 3.12 it obtains creation and
change time separately from the owned native handle; newer stat fields retain
their existing semantics. Native observations bracket the older fstat call.
Reparse inputs and redirected parents are rejected without `Path.is_junction`;
parent identities are checked again and owned handles are closed on failures.
Differing meanings of path and handle `ctime` must not reject unchanged files.
These checks add no retry,
identity fallback or exception to the trusted digest requirement.

The standard build uses the exact closed requirement `>=3.10`.
The current data validator and helper also recognize the existing closed
`>=3.12` recipe variant; this does not restore old Result formats. Unknown variants are not inferred from a product version. No original
artifact is relabeled. Unknown requirements and rehashed mixed variants remain
invalid. Native 3.10/3.11 acceptance remains a separate gate.
A new private directory is required. On Windows it is created atomically with
a protected inheritable DACL for the effective user and administrators, including
on older Python patch versions. Existing paths and ACLs are not repaired. Exactly the
captured hash-verified PYZ is copied there, with no pip, venv, network or cache.
Then use the returned absolute path:

```text
python -I -S -B /private/new-pyz-runtime/patchharbor-<version>.pyz inspect /exchange/patch.zip --json
python -I -S -B /private/new-pyz-runtime/patchharbor-<version>.pyz validate /exchange/patch.zip --reference-bundle /exchange/result.zip --json
python -I -S -B /private/new-pyz-runtime/patchharbor-<version>.pyz pack /private/contents --reference-bundle /exchange/result.zip --entrypoint run.sh --output-dir /private/output --json
```

The actual descriptor supplies `<version>`; do not hardcode it or use an arbitrary
neighboring PYZ. Interpreter switches precede the archive. They reduce ambient
imports/site/bytecode effects but are not a security sandbox. The ordinary
`python archive.pyz ...` form remains supported. Inspect/validate/pack require no
Git or shell; other Core operations retain their normal Git/registry/interpreter
requirements. The PYZ contains no Watcher.

In a Python-only environment, load the trusted helper, call `assess`, `prepare`,
and then `import_api(prepared)`. It verifies the selected artifact again and
refuses any already loaded `patchharbor` module from another origin. It never
clears `sys.modules`; use a fresh process after a conflict or failed partial
import. The checked path stays on `sys.path` for later lazy imports/resources.
The resulting object is the ordinary public API, including `pack_task`.

`tools/pyz_bootstrap.py` is the sole maintained program and is carried as a
separate file beside the Result's `CHAT_INSTRUCTIONS.md`. Read the full environment
from `environment.json`; its version-3 helper descriptor records path, size and
SHA-256. Review origin/code before using the actual helper from that trusted Result.
A digest carried in the same untrusted archive does not authenticate its author.

`python scripts/render_chat_bootstrap.py --check` checks the helper's literal
capabilities and the separate documentation reference without executing code.
`--write` refreshes only those literals; Markdown never receives a program copy.
Wheel, sdist and PYZ carry the same source-normalized helper. Producer identity
pins its resource bytes together with the template before Execute can mutate them.
An optional runtime failure may retain independently verified mandatory resources;
a missing or changed helper cannot silently use another installation.

Current capabilities are Task `[2]`, Result `[4]` and `inspect_task`,
`validate_task`, `pack_task`. Unknown capabilities remain invalid. Existing 2.0
handoff pairs (environment 2) stay readable; new handoffs use environment 3.
Readers unaware of environment 3 reject it explicitly. The E-10 acceptance test
starts with the helper from an actual Result, packs and fully validates against
the original Result, then performs regular Execute through that exact PYZ.
The native snapshot check still rejects corrupt repository evidence after a
successful descriptor-only precheck. See [the complete handoff contract](chat-handoff.md).

## Historical legacy wheel bootstrap

The following wheel procedure and prerequisites document the former RIV
workflow. They do not require supporting pre-1.4.0 Results, installing wheels
as a fallback, or retaining the old helper. The current PYZ procedure above
and the safe handoff procedure below remain the supported paths.

The bootstrap is an explicit consumer action, separate from read-only inspection.
Finding a wheel in a Result never installs or imports it. A digest proves byte
identity; obtain source trust through an already trusted channel, not a digest
copied from the same unknown archive. A venv separates installations, not hostile
code from the host. User permissions and project rules remain authoritative.

### Historical prerequisites and executable example

Use an independently reviewed copy of `scripts/runtime_bootstrap.py` with a
matching, already trusted Core installation. This repository tool reuses the
existing bounded ZIP, Result and wheel readers and legacy patch parser. Its
private imports are not a new supported Core API. It is not a bootstrap program
automatically trusted because it was found inside a Result or its wheel.
If the reviewed helper or compatible trusted Core is absent, use the previous
procedure below with established local tools. Do not run unknown wheel code to
decide whether that same code is trusted.

First inspect only, using absolute paths outside the target snapshot:

```text
<trusted-python> -I -B /trusted/tools/runtime_bootstrap.py /exchange/result.zip
```

The helper checks safe outer paths/types/budgets, all mandatory repository data,
inventory/blob hashes, run/context consistency, full binding, then the runtime's
descriptors, metadata, canonical recipe and wheel RECORD. The profile rejects
`.pth`, foreign modules, launchers and runtime dependencies. No subprocess or
input code executes in this assessment. Runtime provenance is descriptive, not
a signature. Without an independently trusted digest installation is refused.

After source trust is established, one explicit attempt is:

```text
<trusted-python> -I -B /trusted/tools/runtime_bootstrap.py /exchange/result.zip --trusted-source-sha256 <full-trusted-result-sha256> --install-in /private/new-handoff-runtime --patch /exchange/final-patch.zip
```

`--install-in` must name a new directory outside the project; an existing or
symlink destination is refused. The helper captures verified immutable wheel
bytes, creates a venv without pip, and uses an existing local pip with `--python`
to target its explicit interpreter. A hash-pinned local requirements file,
`--no-index --no-deps --only-binary=:all: --no-cache-dir --require-hashes` and a
dry run check the complete `Requires-Python` condition before installation.
No installer, interpreter, dependency or source build is downloaded. A missing
pip/venv or unsupported installer selects fallback after one attempt. Logs stay
in the owned workspace. Remove only that owned workspace when finished.

The subprocess environment forwards a small platform allowlist, uses private
home/config/cache/temp directories and drops secrets, proxies, `PYTHONPATH` and
`PYTHONHOME`. Python runs with `-I`; import must resolve inside the new venv and
provide the expected API/version. Invoke the exact reported interpreter:

```text
<runtime-python> -I -m patchharbor.cli inspect /exchange/final-patch.zip --json
<runtime-python> -I -m patchharbor.cli validate /exchange/final-patch.zip --reference-bundle /exchange/result.zip --json
```

Windows uses `venv/Scripts/python.exe`; POSIX uses `venv/bin/python`. For API
usage run `from patchharbor import api` in that interpreter, then
`api.inspect_task(patch)` and `api.validate_task(patch, reference_bundle=result)`.
Do not import into a different chat interpreter or register an invented Git
repository from extracted `base/`. These calls remain read-only and never prove
tests, CI, sender trust, replay permission or a future Execute.

## Mandatory previous procedure

Missing, unavailable, damaged, incompatible, untrusted or technically unusable
runtime means use the existing development and handoff process for a supported
reference. An unsupported Result format does not qualify for this fallback. Document the
reason and actual tools/checks, without inventing native success. First validate
the original Result's safe outer ZIP and mandatory files, snapshot inventory,
Git blob IDs/untracked SHA, context/run consistency and complete binding. Read
staged/unstaged deltas and actual failure/partial-progress logs. Develop from
that state and build one safe format-1 patch with one entrypoint, full `repo_id`,
`base_commit`, `state_fingerprint` and `fingerprint_algorithm` from the reference.

Use an already trusted compatible Core parser, or the established ZIP, payload,
hash and binding checks when the new native operations are unavailable. The
historical wheel helper returned `method=previous_handoff` and
`native_validation=false`; these labels do not make unsupported data valid. A semantic rejection is not a technical failure
and does not permit fallback around invalid paths, corrupt mandatory data or a
binding mismatch. A missing trustworthy repository proof still blocks a patch.

For a defect isolated to the reserved runtime namespace, the repository-only
reader retains every non-runtime requirement. It does not weaken the public
native reader, archive/recovery policy or safe outer ZIP checks. Original bytes
and their complete SHA are retained; `full_reference_valid=false` distinguishes
this limited receipt from valid full Result evidence. Never silently repair,
downgrade or repackage the reference to obtain apparent native success.

Open and check the final patch, payload hashes, size and SHA after all edits.
Any byte change requires a new validation. Deliver exactly one canonical ZIP;
only authorized backups may copy those same bytes. An external backup failure
does not justify another patch. The real registered Execute independently rechecks
its repository state before mutation.

## Commits, diagnoses and evidence

Zero-commit bundles collect actual diagnostics in Result/logs without staging,
committing, pushing or advancing a plan. One or several commits are allowed;
each is a genuine sequential state with the project's gates before its commit.
Failures preserve proved partial progress for the next Result. There is exactly
one normal final push after the whole successful sequence, and no automatic tag.
PatchHarbor does not impose a project's test/CI policy in its Core.

`tests/test_runtime_bootstrap.py` executes real offline installation and reference
validation with a test-only process-family network denial guard. Build/fixture
preparation is separate. `tests/test_handoff_commit_sequence.py` uses real Execute,
Git commits and a private local bare remote for zero/one/multiple commit cases.
Its gate commands are fixture checks, not nested runs of the project suite.
Both are selected by existing blocking packaging/E2E gates. Native Windows/CI
evidence must come from actual runs, never from these Linux development results.

## Current project acceptance policy

For development of PatchHarbor itself, Development runs a documented,
change-focused parallel selection. Execute runs the full parallel suite before
every commit, including the final commit; there are no serial gates. Only
Christian starts the manual
GitHub workflow. Neither the development loop nor a handoff entrypoint dispatches
CI; the old five-bundle schedule does not execute. Other target projects choose
their own gates. No test or simulated transport is presented as native Windows
or real CIFS evidence. A started workflow is not a completed acceptance run.

The historical RIV implementation and its past CI handoffs remain documented in
[its own plan](../planning/runtime-inspect-validate/commit-plan.md). Those records
are not instructions to resume that completed plan. The active
[1.5.0 refactoring plan](../planning/1.5.0/commit-plan.md) requires final artifact
hashes and the applicable Development, Execute, native and CIFS evidence for the
concrete final state; outstanding proofs remain explicitly open.
