# POSIX-MODE commit plan

Specification: `planning/posix-mode/specification.md`.
Approved scope: one bundle, three real consecutive W/R/C commits.
Each state is applied and tested before its commit; stop on failure, keeping
previous commits and the in-progress working tree. No destructive rollback.

Progress after this tested commit: **1/3**.

- [x] `POSIX-MODE.a.W` — `fix(apply): preserve POSIX modes for repository payloads`
- [ ] `POSIX-MODE.a.R` — `security(apply): validate payload modes and reject unsafe permissions`
- [ ] `POSIX-MODE.a.C` — `refactor(apply): centralize payload mode policy and core usage guidance`

W establishes real payload-mode behavior. R hardens final publication against
observed target changes and tests error, boundary and full-apply cases. C
separates capture/selection/publication responsibilities and updates guidance
without adding a new behavior. No independent repair commit is planned.
The previous parallelization plan and its Windows FIX are not changed.

2026-09-18 retry: the original W bootstrap rejected a local 0664 target before
any source change or commit. Correct W/R/C consistently: preserve existing
ordinary rwx bits, including shared writes; reject existing special bits and
keep ZIP/API requests strict. No independent repair commit or chmod sweep.
The serial C reference is retained for this previously approved bundle only.

Packaging continuation (2026-09-18): the corrected 0664 W payloads were applied,
but W was not committed because the wheel allowlist still omitted the new
`patchharbor/payload_modes.py` module. Resume from that verified dirty worktree;
add the module to the exact wheel/source-distribution contract and a fast source
inventory regression. No test/packaging check is removed. Re-run all W gates
before committing, then apply R and C in sequence. Do not reapply the old W
payloads, reset the worktree, normalize permissions or create a repair commit.
