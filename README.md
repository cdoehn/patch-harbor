# PatchHarbor

PatchHarbor is a controlled cross-platform bridge between an external
development chat and local Git repositories. It registers repository instances,
creates complete Result Bundles, validates repository-bound ZIP patch packages,
and applies a package only to the exact registered state named in its
`patch.json`.

PatchHarbor also retains the explicit `fs run` command for generated Bash and
PowerShell scripts and legacy ZIP PatchBundles.

## Installation

PatchHarbor requires Python 3.12 or newer and [pipx](https://pipx.pypa.io/).
Install the published release with:

```bash
pipx install patchharbor
```

Use the `CHAT_INSTRUCTIONS.md` shipped with the same PatchHarbor version. In a
source checkout or source distribution it is in the project root; an installed
wheel also carries it under its shared `share/patchharbor/` data directory.
Every new Result Bundle embeds a freshly rendered copy of that template plus
local environment data. The original repository file is never overwritten.

## Repository-local setup

Each registered local repository owns **all of its PatchHarbor settings** in
`.patchharbor/config.json`, next to its `.patchharbor/id`. There is no global
Exchange setting and no global fallback. Only the registry (repository UUID to
physical repository path), locks and technical replay/runtime state are shared
per operating-system user; they are not a second configuration store.

Register first, then run the configuration command **from inside that repository**:

```bash
cd /path/to/repository
patchharbor register
patchharbor configure exchange-directory ~/Downloads
patchharbor configure show
```

All `configure` commands resolve the current working directory to its registered
Git repository. Subdirectories work too. Outside a repository, in an unregistered
repository, or with missing/invalid local metadata, the command fails without
creating or repairing a configuration. `register` never asks for an Exchange
path: a genuinely fresh registration creates this complete local Format-1 file:

```json
{
  "format_version": 1,
  "exchange_directory": null,
  "bundle_suffix": "",
  "archive_directory": "PatchHarbor-Archive"
}
```

This is a **new repository-local schema**, not the old global Format 1.
All four fields are required; additional, duplicate or invalid fields, BOMs and
unsupported versions are rejected. `null` means registration is complete but
no Exchange directory has been chosen. It is not a missing configuration file.
`configure show` can display this state. Suffix and archive preferences can be
set before Exchange is chosen; operations needing Exchange fail until it is set.

The Exchange argument must be absolute (the shell expands `~/Downloads`).
The setter creates the directory if needed and stores its physically resolved
absolute path. It may not equal, contain, or be inside **any** registered
repository. Setters update the existing valid document atomically and preserve
all other settings. They never initialize a missing file.
`.patchharbor/` is excluded through Git's local `info/exclude`, not through a
change to the project's versioned `.gitignore`. It is not committed or included
as repository files in Result Bundles. A dot-prefixed name is hidden on Linux;
PatchHarbor does not set a Windows Hidden attribute.

### Shared or separate Exchange directories

Both are supported, with settings remaining independent:

```bash
cd /path/to/repository-a
patchharbor configure exchange-directory ~/Downloads
cd /path/to/repository-b
patchharbor configure exchange-directory ~/Downloads
cd /path/to/repository-c
patchharbor configure exchange-directory ~/Downloads/Repository-C
```

All three repositories must already be registered. A and B share a physical
folder; C uses another one. The watcher scans each distinct physical Exchange
folder once per poll. Manifest `repo_id`, not the filename or another project's
preferences, determines ownership. Automatic discovery accepts a package only
from its target repository's configured Exchange. An explicit `apply PATCH_ZIP`
can read a package elsewhere, but still uses its manifest target's settings.

The flat Exchange directory may contain patch packages, Result Bundles, old
packages, and unrelated files together. PatchHarbor identifies content rather
than relying on filenames. Conservative automatic archival moves only bundles
with complete obsolescence proofs into a direct child folder; nothing is deleted.
Other downloads and unprovable bundles remain untouched. Shared Exchange folders
may have different suffix and archive preferences for each repository.

### Manual upgrade from global configuration

This is an intentional breaking change in the 1.2.0 development line, with
**no migration code, no automatic repair and no dual reading**. Earlier global
configuration formats are not accepted as local configuration formats.
An old `${XDG_CONFIG_HOME:-$HOME/.config}/patchharbor/config.json` on Linux or
`%APPDATA%\PatchHarbor\config.json` on Windows is ignored, even when it exists.
`watcher.json` and `paths.json` are not configuration sources either.

Finish any running Apply and stop the watcher before changing the installation
or editing local metadata. Update the CLI and watcher together. Keep the central
registry, `.patchharbor/id`, Git's local exclusion and the replay ledger; do not
delete locks or replay records to work around a configuration error.

For each **already registered** repository whose local config is missing, create
`.patchharbor/config.json` deliberately in an editor using the four-field JSON
above. Do not overwrite an existing valid file and do not copy an old global
JSON document wholesale. A damaged file requires deliberate manual correction;
`register`, `register --new-id` and `configure` are not repair commands.
Then, from that repository, run `configure exchange-directory` with the intended
absolute path and set any suffix/archive preference. These may be read manually
from the old settings, but the application never imports them. `configure show`
displays only that repository's values. Repeat for every local checkout.

For genuinely new repositories and ordinary Git clones, use the normal
`register` then `configure` workflow instead. A clone does not inherit ignored
metadata. `unregister` removes only the registry mapping: ID, config and the
local exclusion stay intact. Re-registering reuses them. After moving the entire
local repository, re-register at the new path; the old registered path must no
longer exist. A copied identity at two existing paths is a conflict, not a move.
A deliberate `register --new-id` can give the copy its own ID when its retained
local metadata is valid; it does not reset its settings.

### Conservative automatic Exchange archival

The default archive is **`PatchHarbor-Archive`**, directly inside the configured
Exchange directory. It is created on demand during normal Apply discovery,
Watcher scans, or manual bundle creation. No separate cleanup command is needed.
Configure its single folder name from the owning repository:

```bash
patchharbor configure archive-dir PatchHarbor-Archive
patchharbor configure archive-dir .PatchHarbor-Archive
patchharbor configure show
```

A leading dot uses normal Linux hidden-file semantics. On Windows it is simply
part of the name; PatchHarbor does not set a Hidden attribute. Absolute paths,
path separators, `.`/`..`, traversal and non-portable names are rejected. The
name supports 1–128 ASCII letters, digits, dots, underscores and hyphens, but no
trailing dot or Windows reserved device name. Disable automatic archival for
this repository with either setting (existing archive files are retained):

```bash
patchharbor configure archive-dir --clear
patchharbor configure archive-dir ""
```

**A timestamp, filename or mere successful exit is never enough.** The existing
replay state now records a full `completed_commit` only when a successful tracked
Apply moves the repository to a new, clean descendant commit. A patch can be
archived only if its exact path/content identity, full manifest binding and
successful completion receipt agree, and the current clean repository still
contains that commit in its original Git history. Explicit exchange packages
also record this evidence, without changing explicit retry eligibility. Legacy
records without a completion receipt remain conservatively unarchived.

A Result Bundle can be archived only when it describes a successful, clean,
completed run at a strict ancestor of the current clean HEAD. Its manifest,
context and run log must agree; every snapshot blob hash, size and mode is
checked against the complete actual Git tree, and unexpected contents are
rejected. Current, dirty, failed, incomplete, contradictory or damaged results
remain. Unknown repositories, shallow/grafted/replaced histories, Git failures
and unavailable proofs always mean **keep the original file**.

Manual parameterless Apply and bundle creation maintain only the current
registered repository. Explicit Apply maintains the package's repository, but
never archives the explicitly selected file before executing it. The Watcher
remains global across registered repositories. Dry-run never archives. Only
top-level files are considered; the archive is never scanned recursively.

Directories are physically checked, pinned and revalidated; links/junctions
cannot redirect the destination. Bundle bytes and repository evidence are
rechecked immediately before a no-overwrite rename. Name collisions use a fresh
unique destination name; existing files are never replaced. A failed or
unsupported safe rename leaves the source in place (no copy-and-delete
fallback). Retained replay receipts continue to prevent unintended reprocessing.

Within one scan, validated candidates are grouped by repository and share one
initial consistent state capture. Current results and patches without a usable
completion receipt need no ancestry query. Each actual move still rehashes the
file and captures the full repository state again, then checks fresh Git,
registration, configuration and replay evidence. Nothing authorizing a move is
cached across scans or reused in place of this final check.

### Optional bundle filename suffix

Configure a suffix for the current registered repository, using its local
configuration. For example, append `.txt` **after** the `.zip` extension:

```bash
patchharbor configure bundle-suffix .txt
patchharbor configure show
```

All newly generated Result Bundles for this repository then use
`<Repository>_Result_<HHMMSS>_<MMDD>_<ID6>.zip.txt`, including manual `bundle`,
automatic Apply results (success, failure, dry-run), Watcher results, and explicit
`--output-dir` targets. There is no suffix argument on `apply` or `bundle`.
Disable it with:

```bash
patchharbor configure bundle-suffix --clear
```

An empty `bundle_suffix` produces the unchanged `.zip` name. The suffix is literal:
no dot is inserted automatically. It may contain at most 32 ASCII letters,
digits, dots, underscores or hyphens, must include a letter or digit, and must
not contain `..` or end with a dot. Paths, whitespace, control characters and
incomplete-download endings such as `.part`, `.tmp` or `.crdownload` are rejected.
Suffix and archive preferences may be set while Exchange is still `null`.
Once an Exchange path is stored, setters revalidate it. An unavailable old path
can be replaced deliberately with `configure exchange-directory`, preserving the
other preferences; this is an explicit setting change, not automatic repair.
Reads and writes accept only the complete repository-local Format 1. The global
Format-4 replay ledger is separate from this configuration schema and remains
intact. Upgrade all installed PatchHarbor entrypoints together.

Patch packages are created by the development chat, not by a new local command.
The new Result Bundle's `context.json` carries `bundle_suffix` as optional
filename metadata. The matching chat instructions require the same suffix on
`<Repository>_Patch_<HHMMSS>_<MMDD>_<ID6>.zip`. Missing metadata in older bundles
means no suffix. After changing the setting, give the chat a fresh Result Bundle.
Do not put this field in `patch.json`: it is not part of repository binding.
`patchharbor context --json` keeps its existing closed schema; a standalone
context therefore needs the naming preference supplied separately.

The content stays ZIP, not text. Renaming alone does not guarantee that another
application can read it. The suffix setting never renames existing files. Old `.zip` and new
`.zip.txt` packages may coexist; selection, state binding, `mtime_ns`, manual
retry and the Watcher guard remain content-based and unchanged. Result Bundles
are never executed as patches, regardless of their filename.

Explicit `--output-dir` can bypass an unset or unavailable Exchange directory,
**not a missing or malformed local configuration**. It always uses the target
repository's valid local suffix, never another project's settings or a default
fallback. Default output requires an available Exchange directory. Result target
preparation revalidates the local identity, Exchange value and suffix before
publication; concurrent changes cause a controlled error.

## Initialize a repository

A repository must be a local Git repository with a committed `HEAD`. Registration
creates a local `.patchharbor/id`, the complete `.patchharbor/config.json`
with unset Exchange, and a user-specific central mapping from its UUID to the
physical repository path. Existing identities require valid local metadata.

### New Git repository

Create the Git repository and its first commit, then register it once:

```bash
cd /path/to/new-repository
git init
# Add the initial files and create the first Git commit.
patchharbor register
patchharbor configure exchange-directory ~/Downloads
patchharbor bundle
```

### Existing unregistered repository

```bash
cd /path/to/existing-repository
patchharbor register
patchharbor configure exchange-directory ~/Downloads
patchharbor bundle
```

### Already registered repository

With a valid local configuration and Exchange path, no re-registration is
needed. Create a fresh snapshot whenever the repository state changes:

```bash
cd /path/to/registered-repository
patchharbor context
patchharbor bundle
```

`context` is an optional human-readable check. Human-facing terminal output,
including the context printed by `patchharbor register`, shortens long technical
identifiers to their first six characters plus `…`. This shortened text is
presentation only: do not copy it into `patch.json` or use it as chat or machine
input. Run `patchharbor context --json` from the repository root, or
`patchharbor context --json REPOSITORY` from elsewhere, when complete values are
required. `register` itself deliberately has no `--json` option.

The Result Bundle already contains the full repository ID, base commit, state
fingerprint, committed snapshot, staged and unstaged changes, and non-ignored
untracked regular files. For standard chat initialization, upload that Result
Bundle instead of copying either form of terminal context output. Its
`context.json` is the authoritative source of complete repository-binding values.

Use `patchharbor registry list` to inspect all registrations. Its normal rows
also shorten repository UUIDs. Use `patchharbor registry list --json` when a full
UUID is needed for machine processing or `unregister`; alternatively pass the
exact repository path to `patchharbor unregister REPOSITORY_OR_REPO_ID`. A
six-character display prefix is never a valid repository selector. Use
`patchharbor register --new-id` only when intentionally replacing the local
instance identity.

## Initialize a new development chat

Upload the newest Result Bundle produced by `patchharbor bundle` and the
development request. Ask the chat to read the root `CHAT_INSTRUCTIONS.md` and
initialize itself from that bundle. It already contains the version-matching
contract plus a fresh local-environment section; no extra command or separate
instructions file is required. For old bundles without embedded instructions,
provide the version-matching `CHAT_INSTRUCTIONS.md` separately.

The local repository path or Exchange path in `environment.json` helps the chat
write commands for the development computer. These paths are informational,
never repository selectors or additions to `patch.json`. The Result Bundle
supplies the repository identity and exact state, while local PatchHarbor
resolves the registered path. The chat takes all
repository-binding identifiers from the bundle's complete `context.json`, never
from shortened human-facing terminal output.

The chat contract requires one downloadable repository-bound ZIP patch package.
Patch filenames use
`<Repository>_Patch_<HHMMSS>_<MMDD>_<ID6>.zip`, followed by `bundle_suffix`
from the Result Bundle when configured. After an Apply, upload the
newly created Result Bundle back to the same chat. For a failed entrypoint or
test run, that bundle contains the actual remaining repository state plus
`logs/run.json` and, when execution started, `logs/execution.log`.

## Self-contained bundle handoff

Every Result Bundle contains freshly generated root `CHAT_INSTRUCTIONS.md` and
`environment.json`, including manual `bundle`, Apply success, failure, Dry Run,
Watcher results, and explicit `--output-dir` targets. Both documents are verified
and published atomically with the snapshot and logs. No sidecar is written and
no `chat-instructions` command is introduced. Existing bundles are not rewritten.

Generated instructions use canonical LF line endings on every platform. The
loader normalizes CRLF and lone CR in the installed UTF-8 template; the shared
renderer applies the same rule to an explicitly supplied template for external
Patch authors. Other text, blank lines and the presence or absence of a final
newline are preserved. Template size/encoding checks remain strict and use the
original input bytes. This affects only generated documentation: the template
file, repository snapshots, received payload bytes and JSON values are not
rewritten or normalized.

`environment.json` uses marker `patch-harbor-environment`, format version 1. It
includes the actual resolved repository name/path and full binding values, the
configured Exchange path, the distinct actual output directory, bundle suffix,
filename schemas and UTC convention, and an allowlisted runtime description:
OS/distribution, kernel release, architecture, Python version/implementation,
`uv` version, configured shell, and PatchHarbor version. A new capture is made
for each publication; no prior bundle or target-project instructions are reused.

Missing facts are `null`, not guesses. For example, a missing or unresponsive
`uv --version` does not prevent a Result Bundle; its optional local probe is
limited to two seconds. OS detection makes no network requests. The distribution
identifies the running userland (such as Ubuntu inside Termux/proot); its kernel
may belong to the host. The configured shell comes only from `SHELL`/`COMSPEC`
and is not evidence of the currently active shell. Command examples are quoted
for POSIX shells or PowerShell, explicitly labelled, and omitted when unknown.

Only allowlisted fields are collected, not hostnames, IP addresses, user-name
fields, hardware serial numbers, tokens or the complete environment. Required
absolute paths may naturally contain a user name. Review bundles before sharing.
An explicit output directory can bypass an unset or unavailable Exchange path,
but never a missing or invalid repository-local configuration. The environment
records the selected repository's configured values, not a substituted Exchange
path inferred from the output directory. `context.json`, `patch.json`,
fingerprints and replay identities do not gain environment-dependent fields.

External chat-generated Patch packages carry the same passive documents under
`PATCHHARBOR_META/CHAT_INSTRUCTIONS.md` and `PATCHHARBOR_META/environment.json`.
The root `CHAT_INSTRUCTIONS.md` remains available as a genuine repository payload
when a documentation change requires it. The reserved metadata pair is validated
and excluded from mutation and execution; it cannot be an entrypoint. Existing
packages without it still work. Each metadata file is UTF-8 without BOM, at most
128 KiB, with the ordinary ZIP safety/resource rules still enforced. Unknown or
incomplete reserved entries and metadata bindings that differ from `patch.json`
are rejected. This is passive documentation, not authentication or orchestration.

The chat generates a fresh handoff for each Patch using the latest target
machine's environment snapshot, retaining its capture time and unknown values,
not probing the chat sandbox as if it were the development machine. PatchHarbor
Core creates Result Bundles; it does not create chat patches or edit received
packages. See the chat contract for the first-upgrade bootstrap rule for older
runners. The installed shared template is required; if missing, publication
fails cleanly instead of emitting an apparently self-contained incomplete bundle.

## Manual workflow

Manual mode is the normal interactive workflow and the recommended mode on
Termux/Android.

```bash
cd /path/to/registered-repository
patchharbor bundle
# Upload the new Result Bundle; its chat instructions are already inside.
# Save the chat's one returned patch ZIP in the configured Exchange directory.
patchharbor apply --dry-run
patchharbor apply
```

A deliberate manual parameterless `patchharbor apply` first resolves the
current working directory to exactly one registered Git repository. Calls from
any subdirectory of that repository resolve to the same repository root. If the
current directory is not inside a uniquely registered repository, Apply stops
without scanning for a fallback package belonging to another repository.

PatchHarbor then scans only the top level of the configured Exchange directory
and considers packages for that one `repo_id`. It filters by base commit, state
fingerprint, package validity, and manual replay eligibility before ranking the
remaining candidates. The greatest nanosecond modification time (`mtime_ns`)
wins. Equal `mtime_ns` values use the lexicographically first filename after
Unicode NFC normalization, with the original filename as a final deterministic
fallback. A newer foreign, state-mismatched, or replay-ineligible package never
blocks an older eligible package. Filenames do not determine repository or state
binding; they are used only for that final tie-breaker.

The default timeout for one script or repository entrypoint is 10,800 seconds
(three hours). Use `--timeout SECONDS` to override it for one invocation.

A Dry Run validates the selected package without changing the repository or its
replay state. A non-Dry-Run Apply records `attempted` immediately before mutation
or entrypoint execution and publishes `failed` or `succeeded` from the actual
result. A successful package remains replay-protected. A failed package can be
retried by another deliberate manual parameterless `patchharbor apply` while its
complete repository binding still matches. An explicit package path remains a
separate deliberate override.

### Recovering an interrupted Apply

An `attempted` record alone is not evidence of a crash or success. A run can
still be working even when `screen -ls` shows no socket. Recovery must acquire
the **same exclusive repository lock** as Apply. A busy lock, dirty repository,
missing receipt or contradiction leaves the attempt untouched. PatchHarbor does
not infer liveness from process names and never automatically resets files.

New Apply Result manifests record the full `patch_sha256` of the exact validated
ZIP bytes and an optional `completed_commit`, alongside the existing `run_id`,
repository ID and expected/actual state binding. A completion is recorded only
for a successful executed entrypoint and a verified clean forward commit. Dry
runs, failures and successful no-op runs have no completion proof.

For tracked Exchange attempts the existing local replay ledger (Format 4) also
stores `attempt_run_id` and `result_sha256`. The order is:

1. Persist `attempted` and its run ID before mutation.
2. Execute the entrypoint and capture its actual result and repository snapshot.
3. Write and verify the Result ZIP; pin its full SHA-256 in the local ledger
   **before** atomically publishing that ZIP.
4. Publish the terminal replay outcome after the Result publication attempt.

A later non-dry Exchange scan can repair `attempted` to `succeeded` and restore
`completed_commit` only when the original patch identity, pinned Result digest,
run ID, repository ID, complete original binding, successful report, clean full
snapshot and original Git history all agree. The required history is
`expected_base_commit -> completed_commit -> current HEAD`, where the first
step must advance. It revalidates the evidence under the repository, registry
and replay-state locks before a compare-and-swap. An edited Result cannot be
made into proof just by retaining its filenames or JSON identifiers. Hashes are
integrity/correlation checks anchored in the trusted local ledger, not digital
signatures or authentication against somebody who can rewrite that ledger.

Recovery runs before archival for manual CWD-scoped Apply, package-scoped
explicit Apply and the global watcher, and during manual bundle maintenance.
It also runs when archival is disabled. Dry runs do not repair state. A still
pending receipt is protected from archival. Once proven, the existing archival
rules may move the consumed patch; a current Result still remains active.

Only the active Exchange level is searched. A Result moved or renamed within
that level keeps the same proof if its bytes are identical; an explicit output
outside Exchange must be brought into the active Exchange to be found. The
original tracked patch path/content identity must still exist there. Archived
subdirectories are not recursively searched.

**Limits:** a crash before a success Result is published (even after a Git
commit) does not prove success. It remains `attempted`; no automatic retry or
rollback is attempted. Formats 1–3 remain readable without inventing run IDs,
hashes or completion proofs; writes migrate to Format 4. This cannot retroactively
repair old upgrade attempts that never recorded these proofs. A still-running
older executable also does not gain the new receipt protocol by changing files:
reinstall the current version before subsequent Apply runs.

### Compact console and verbose diagnostics

Normal `apply`, `fs run` and `bundle` output shows important phases, results,
warnings and errors. File reads/writes, ZIP members, SHA checks and individual
Git queries are grouped instead of printed line by line. A running internal
operation appends **at most one dot every 0.8 seconds** to its current line.
There is no carriage return, cursor movement, redraw or catch-up burst. Fast
operations need no dots; completion or another visible message ends the line.

Use `--verbose` (or `-v`) to show the complete technical activity stream:

```sh
patchharbor apply --verbose
patchharbor bundle --verbose
patchharbor --verbose context
patchharbor fs run --verbose generated.sh
```

The option works before or after the command. `--plain` and `--no-color` only
change decoration, not detail selection. Colors and short human-readable IDs
remain. `--json` suppresses both human activity and dots even with `--verbose`;
its machine schema, complete identifiers and exit statuses do not change.

`MESSAGE` blocks and live script stdout/stderr are **never filtered by verbosity**.
Dots stop while child output is active and are never inserted into raw logs.
Library calls without an observer remain silent. Small configuration/context
commands keep their existing compact summaries; `--verbose` enables their
internal activity too. Use verbose mode for individual scan rejection reasons.
There are no automated tests of console text, colors, symbols or dot formatting;
functional data, error, recovery and process tests remain in place.

### Explicit path overrides

An explicit patch path bypasses parameterless package selection. Its complete
`repo_id` may resolve another registered repository even when it differs from
the repository containing the current working directory. This is a deliberate
user selection; all package, state-binding, path, and revalidation checks remain
mandatory. An explicit `--output-dir` overrides only the Result Bundle
destination:

```bash
patchharbor bundle --output-dir /path/to/results /path/to/repository
patchharbor apply --dry-run --output-dir /path/to/results /path/to/patch.zip
patchharbor apply --output-dir /path/to/results /path/to/patch.zip
```

Supplying both an explicit `PATCH_ZIP` and explicit `--output-dir` also permits
Apply when the target repository's Exchange path is unset or unavailable. Its
local configuration must nevertheless exist and validate; the target
repository's configured suffix still applies. Explicit output directories must
remain outside all registered repositories.

The separate manual script runner is intentionally explicit and operates in the
current working directory:

```bash
patchharbor fs run /path/to/script-or-bundle
```

## Termux and Android

Use manual mode on Termux. PatchHarbor does not treat the Android background
process lifecycle as a reliable systemd service environment. Download the patch
ZIP into the configured Exchange directory and run `patchharbor apply` manually;
reusing the previous shell command is sufficient. No Termux-specific watcher
support is claimed by PatchHarbor 1.2.0.

Functional CLI test helpers have no default subprocess deadline; slow Git or
shared storage must not turn a correct scan into an arbitrary 20-second failure.
Explicitly requested lifecycle/timeout checks retain their bounds. Termux patch
entrypoints run pytest without per-test or whole-suite deadlines. The product's
10,800-second default entrypoint timeout is unchanged. The native acceptance
matrix has a 120-minute job limit; separate PowerShell/Docker bounds are unchanged.

## Linux watcher

The optional watcher is a thin permanent trigger for Core's parameterless
automatic Apply mode. It has no input-directory argument and no separate
configuration or file-classification logic. Its selection scope remains global:
it can inspect eligible packages for every registered repository and does not
use the watcher's current working directory as a repository restriction. Unlike
a deliberate manual Apply, this mode does not retry an unchanged failed package
on later polls.

Register and configure each repository first. The following example configures
one already registered repository, then installs the disabled systemd user unit:

```bash
cd /path/to/registered-repository
patchharbor configure exchange-directory ~/Downloads
patchharbor-watcher --install-systemd-user-unit
systemctl --user daemon-reload
systemctl --user enable --now patchharbor-watcher.service
```

The installer never enables or starts the service. Run the watcher directly in
the foreground with `patchharbor-watcher`, optionally using
`--poll-interval SECONDS`.

Inspect or stop the service with:

```bash
journalctl --user -u patchharbor-watcher.service
systemctl --user disable --now patchharbor-watcher.service
```

Startup validates the central registry, not a configuration relative to the
service's working directory. Every poll reloads the registered repositories'
local settings through Core and scans distinct physical Exchange directories
once. Valid repositories with `exchange_directory: null` and missing repository
paths have no watched directory and are skipped. A missing/invalid config in an
existing repository, conflicting identity or unavailable configured Exchange
fails the poll without repair; it is not silently treated as an unconfigured repo.
After manual correction the next poll reloads the settings.

The watcher uses the same repository-local configuration, package validation,
persistent replay state, repository locks and Result Bundle behavior as Core. A
failed package remains available for a later manual Apply but is not immediately
repeated by the watcher. Do not run the autonomous watcher and Repo Assist or
another orchestrator for the same repositories at the same time.

## Security and responsibility boundaries

PatchHarbor is not a sandbox. Entrypoints run with the rights of the current
user. Repository ID, base commit, and fingerprint verify the selected local
state; they do not authenticate who created a patch package. Run only trusted
packages.

Payload files are replaced atomically one by one, but a package is not a global
transaction and earlier successful writes are not automatically rolled back.
PatchHarbor does not run target-project tests or create Git commits. Repo Assist
owns commit plans, journals, reproducibility, and commit management;
PromptBridge owns chat, network, upload, and download transport.

## Result Bundles

`patchharbor bundle [REPOSITORY]` creates a complete repository snapshot
without Git history. It contains every file from the current base commit, staged
and unstaged changes, and every non-ignored untracked regular file. Without
`--output-dir`, it publishes directly in the configured Exchange directory. The
filename is `<Repository>_Result_<HHMMSS>_<MMDD>_<ID6>.zip`, using UTC, no
year, and the first six run-ID characters without an ellipsis. Filenames are
presentation only; Exchange classification still uses validated content.

Review a Result Bundle before sharing it. It can contain complete source code
and secrets from non-ignored files. PatchHarbor excludes `.git`, the local
`.patchharbor/` directory, and ignored untracked files, but it does not perform general
secret detection.

## Command reference

The installed `patchharbor --help`, `patchharbor COMMAND --help`, and
`patchharbor-watcher --help` screens are the complete user-facing CLI reference.
Only implemented commands and options are shown there.


### Application and public API boundaries

Application workflows now publish immutable, request-local facts through
`progress.py`. Repository and script records carry full data; only the CLI
adapter knows colors, shortening or verbosity. Observation is optional and
cannot authorize mutation or override recovery checks. Child output is separate
and requires an explicitly supplied `OutputTargets`; the default is silent.
Directory selection is an explicit callback, with the interactive menu owned by
the CLI. Unknown choices are rejected before a file is executed.

The public `patchharbor.api` facade uses these boundaries in version 1.2.0.
Library callers supply `api.OutputStreams` and receive structured results.
The main CLI and the Watcher use the same API; neither duplicates Core decisions.


Tool failures internally carry a `FailureReason`, not a CLI exit number.
`exit_status.py` is the shared compatibility adapter used by the CLI and the
existing JSON/Result serializers. Numeric schemas and exit priorities remain
unchanged. Child-process exit codes remain actual process data, including values
such as 124 or 130; they are not mistaken for PatchHarbor timeout/interruption.
The Application makes decisions from semantic outcomes, not serialized statuses.


## Python-Bibliothek – PatchHarbor 1.2.0

`from patchharbor import api` stellt Konfiguration, Registry, Kontext, Bundles,
Apply/Dry-Run, den automatischen Einzelpoll und den expliziten Skriptrunner bereit.
Die Aufrufe bleiben ohne explizite Streams/Beobachter still und liefern typisierte
Resultate bzw. fachliche Fehler. Kein CLI-Subprozess ist erforderlich.

Der vollständige Vertrag mit Beispielen steht in [docs/python-api.md](docs/python-api.md).
[Plan](planning/1.2.0/commit-plan.md) und [Spec](planning/1.2.0/specification.md)
dokumentieren die vier umgesetzten Schritte: Bibliotheksgrenze, CLI, Watcher
und Release. `patchharbor.api` ist die unterstützte öffentliche Python-Schnittstelle
ab 1.2.0; alle anderen Implementierungsimporte bleiben intern.

Die Haupt-CLI verwendet die API für alle fachlichen Operationen. Der Watcher
verwendet sie zur Registry-Prüfung und im separaten Prozess jedes Apply-Polls;
Core lädt dabei die repositorylokalen Einstellungen.
Eine CLI-Installation mit `uv tool` stellt das Modul nicht automatisch in anderen
Python-Umgebungen bereit. Zum Importieren muss PatchHarbor in der Umgebung des
aufrufenden Python-Programms installiert sein. Das Wheel enthält `py.typed` und
die API-Dokumentation; neue Runtime-Abhängigkeiten gibt es nicht.


### Watcher als API-Verbraucher (API-3)

Der Watcher prüft beim Start die Registry über `api.repositories()`.
Jeder automatische Poll liest die repositorylokalen Einstellungen frisch und bleibt ein eigener
Prozess derselben Installation; dessen privater Worker ruft `api.apply_next()`
direkt auf, nicht mehr den CLI-Parser. Betriebs-JSON, globaler Scope, Replay und
Failed-Retry-Schutz bleiben erhalten. Die Prozess-/Signalgrenze und der Linux-
Servicevertrag bleiben unverändert. Die Paketversion ist 1.2.0.
