# PatchHarbor

PatchHarbor is a controlled cross-platform runner for generated Bash and
PowerShell scripts and repository-bound ZIP patch packages.

## Installation

PatchHarbor requires Python 3.12 or newer and [pipx](https://pipx.pypa.io/).
Install the published release with:

```bash
pipx install patchharbor
```

## Core workflow

Register one local Git repository, capture its exact state, and create a
complete Result Bundle for a chat or another external workflow:

```bash
cd /path/to/repository
patchharbor register
patchharbor context
patchharbor bundle
```

A repository-bound patch package can then be checked without mutation and
applied only to the registered repository state named in its `patch.json`:

```bash
patchharbor apply --dry-run /path/to/patch.zip
patchharbor apply /path/to/patch.zip
```

The original manual runner remains available for a script, directory, pipe,
or ZIP PatchBundle that is intentionally executed in the current working
directory:

```bash
patchharbor fs run /path/to/script-or-bundle
```

## Security and responsibility boundaries

PatchHarbor is not a sandbox. Entrypoints run with the rights of the current
user. Repository ID, base commit, and fingerprint verify the selected local
state; they do not authenticate who created a patch package. Run only trusted
packages.

Payload files are replaced atomically one by one, but a package is not a global
transaction and earlier successful writes are not automatically rolled back.
PatchHarbor does not run target-project tests or create Git commits. Repo Assist
owns tests, commits, retries, and journals; PromptBridge owns chat, network,
upload, and download transport.

## Command reference

The installed `patchharbor --help` and `patchharbor-watcher --help` commands are
the complete user-facing reference. Only implemented commands and options are
shown there.

## Result Bundles

`patchharbor bundle [REPOSITORY]` creates a complete repository snapshot
without Git history. It contains every file from the current base commit,
staged and unstaged changes, and every non-ignored untracked regular file.

Review a Result Bundle before sharing it. It can contain complete source code
and secrets from non-ignored files. PatchHarbor excludes `.git`, the local
`.patchharbor/id`, and ignored untracked files, but it does not perform
general secret detection.

## Linux watcher

The optional watcher is installed with PatchHarbor. Configure one
non-recursive input directory and install its systemd user unit with:

```bash
patchharbor-watcher --configure ~/Downloads
patchharbor-watcher --install-systemd-user-unit
systemctl --user daemon-reload
```

Activate or deactivate the service explicitly:

```bash
systemctl --user enable --now patchharbor-watcher.service
systemctl --user disable --now patchharbor-watcher.service
```

The installer never enables or starts the service. Operational records go to
stdout and stderr and can be read with:

```bash
journalctl --user -u patchharbor-watcher.service
```

Do not run the autonomous watcher and Repo Assist for the same repositories at
the same time. The repository lock rejects simultaneous PatchHarbor Core jobs,
but it does not coordinate two workflow orchestrators.
