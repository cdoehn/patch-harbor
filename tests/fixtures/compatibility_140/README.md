# Immutable PatchHarbor 1.4.0 compatibility artifacts

These eight Results and five patches were produced by the original 1.4.0
implementation in small, disposable Git repositories containing public sample
data. The ZIP bytes were copied unchanged. Tests must never regenerate these
files with the current writer or rewrite their embedded runtime capabilities.

`provenance.json` records every archive's original filename, full SHA-256, byte
size, format, four binding values, snapshot members and actual execution facts.
The shared test helper pins the provenance file itself. The fixtures exercise:

| Result | Actual origin | New commits | Archival success evidence |
| --- | --- | --- | --- |
| clean | manual bundle, embedded PYZ | 0 | yes |
| diagnostic | successful diagnostic Apply | 0 | yes, without a commit receipt |
| single | successful Apply, executable payload | 1 | yes |
| multi | successful Apply with successive states | 2 | yes |
| dry-run | Apply dry-run, entrypoint not executed | 0 | no |
| partial-failure | exit 7 after a real commit and further dirty changes | 1 | no |
| dirty | staged, unstaged, deleted and binary untracked files | 0 | no |
| unavailable | genuine unprepared source producer | 0 | no, runtime warning |

The five original Patch-1 archives accompany the five Apply cases. A readable
reference does not imply successful execution, archival permission or a clean
repository. Failed-Apply references bind the actual resulting commit/state,
not the earlier expected commit. Diagnostic success does not imply a commit.

## Producer provenance

The embedded `patchharbor-1.4.0.pyz` was taken from the verified Apply Result
`patchharbor-apply_Result_121920_1029_43a1e8.zip`, SHA-256
`09301a80390bd41410d37a6485d5377071af1d5e96b7946f0b05b7c108d91de1`.
Its 973,604 bytes have SHA-256
`4e0d26997bffe9476e79d98211cef2d93be7899063a0eb3480bea2ffa3d8f594`
and content ID
`3a9f8c9e85c37601095405496523eaf322d3fe5d1539f57a0bc66157816d1560`.
Its declared source commit is **null**, preserved as such. All 102 shipped core
Python modules match the release-tag source bytes at
`282db1ef5c0af8e2a3ecf41f431f80006487dde4`. This comparison is separate provenance,
not a fabricated declaration inside the PYZ.

The `unavailable` Result came from an isolated process using unchanged source
files from that same commit, without prepared runtime resources. No runtime
provider was mocked. Their complete source-file hash inventory is recorded.

Capture used CPython 3.14.4 on Linux. This records historical producer provenance;
the current consumer tests also run in the existing manual CI matrix. Local
Linux evidence does not replace native Windows/interpreter acceptance.

## Tests and controlled reproduction

`tests/test_compatibility_140.py` covers current Reader/Pack/Inspect/Validate,
full binding and modes, conservative Exchange/recovery evidence and altered
copies with unknown formats or corrupt bytes. Only the exact pinned original
PYZ may execute, in a fresh stdlib-only process. Static readers must not import
it. Existing tests continue to exercise the current producer end to end.

The one-time capture tool is `tests/produce_compatibility_140.py`; its hash is
also pinned in the provenance. It uses private temporary repositories and
private user-data paths, makes no push or network call, and removes its sample
repositories afterward. It is not a pytest fixture and is never run by tests.
For an explicitly reviewed recapture, supply the verified original producer,
the verified original unprepared source tree/manifest, the reference name and
full digest, and a **new output directory**. Its `--help` describes the inputs.
Never overwrite these goldens as part of routine maintenance.

Run the full parallel suite with `python tools/run_tests.py --suite all`.
Only Christian starts CI; this fixture adds no CI trigger.
