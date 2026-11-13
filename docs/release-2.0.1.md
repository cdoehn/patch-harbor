# PatchHarbor 2.0.1

This version packages the changes since 2.0.0. The GitHub release and its exact
commit remain subject to the [complete release gates](release-runtime.md).

## Changes

- Local test profiling has capacity estimates with tenfold headroom for full
  suites, scalable collection limits, streaming Python-profile imports and
  one-time indexing of strace phases. Profiling remains an explicit local
  operation; preparation and test execution are measured separately.
- Shorter chat instructions refer to the standalone `tools/pyz_bootstrap.py`
  helper. Every handoff includes the helper and verifies its size and SHA-256.
- Task Bundle format 3 and Result Bundle format 5 require the exact product
  version. Historical readers and migration paths are removed. Internal task
  execution names use `execute`; public CLI aliases and the separate deprecated
  ScriptBundle runner remain available.
- A single current Core-PYZ profile supports CPython 3.10+. Prepared packages
  use their own verified resources and do not fall back to another installation.
- Watcher stop notifications avoid the non-reentrant Event lock in signal
  handlers. Windows helper bytes use canonical LF line endings, and timing
  tests compare phases with independently observed work intervals.

## Updating from 2.0.0

Install the reviewed 2.0.1 artifact following the
[installation instructions](install-and-update.md). Version 2.0.1 accepts only
packages produced for 2.0.1, including when their format numbers are unchanged.
There is no package or replay-state migration. Existing unsupported files are
preserved and rejected rather than silently rewritten.

After updating the tool, create a new Result directly from the actual repository:

```sh
patchharbor bundle /absolute/path/to/repository
```

Use that fresh Result to prepare subsequent Task Bundles. Updating repository
source files alone does not change an already installed watcher or CLI.

## Release files

The official workflow builds and verifies these five files on the exact `dev`
commit, then publishes the original candidate bytes after native CI succeeds:

- `patchharbor-2.0.1.pyz`
- `patchharbor-2.0.1-py3-none-any.whl`
- `patchharbor-2.0.1.tar.gz`
- `runtime-manifest.json`
- `SHA256SUMS`

The manifest records source and runtime identities. Verify the checksums and an
independently trusted PYZ hash before importing the portable runtime.
