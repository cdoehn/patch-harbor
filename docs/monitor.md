# PatchHarbor Monitor

`patchharbor monitor` opens a read-only repository and Exchange overview.
Every process has its own selection, view, filter and scroll position.

```
patchharbor monitor
patchharbor monitor --repo /path/to/repository --view overview
patchharbor monitor --exchange /path/to/exchange --view exchanges
patchharbor monitor --once --json
```

Git state is green when clean, red when dirty and unknown when unavailable.
Staged, unstaged and untracked counts are separate; ignored files do not count.
A clean observation is not a reservation. Old data are marked stale.
The monitor neither executes a patch nor changes registry, replay or Git state.
Discovery and each repository have independent bounded child queries. One slow
repository cannot delay a healthy peer. At most four repository queries and two on-demand detail queries run per viewer,
and repeated refresh requests never duplicate an in-flight source. Default
interval is 5 seconds, query budget 10 seconds (0.1–60 configurable).
Registry responses and child output are limited to four MiB and 256 targets. Unsupported Git conversions are reported as unknown without running
filters. The existing safe capture primitives are reused; the separate source-safe
export host contract is not extended by this viewer.

Tab switches focus, arrows/j/k select a target, 1–7 switch views, / searches,
s reverses order, r requests refresh, ? shows help, q closes this viewer.
`--plain`, `--no-color` and NO_COLOR disable colors. JSON requires --once.
Views 3/4/5 show packages, retained history and Result logs. Tab focuses the
artifact list; / filters names, full hashes and run IDs there. Select a Result
then press 5 for its log; arrows scroll that log. `a` / `--archive` includes the
configured archive. `--artifact-match` initializes the artifact filter.

The automatic candidate is an observation from native content validation,
full binding equality and the native newest-mtime/tie-break ordering. It is
never reserved. Replay status, archive placement and outcomes are separate;
`attempted` is not evidence of a live process. Results link only through full
patch hashes and bindings. Equal states are possible source references, not a
unique parent ZIP. Retained history is explicitly incomplete. Exit 0/success is
green; primary failure or failed Result publication is red. Dry-run says
validation and never pretends to be an applied patch.

Artifact observations are limited to 256 files / 256 MiB total, 64 MiB per input,
128 MiB expanded ZIP data. Logs show at most their last 64 KiB. Limits/errors
are explicit, and terminal control characters are neutralized. Each selected
repository is refreshed no more often than every 10 seconds by default.

Views 6/7 show watcher/Apply instances and their live log tails. Each instance
has its own UUID, PID plus native process birth identity, timestamps and actual
phase. The Apply detail shows requested and effective timeout separately; the
effective value appears only when the interpreter really starts. Remaining time
is a timeout budget, never a completion estimate. Watcher targets, subscriptions,
quiet deadlines and observed lock/backoff state come from its event loop.
Absence of a current observation is unknown, never stopped or unlocked.

Producers publish optional version-1 observations under the user state directory
in `monitor-v1`, outside configured Exchanges. They update bounded memory and
one background thread coalesces disk writes; failures never change Apply or
watcher results. No viewer is needed. Each Apply retains at most 32 KiB of live
output; its required execution log remains byte-exact and unbounded by this view.
Heartbeat freshness is 15 seconds, checked against a native process birth token
on Linux and Windows. Viewers only read these files. Existing running processes
begin publishing after their normal next start with the updated code; this
feature does not restart or install services.

Replay and repository state are rechecked after artifact scans. Concurrent
changes mark the observation stale. An unreadable/oversized artifact makes
candidate selection incomplete. Archived packages retain processing evidence
only through the original Exchange path plus the exact hash and binding.
Copies of one Result count as one source identity; different Results claiming
one run ID are explicitly ambiguous. History shows only the selected repository
and indicates attempts whose Result is absent from the observed inventory.

Content is read and hashed once per artifact observation; native parsers share
that byte capture. At most 32 small fact records are reused for duplicate hashes
within a scan; ZIP contents are not cached. Each viewer retains at most eight
64 KiB log tails for 60 seconds, keyed by full path and hash. `r` bypasses the
log cache. Artifact and log timestamps describe the observed data, not freshness
of the screen redraw.

The reader validates the versioned envelope, identities, timestamps, outcomes
and bounded watcher data. Invalid records are isolated. PID reuse, missing birth
identity, expired heartbeat and clock discontinuities are unknown/stale, never
active. Fact timestamps and heartbeat timestamps are distinct. Concurrent runs
have independent files even when existing Core locks reject one admission.
A bounded final flush cannot hold up execution; if observation completion is
lost, readers retain unknown/stale evidence rather than inventing success.
Publishers retain the newest 128 completed records; active/unknown records and
unrelated files are untouched. Readers cap directory entries at 512 and returned
instances at 64, with an explicit incomplete flag. A selected instance is queried
directly. The viewer never performs retention or recovery.

Tab cycles repository selection, artifact/instance list and scrollable detail
text in the corresponding views. Long relation lists remain readable in the
detail focus. Unchanged screens are not redrawn. The display separates the
expected starting state from a Result's captured resulting state, and exposes
incomplete inventories even when the selected Result itself is valid.

Implementation boundaries: `monitor_live_schema` owns the closed data contract,
`monitor_live_storage` owns bounded reads/retention, and `monitor_live` owns the
optional asynchronous publisher. The watcher supplies facts from its scheduling
state through its existing observation module. Neither presentation nor readers
control execution or infer lock ownership from files.
