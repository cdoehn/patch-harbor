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

## One-time user setup

PatchHarbor uses one shared Exchange directory per operating-system user. It is
not configured per repository, and `patchharbor register` never asks for it.
Configure and inspect it with:

```bash
patchharbor configure exchange-directory ~/Downloads
patchharbor configure show
```

On Linux, the default configuration path is:

```text
${XDG_CONFIG_HOME:-$HOME/.config}/patchharbor/config.json
```

On Windows, it is:

```text
%APPDATA%\PatchHarbor\config.json
```

Format 2 is a closed JSON schema with exactly these fields:

```json
{
  "exchange_directory": "/absolute/path/to/exchange",
  "format_version": 2,
  "bundle_suffix": ""
}
```

The CLI is the recommended way to write this file. Direct editing is allowed,
but missing, additional, duplicate, or invalid fields are rejected. The path is
stored as a physically resolved absolute directory. The Exchange directory may
not equal, contain, or be inside any registered repository. `watcher.json` and
`paths.json` are not configuration sources in PatchHarbor 1.1.1.

The flat Exchange directory may contain patch packages, Result Bundles, old
packages, and unrelated files together. PatchHarbor identifies content rather
than relying on filenames, and it does not move, rename, archive, or delete
Exchange files.

### Optional bundle filename suffix

Configure a suffix once, using the same shared configuration as the Exchange
path. For example, to append `.txt` **after** the existing `.zip` extension:

```bash
patchharbor configure bundle-suffix .txt
patchharbor configure show
```

All newly generated Result Bundles then use
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
Set the Exchange directory before configuring the suffix. Changing either
setting preserves the other. Reads accept existing closed Format-1 configuration
files as an empty suffix without rewriting them; the next configuration write
atomically migrates to Format 2. Older PatchHarbor versions cannot read Format 2.

Patch packages are created by the development chat, not by a new local command.
The new Result Bundle's `context.json` carries `bundle_suffix` as optional
filename metadata. The matching chat instructions require the same suffix on
`<Repository>_Patch_<HHMMSS>_<MMDD>_<ID6>.zip`. Missing metadata in older bundles
means no suffix. After changing the setting, give the chat a fresh Result Bundle.
Do not put this field in `patch.json`: it is not part of repository binding.
`patchharbor context --json` keeps its existing closed schema; a standalone
context therefore needs the naming preference supplied separately.

The content stays ZIP, not text. Renaming alone does not guarantee that another
application can read it. Existing files are never renamed. Old `.zip` and new
`.zip.txt` packages may coexist; selection, state binding, `mtime_ns`, manual
retry and the Watcher guard remain content-based and unchanged. Result Bundles
are never executed as patches, regardless of their filename.

Explicit `--output-dir` remains usable with missing or malformed configuration,
as before; it then uses no suffix. A valid configured suffix is honored even if
the configured Exchange directory is temporarily unavailable. With default
Exchange output, invalid configuration remains an error. A suffix change during
Result Bundle preparation is rejected rather than publishing inconsistent
filename metadata.

## Initialize a repository

A repository must be a local Git repository with a committed `HEAD`. Registration
creates a local `.patchharbor/id` and a user-specific central mapping from its
UUID to the physical repository path.

### New Git repository

Create the Git repository and its first commit, then register it once:

```bash
cd /path/to/new-repository
git init
# Add the initial files and create the first Git commit.
patchharbor register
patchharbor bundle
```

### Existing unregistered repository

```bash
cd /path/to/existing-repository
patchharbor register
patchharbor bundle
```

### Already registered repository

Do not register it again. Create a fresh snapshot whenever the repository state
changes:

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

Start a new chat with exactly these repository inputs:

1. the version-matching `CHAT_INSTRUCTIONS.md`,
2. the newest Result Bundle produced by `patchharbor bundle`,
3. the development request or instruction to prepare the next plan commit.

Do not give the chat the local repository path or Exchange path. It does not
need either path: the Result Bundle supplies the repository identity and exact
state, while local PatchHarbor resolves the registered path. The chat takes all
repository-binding identifiers from the bundle's complete `context.json`, never
from shortened human-facing terminal output.

The chat contract requires one downloadable repository-bound ZIP patch package.
Patch filenames use
`<Repository>_Patch_<HHMMSS>_<MMDD>_<ID6>.zip`, followed by `bundle_suffix`
from the Result Bundle when configured. After an Apply, upload the
newly created Result Bundle back to the same chat. For a failed entrypoint or
test run, that bundle contains the actual remaining repository state plus
`logs/run.json` and, when execution started, `logs/execution.log`.

## Manual workflow

Manual mode is the normal interactive workflow and the recommended mode on
Termux/Android.

```bash
cd /path/to/registered-repository
patchharbor bundle
# Upload CHAT_INSTRUCTIONS.md and the new Result Bundle to the chat.
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
Apply without a valid Exchange configuration. Explicit output directories still
must remain outside all registered repositories.

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
support is claimed by PatchHarbor 1.1.1.

## Linux watcher

The optional watcher is a thin permanent trigger for Core's parameterless
automatic Apply mode. It has no input-directory argument and no separate
configuration or file-classification logic. Its selection scope remains global:
it can inspect eligible packages for every registered repository and does not
use the watcher's current working directory as a repository restriction. Unlike
a deliberate manual Apply, this mode does not retry an unchanged failed package
on later polls.

Configure the shared Exchange directory first, then install the disabled systemd
user unit:

```bash
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

The watcher uses the same `config.json`, package validation, persistent replay
state, repository locks, and Result Bundle behavior as `patchharbor apply`. A
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
`.patchharbor/id`, and ignored untracked files, but it does not perform general
secret detection.

## Command reference

The installed `patchharbor --help`, `patchharbor COMMAND --help`, and
`patchharbor-watcher --help` screens are the complete user-facing CLI reference.
Only implemented commands and options are shown there.
