# Installation-free PYZ bootstrap and legacy handoff


## Stdlib-only PYZ bootstrap and embedded executable

`scripts/pyz_bootstrap.py` is a reviewed example tool, not another Core validator
or a public application subcommand. It has no import-time PatchHarbor dependency.
Use a trusted copy of the helper and an explicitly trusted Result. A digest
copied from an unknown archive does not authenticate its sender. The current
production writer emits Format 3 with exactly one Core-PYZ. Legacy 1/2 references
retain their versioned previous path. Upgrading repository files does not restart
or replace an already running older global installation.

Read-only assessment and optional single-file preparation:

```text
python -I -S -B /trusted/tools/pyz_bootstrap.py /exchange/result.zip
python -I -S -B /trusted/tools/pyz_bootstrap.py /exchange/result.zip --trusted-source-sha256 <full-trusted-result-sha256> --prepare-in /private/new-pyz-runtime
```

The precheck bounds archive metadata before `ZipFile` allocation, rejects unsafe
paths, duplicate/special members, and verifies the selected runtime metadata and
artifact descriptors, size/hash and Python requirement. It never guesses the
first `.pyz`, imports archived code, installs a package or extracts the snapshot.
`scope=runtime_descriptor_precheck` and `full_reference_valid=false` distinguish
these data checks from the full native reference reader. Legacy and unavailable
runtimes select an explicit documented fallback. Corrupt data is not success.

Preparation requires Python >=3.12 and a new private directory. Exactly the
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
The resulting object is the ordinary public API, including `pack_patch`.

PP-05A enables the native Format-3 reader. PP-05B embeds the complete reviewed
stdlib program in the canonical `CHAT_INSTRUCTIONS.md`: save that executable
code from the actual trusted Result handoff, assess and prepare its exact PYZ,
then pack/inspect/validate against that same original reference. No repository
helper or installed Core is required to start. The functional fixture test uses
the built handoff resource in a fresh stdlib-only process, and proves that a
successful descriptor precheck cannot bypass a corrupt repository snapshot.

Metadata fields, capabilities, artifact descriptors and provenance are closed;
unknown future Results are rejected, while legacy Formats 1/2 select their own
path. The old wheel helper reports `result_format_requires_pyz_bootstrap` for
valid Format 3 without accessing wheel fields or installing anything. Production
emits Format 3 from PP-06B. Its E-10 test obtains the executable helper from the
first actual Result produced by a real installation, then performs pack, full
reference validation and regular Apply through the selected PYZ.

## Legacy wheel bootstrap

The bootstrap is an explicit consumer action, separate from read-only inspection.
Finding a wheel in a Result never installs or imports it. A digest proves byte
identity; obtain source trust through an already trusted channel, not a digest
copied from the same unknown archive. A venv separates installations, not hostile
code from the host. User permissions and project rules remain authoritative.

## Prerequisites and executable example

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
`api.inspect_patch(patch)` and `api.validate_patch(patch, reference_bundle=result)`.
Do not import into a different chat interpreter or register an invented Git
repository from extracted `base/`. These calls remain read-only and never prove
tests, CI, sender trust, replay permission or a future Apply.

## Mandatory previous procedure

Missing, unavailable, damaged, incompatible, untrusted or technically unusable
runtime means use the existing development and handoff process. Document the
reason and actual tools/checks, without inventing native success. First validate
the original Result's safe outer ZIP and mandatory files, snapshot inventory,
Git blob IDs/untracked SHA, context/run consistency and complete binding. Read
staged/unstaged deltas and actual failure/partial-progress logs. Develop from
that state and build one safe format-1 patch with one entrypoint, full `repo_id`,
`base_commit`, `state_fingerprint` and `fingerprint_algorithm` from the reference.

Use an already trusted compatible Core parser, or the established ZIP, payload,
hash and binding checks when the new native operations are unavailable. The
example helper uses those existing parsers and returns `method=previous_handoff`
and `native_validation=false`. A semantic rejection is not a technical failure
and does not permit fallback around invalid paths, corrupt mandatory data or a
binding mismatch. A missing trustworthy repository proof still blocks a patch.

For a defect isolated to the reserved runtime namespace, the repository-only
reader retains every non-runtime requirement. It does not weaken the public
native reader, archive/recovery policy or safe outer ZIP checks. Original bytes
and their complete SHA are retained; `full_reference_valid=false` distinguishes
this limited receipt from valid full format-2 evidence. Never silently repair,
downgrade or repackage the reference to obtain apparent native success.

Open and check the final patch, payload hashes, size and SHA after all edits.
Any byte change requires a new validation. Deliver exactly one canonical ZIP;
only authorized backups may copy those same bytes. An external backup failure
does not justify another patch. The real registered Apply independently rechecks
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
preparation is separate. `tests/test_handoff_commit_sequence.py` uses real Apply,
Git commits and a private local bare remote for zero/one/multiple commit cases.
Its gate commands are fixture checks, not nested runs of the project suite.
Both are selected by existing blocking packaging/E2E gates. Native Windows/CI
evidence must come from actual runs, never from these Linux development results.

## Current project acceptance policy

For development of PatchHarbor itself, each commit state is checked with the
full parallel suite in Development and Apply. Only Christian starts the manual
GitHub workflow. Neither the development loop nor a handoff entrypoint dispatches
CI; the old five-bundle schedule does not apply. Other target projects choose
their own gates. No test or simulated transport is presented as native Windows
or real CIFS evidence. A started workflow is not a completed acceptance run.

The historical RIV implementation and its past CI handoffs remain documented in
[its own plan](../planning/runtime-inspect-validate/commit-plan.md). Those records
are not instructions to resume that completed plan. The current PYZ/PACK plan
requires final artifact hashes and actual local, Apply, native and CIFS evidence
for the concrete final state; outstanding proofs remain explicitly open.
