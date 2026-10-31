# Complete runtime releases

The existing `acceptance-tests.yml` workflow has three explicit
`workflow_dispatch` actions: `prepare`, `none` (acceptance) and `publish`.
There are no push, tag, scheduled or automatic retry triggers. Every official
build and every release from 1.8.0 onward requires its own Core-PYZ as well as
wheel and built sdist. A source archive supplied by GitHub does not replace them.
The workflow is generic: filenames derive from the requested actual version.

The release operator records the complete confirmed Apply commit and verifies
that it was normally pushed to `dev`. Local Development evidence is a documented
parallel selection. Apply must complete its full parallel suite before each
actual commit. The Apply entrypoint never tags, runs CI or publishes a release.
Historical releases are not rebuilt or relabeled.

1. Dispatch `prepare` on `dev` with `release_version`, `expected_commit` (full
   40-character SHA) and a unique `handoff_id`. The job refuses a different or
   dirty checkout or an existing conflicting tag. It builds once, installs
   wheel and sdist freshly, exports through API/CLI/PYZ without Git or network,
   and runs the clean/dirty public consumer proof. Preparation needs no tag or
   previous CI. The `patchharbor-prepared-release` artifact holds the exact
   candidate assets and evidence for 14 days. Record its Run-ID and download it.
2. Check the candidate manifest and full hashes, and record whether the release
   tag already exists. For this expressly authorized 1.8.0 delivery, create the
   new tag at exactly the confirmed commit after these local gates, then start
   CI. Never move an existing tag or overwrite its assets. Record the created
   ref/object identity for a possible rollback.
3. Dispatch `none` with the same full `expected_commit` and another unique
   `handoff_id`. This runs the existing 13 native Python/Linux/Windows/shell and
   Docker lanes. Wait for the complete run and retain its Run-ID. On failure,
   remove only this attempt's newly created tag after rereading its exact
   identity and checking that no release was published. Preserve a preexisting
   or changed tag. Correct the proved failure through Apply before trying a new
   candidate. Never treat a green run at another HEAD as release approval.
4. Dispatch `publish` on the same commit with `release_version`,
   `expected_commit`, `acceptance_run_id` and `prepared_run_id`. It verifies the
   successful exact-commit preparation run, downloads its original files,
   validates all acceptance artifacts and compares every lane's canonical PYZ
   hash with the candidate. No candidate rebuild occurs. An existing exact tag
   is mandatory before writing a release. Write permission exists only here.
5. The publisher creates a marked draft or resumes only its own matching draft,
   uploads the exact five files without clobber, downloads all draft assets and
   compares them with the originals, then publishes. It downloads the published
   assets again and saves `published.json`. An already identical published
   release is verified and recorded without rewriting it. Conflicts stop the
   operation. GitHub has no atomic multi-asset publication transaction.

Example preparation and acceptance dispatches (set the actual full values):

```bash
gh workflow run acceptance-tests.yml --repo cdoehn/patch-harbor --ref dev -f release_action=prepare -f release_version="$VERSION" -f expected_commit="$COMMIT" -f handoff_id="$PREPARE_ID"
gh workflow run acceptance-tests.yml --repo cdoehn/patch-harbor --ref dev -f release_action=none -f expected_commit="$COMMIT" -f handoff_id="$CI_ID"
gh workflow run acceptance-tests.yml --repo cdoehn/patch-harbor --ref dev -f release_action=publish -f release_version="$VERSION" -f expected_commit="$COMMIT" -f acceptance_run_id="$CI_RUN" -f prepared_run_id="$PREPARE_RUN" -f handoff_id="$PUBLISH_ID"
```

The required download files for a version `X.Y.Z` are:

- `patchharbor-X.Y.Z.pyz`
- `patchharbor-X.Y.Z-py3-none-any.whl`
- `patchharbor-X.Y.Z.tar.gz`
- `runtime-manifest.json`
- `SHA256SUMS`

`runtime-manifest.json` is UTF-8 JSON with `marker:
"patchharbor-runtime-release"`, integer `format_version: 1`, `version`, full
`source_commit`, `tag`, `runtime`, `integration_capabilities` and
`capability_host`. `runtime` contains `filename`, integer `size`, full `sha256`,
`profile`, `requires_python` and `content_id`. Capabilities are queried from the
actual PYZ and bound to the observed OS, machine, Python and implementation.
They do not imply the same host capabilities on another platform. A prepared
manifest's `tag` names the intended release; it does not assert that a tag exists.
Release provenance is external metadata and does not alter canonical PYZ bytes.

`SHA256SUMS` has four LF-terminated lines, sorted by filename, each containing
the full lowercase SHA-256, two spaces and the basename. It includes the
manifest and three built files, and excludes itself. The manifest contains
neither its own hash nor a checksum-file hash. Assets contain no local absolute
paths, private logs, secrets or work directories.

Copy final download evidence and the machine-readable downstream handoff to
the project's durable Exchange reports area. Include Bundle/Result identity,
full commit, release/download URLs, actual PYZ bytes/hash, native CI links,
capabilities and consumer proofs. Expiring Actions storage or a draft alone
does not complete publication. An administrator's ability to bypass this
workflow is not a product guarantee. [Consumer instructions](runtime-export.md)
explain independent hash trust and the direct import path.
