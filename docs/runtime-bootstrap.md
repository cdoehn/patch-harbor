# Verified offline bootstrap and previous handoff procedure

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

## PatchHarbor project CI at the handoff boundary

The project, not Core, requests acceptance CI every fifth bundle after 009
(014, 019, ...). Intermediate bundles do not spend an extra CI run. The prepared
Apply entrypoint checks GitHub read access before its commits and dispatches
once after its single final push. `gh` must already be authenticated for the
repository with Actions write access; failure does not trigger a login prompt,
retry or second push. Local commits and their actual result remain reviewable.

The workflow retains only `workflow_dispatch`. `handoff_id` and the full
`expected_commit` bind the request and checkout. The existing Ubuntu 26.04 lane
uses Python 3.14 and installs uv for one representative route; Ubuntu 24.04 and
native Windows use Python 3.12. pipx and wheel/source/sdist acceptance remain in
packaging. No new runner lane is added. Optional uv absence in other lanes is
an explicit skip; the designated lane must provide a passed uv proof.

`scripts/run_handoff_ci.py` records a durable intent in an owned ignored
`build/handoff-ci/<id>` before dispatch. Reusing the same workspace refuses a
second attempt. An ambiguous network response requires diagnosis, not redispatch.
GitHub is polled by that ordinary process, without model calls. The correlated
run must complete successfully with all six jobs, including both Windows engines.
Reports must be structurally complete, internally bound to unchanged source
bytes and the expected platform/interpreter. Cross-platform source digests may
differ because checkouts have platform EOL conventions; each job still binds to
the exact requested Git commit.

Machine JSON in the Apply execution log contains run ID/URL, full commit, job
steps, artifact hashes, test counts and the relevant bootstrap/commit proofs.
Failures retain job diagnostics and artifact references. A dispatch/start is not
a passed CI. Final plan approval requires the actual completed Apply and CI.
The workflow run/job/artifact contracts follow the
[GitHub REST API](https://docs.github.com/en/rest/actions/workflows#create-a-workflow-dispatch-event),
[workflow job endpoint](https://docs.github.com/en/rest/actions/workflow-jobs#list-jobs-for-a-workflow-run-attempt)
and [artifact endpoint](https://docs.github.com/en/rest/actions/artifacts#download-an-artifact).

## Final RIV audit

| Contract | Executable evidence and boundary |
| --- | --- |
| Static inspection, immutable package facts and CLI JSON 2 | `test_patch_inspection*`; no execution or registry access in package scope |
| Original Result 1/2 and explicit repository validation | `test_reference_validation*`, `test_repository_validation`; exact binding, actual state, no fabricated Git history |
| Canonical runtime profile, provenance and limits | `test_runtime_artifact`, `test_runtime_robustness`, `test_runtime_permissions`; no runtime dependencies or implicit installer |
| Mixed versions, archive and recovery | `test_result_format2`, `test_result_robustness`; strict public native integrity remains separate from success policy |
| All Result writers and request-pinned self-update | `test_result_runtime_writer`, `test_result_runtime_publication`, `test_result_runtime_roundtrip`; original producer with new repository snapshot |
| Installed three-generation roundtrip | `test_runtime_packaging`; same canonical bytes, bounded measured overhead, wheel/source/sdist and native rights |
| Bootstrap and previous procedure | `test_runtime_bootstrap`; real offline operation, trust/byte checks, mandatory fallback and invalid-base rejection |
| Zero/one/multiple commits, failure/partial progress | `test_handoff_commit_sequence`; real local Apply, private remote, gates before commits and one final push |
| Due CI and its complete evidence | `test_handoff_ci`; transport fixtures prove correlation/error handling. Actual Linux/Windows CI must still run on the final pushed HEAD |

The local development gates for W and R passed in parallel with 2,174 and 2,224
tests respectively (7 explicit skips each). C must retain R's exact collection
and outcomes; its separate full gate provides that evidence. The actual Apply
runs the intermediate parallel gates and, only at the final state, serial then
parallel before the final commit and sole push. No local test or simulated
transport is presented as an executed Windows job or a completed Apply.

All 18 planned implementation positions are prepared by this final bundle;
15 are confirmed by received Apply Results. Final approval awaits the actual
remaining three commits and successful bound CI. On confirmation the active
plan ends, without an extra bundle, new plan, version bump or automatic tag.
