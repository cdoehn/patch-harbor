# Troubleshooting Apply and Result publication

Start with the actual run, full package SHA-256 and repository state. A filename,
an apparently successful start or a Dry Run is not proof of completed Apply.
Use `patchharbor configure show`, `patchharbor context --json` and read-only
`git status`/`git log` in the intended repository. Human-facing shortened IDs
must not be copied into a package manifest.

## Read the right evidence

An Apply Result contains `logs/run.json` and, when execution started,
`logs/execution.log`. Read the primary execution result separately from the
Result-publication result. Check `dry_run`, actual context, complete binding
and any confirmed partial progress. Inspect/validate are static checks:

```bash
patchharbor inspect /path/to/patch.zip --json
patchharbor validate /path/to/patch.zip --reference-bundle /path/to/result.zip --json
```

`patchharbor apply --verbose` exposes detailed rejection reasons, but a non-dry
Apply can execute a package. Stop a conflicting watcher/orchestrator and review
the actual state before choosing a deliberate manual retry. Use verbose mode on
the initial request or a justified recovery request, not as a harmless log reader.

## Common tool exit codes

| Code | Meaning and next check |
| --- | --- |
| 2 | Usage error: check the command's `--help`. |
| 4 | Invalid/unreadable source, including a rejected Result reference. Preserve the original bytes and inspect the reason. |
| 8 | Repository identity/registration problem. Check the intended local instance and configuration. |
| 9 | Repository state mismatch. Compare the actual base commit and fingerprint; create a fresh Result if state changed. |
| 10 | Invalid patch package. Inspect the reported schema, path, entrypoint or integrity failure. |
| 11 | Result creation/publication failed. Inspect emergency diagnostics and the actual repository before retrying. |
| 12 | Repository busy. Let the owning Apply finish; do not delete lock files. |

These are PatchHarbor tool statuses. Entrypoint exit codes are also preserved
and can have the same numeric values; the run report identifies which occurred.
Timeout/interruption and interpreter failures have their own diagnoses. Do not
infer a test result or repository rollback from an exit number alone.

## Apply succeeded but no Result appeared

The entrypoint can finish, commit and push before Result publication fails.
The process can then exit with code 11 even though those changes remain.
Payload replacement is not a package-wide transaction and there is no automatic
rollback. **Do not blindly rerun the old ZIP.**

Preserve the emergency diagnostics path printed by PatchHarbor. When available,
`run.json`, the execution log and `verification.json` explain the execution and
publication phases. Inspect the actual Git HEAD, working tree and remote evidence
without resetting or cleaning files. Correct the diagnosed publication problem,
then run `patchharbor bundle` from the registered repository to capture the
current state. This new manual bundle is a state snapshot; it does not recreate
the missing Apply receipt or retroactively prove tests, commit or push.

An interrupted `attempted` replay record is not automatically a crashed process.
Existing [recovery checks](repository-workflow.md#recovering-an-interrupted-apply)
require the lock and complete pinned evidence. Leave uncertain attempts intact.

## Large snapshots and shared storage

The current reader and writer allow 250,000 stored repository files and 250,010
outer ZIP entries, with unchanged byte and inner-runtime limits. A message such
as `more than 1000 entries` can identify an older installed outer-ZIP reader;
check the executable, version and artifact actually used. Merely changing a Git
branch does not update the CLI or running watcher. Inner runtime archives still
have their separate 1,000-entry bound. Do not bypass integrity checks or silently
raise unrelated budgets to make a damaged bundle pass.

On Linux with a Windows CIFS Exchange, publication retries only the typed
file-stability condition, first after 2 seconds and then with bounded backoff.
Corrupt content, resource-limit failures and missing files are not converted
into retry success. Preserve `verification.json` and relevant mount options
without credentials. See [CIFS publication](result-publication-cifs.md).

## Watcher is idle or reports no candidate

The watcher uses all registered repositories' configured Exchanges. It observes
top-level filesystem events and waits for five seconds of quiet. Result Bundles,
foreign packages, stale bindings and replay-ineligible packages cannot become
Apply candidates. Repeated identical `no_candidate` messages are suppressed;
silence is not proof that the service stopped.

Check the service and journal, local settings and package binding. Changes only
inside existing subdirectories do not trigger discovery. A Git change alone
does not trigger it either. On network mounts, verify that the OS supplies the
needed native events; Result write retries cannot repair missing watcher events.
A deliberate manual Apply is available. The watcher never silently substitutes
polling or automatically retries an unchanged failed package.

See [watcher operation](watcher-events.md), [safe publication](../README.md#publish-only-complete-zips)
and [updating the installed service](install-and-update.md#update-while-a-watcher-is-installed).
