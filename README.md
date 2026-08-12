# PatchHarbor

PatchHarbor is a controlled cross-platform runner for generated Bash and
PowerShell scripts and ZIP PatchBundles.

## Installation

PatchHarbor requires Python 3.12 or newer and [pipx](https://pipx.pypa.io/).
After publication, install it with:

```bash
pipx install patchharbor
```

## Command reference

The complete user-facing command reference is built into the CLI:

```bash
patchharbor --help
patchharbor fs run --help
patchharbor --version
```

## Result Bundles

`patchharbor bundle [REPOSITORY]` creates a complete repository snapshot
without Git history. It contains every file from the current base commit,
staged and unstaged changes, and every non-ignored untracked regular file.

Review a Result Bundle before sharing it. It can contain complete source code
and secrets from non-ignored files. PatchHarbor excludes `.git`, the local
`.patchharbor/id`, and ignored untracked files, but it does not perform
general secret detection.
