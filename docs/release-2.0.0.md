# PatchHarbor 2.0.0 candidate and outstanding acceptance

Version `2.0.0` is a source/package value. This draft does not prove a successful
Apply, native CI, an existing tag, a GitHub release or a system installation.
The complete [release procedure](release-runtime.md) and its exact-commit gates
remain authoritative. No intermediate push or tag is part of this bundle.

After the final local Apply commit passes its full parallel suite, the existing
build and distribution verifiers can prepare the five candidate assets locally:

```sh
python scripts/prepare_local_release.py --version 2.0.0 --commit FULL_CONFIRMED_COMMIT --assets build/release-2.0.0-assets --workspace build/release-2.0.0-evidence
```

Both directories must be new and separate. This command uses the existing
canonical build, real wheel/sdist installations, Core-PYZ API/CLI exports,
clean/dirty consumer verification, manifest writer and checksum verifier. It
requires the supported Linux x86-64 safe-reference verification host. It neither
contacts GitHub nor creates a tag, pushes a branch, installs globally or
publishes files. Its receipt is `local-candidate.json`, not a CI/release approval.
Development prepares this command only; tests and candidate execution belong
in Apply for this development task.

The intended assets are `patchharbor-2.0.0.pyz`,
`patchharbor-2.0.0-py3-none-any.whl`, `patchharbor-2.0.0.tar.gz`,
`runtime-manifest.json` and `SHA256SUMS`. Local profiling code and data stay
outside the Core-PYZ. The installed wheel includes the optional watcher.

Outstanding acceptance must remain explicit:

- Bound Apply Results for every prepared WRC state and the final local candidate.
- Native Windows/Linux and all supported Python/shell lanes on the exact final
  commit, triggered manually by the designated operator.
- Event/polling behavior and relevant native CIFS publication constraints; local
  simulations alone do not establish behavior on a different host or mount.
- Exact final-commit canonical bytes across native CI and the approved candidate.
- Separately authorized final push, tag, release, Main integration and installation.

Any source edit after candidate creation requires a fresh candidate and its own
acceptance. Historical green runs and the old 1.9.1 release are not transferable.
