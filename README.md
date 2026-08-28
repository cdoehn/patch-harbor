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

Format 1 is a closed JSON schema with exactly these fields:

```json
{
  "exchange_directory": "/absolute/path/to/exchange",
  "format_version": 1
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

`context` is an optional human-readable check. The Result Bundle already
contains the repository ID, base commit, state fingerprint, committed snapshot,
staged and unstaged changes, and non-ignored untracked regular files.

Use `patchharbor registry list` to inspect all registrations. Use
`patchharbor unregister REPOSITORY_OR_REPO_ID` only to remove a central mapping,
and `patchharbor register --new-id` only when intentionally replacing the local
instance identity.

## Initialize a new development chat

Start a new chat with exactly these repository inputs:

1. the version-matching `CHAT_INSTRUCTIONS.md`,
2. the newest Result Bundle produced by `patchharbor bundle`,
3. the development request or instruction to prepare the next plan commit.

Do not give the chat the local repository path or Exchange path. It does not
need either path: the Result Bundle supplies the repository identity and exact
state, while local PatchHarbor resolves the registered path.

The chat contract requires one downloadable repository-bound ZIP patch package.
After an Apply, upload the newly created Result Bundle back to the same chat.
For a failed entrypoint or test run, that bundle contains the actual remaining
repository state plus `logs/run.json` and, when execution started,
`logs/execution.log`.

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

Parameterless `apply` scans only the top level of the configured Exchange
directory. It selects exactly one unattempted package whose `repo_id`, base
commit, and state fingerprint match a currently registered repository. The
current working directory does not select the repository. No match or multiple
matches stop without repository mutation.

A Dry Run validates the selected package without changing the repository and
does not mark it as attempted. A non-Dry-Run Apply records the automatic attempt
immediately before mutation or entrypoint execution and then attempts a Result
Bundle in the Exchange directory. An unchanged automatically attempted package
is not selected again; an explicit package path can deliberately retry it.

### Explicit path overrides

An explicit patch path bypasses automatic package selection. An explicit
`--output-dir` overrides only the Result Bundle destination:

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

The optional watcher is a thin permanent trigger for the same parameterless Core
Apply operation. It has no input-directory argument and no separate
configuration or file-classification logic.

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

The watcher uses the same `config.json`, automatic package discovery, persistent
attempt identity, repository locks, and Result Bundle behavior as
`patchharbor apply`. Do not run the autonomous watcher and Repo Assist or another
orchestrator for the same repositories at the same time.

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
without Git history. It contains every file from the current base commit, staged and
unstaged changes, and every non-ignored untracked regular file. Without
`--output-dir`, it publishes directly in the configured Exchange directory.

Review a Result Bundle before sharing it. It can contain complete source code
and secrets from non-ignored files. PatchHarbor excludes `.git`, the local
`.patchharbor/id`, and ignored untracked files, but it does not perform general
secret detection.

## Command reference

The installed `patchharbor --help`, `patchharbor COMMAND --help`, and
`patchharbor-watcher --help` screens are the complete user-facing CLI reference.
Only implemented commands and options are shown there.
