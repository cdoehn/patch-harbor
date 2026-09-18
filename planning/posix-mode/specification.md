# POSIX payload permissions – approved core contract

Policy revision: 2026-09-18; correction before the first POSIX commit.
Latest base: `patch-harbor_Result_105838_0918_24a9a2.zip`.
The previous attempt stopped at existing mode 0664 before source mutation.

Task: POSIX-MODE. Based on the clean Blade result at `83bcd5d920790c22f015ba0bd5c53df7885223a2`.
This is a new three-commit W/R/C task; `planning/test-parallel/commit-plan.md`
remains complete at 15/15. The independent external Windows CI is not an approval
of this change and is not assumed green.

## Scope and rules

The core writes repository payloads before the entrypoint starts. Preserve the
ordinary POSIX rwx mode of an existing regular target (including 0600, 0640,
0644, 0750, 0755, 0664, 0666, 0775 and 0777). Existing group/other-write bits
are preserved as local policy, not endorsed as safe for every deployment.
Never let the staging file's private 0600 accidentally replace that mode.
An existing mode takes precedence over a safe requested ZIP mode. Validate both:
an unsafe request is invalid even when a pre-existing mode would win.

For new regular files, preserve explicit safe Unix permission bits from ZIP
`create_system == 3` and `external_attr >> 16`. Without usable Unix metadata use
0644; do not guess executability from names/extensions. Python ZIP writers may
explicitly emit 0600: that is real metadata, not a missing-value signal. A high
word of zero is absent metadata; a typed regular file with explicit mode 0000
is distinct and remains 0000. Other hosts' external attributes do not describe
Unix modes and are not interpreted as permission bits.

Permission bits are integers in 0000..7777 (not booleans). Requested ZIP/API
modes reject 07022: setuid, setgid, sticky, group-write and other-write, even
if an existing target would override the request. Existing modes reject only
07000 (setuid, setgid, sticky); all ordinary 0000..0777 bits remain unchanged.
There is no normalization to 0644, no chmod sweep and no automatic repair of
special bits. Reject invalid current modes during
read-only preflight of all payloads, before any repository file/parent is
written. Revalidate targets and current modes at mutation time. Detect observed
concurrent changes at the final publication check; the repository lock remains
the cooperative synchronization boundary, not a sandbox against hostile actors.

File-type/path rules remain: no payload or target symlinks, junctions, special
files, or symlink parents. Directory entries create no payloads and their mode
is not applied. Existing regular hardlinked targets are not written in place;
atomic replacement does not modify another link's contents.

Stage bytes privately beside the target, flush, set the final POSIX mode on the
open descriptor, synchronize it, and only then replace. On observed inspection,
mode, sync or replace failure, leave that target's original bytes/mode unchanged
and clean up the temporary file (cleanup can only be best effort if the OS also
refuses unlink). Earlier successfully published payloads remain on a later
runtime failure: no multi-file transactional rollback is promised.

The low-level atomic writer receives an optional explicit mode, not repository
policy. Calls without a mode keep the private staging-file behavior for registry,
configuration and runtime state. Windows retains native permission/ACL semantics;
ZIP validation remains cross-platform but POSIX bits are not mapped to Windows
ACLs/read-only attributes. Ownership, ACLs and extended attributes are not copied
or guaranteed by this POSIX-mode fix. Fingerprint and package format stay unchanged.
Already affected 0600 files are not automatically broadened: their original
permissions cannot be reconstructed from current permission bits or Git.

## Entrypoint/core boundary and bootstrap

Use existing core facilities rather than implementing new payload writers,
path validators, registry/state or archive machinery in the entrypoint. Inspect
available source/API first and use actual supported functions (no invented API).
If reusable infrastructure is missing, extend the core deliberately. Entrypoints
orchestrate task-specific tests and commits; no recursive apply/bundle calls.

This self-upgrade is delivered to an older installed core with the very bug being
fixed. Therefore the bundle has no automatically applied repository payloads.
For its first W step the orchestrator loads a private copy of the exact W core
source (not a separately implemented writer), preflights and writes only W via
its `write_bundle_payloads`. R and C use that tested committed core from the
repository in fresh subprocesses. No end-state installation ahead of commits;
no chmod sweep, no destructive reset, no production reinstall or push.

## Acceptance

W: existing ordinary/new safe modes, ZIP transport, whole-batch invalid-mode preflight,
private-state boundary and native Windows branch; targeted and full auto tests.
R: failure injection, final-state checks, umask independence, real format-1
apply-before-entrypoint and dry-run/rejection tests; full auto suite.
C: behavior-neutral policy/adapter cleanup, public guidance, complete auto and
serial tests including packaging and comparison of core result evidence.
No new visual/documentation tests, no custom scheduler, no short test timeouts.
Native Windows CI is a subsequent external verification, not fabricated locally.

The complete serial run is retained only as the explicitly approved exception
for this POSIX bundle. Subsequent local bundles use parallel complete suites;
the serial full-suite reference belongs in CI. No runner/CI behavior changes
are introduced by documenting this policy.

## Packaging continuation after the corrected W attempt

Resume input: `patch-harbor_Result_112656_0918_06e4db.zip`; base commit remains
`83bcd5d920790c22f015ba0bd5c53df7885223a2`. Its worktree already contains all W
payloads, but the failed full-suite packaging gate prevented the first commit.
Verify this exact worktree before applying the packaging-contract correction.
Include `payload_modes.py` in the explicit wheel inventory and require it in the
source distribution. Keep the wheel inventory equality, size, metadata, pipx
installation and real execution checks. Add a fast inventory regression so an
omitted module is detected without waiting for the build/install test.
This changes no permission policy and creates no additional repair commit.
