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

Tab switches focus, arrows/j/k select a target, 1–5 switch views, / searches,
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

Live watcher status remains the later VIEW-03 step; unknown watcher status
in this stage does not assert a stopped watcher.

Replay and repository state are rechecked after artifact scans. Concurrent
changes mark the observation stale. An unreadable/oversized artifact makes
candidate selection incomplete. Archived packages retain processing evidence
only through the original Exchange path plus the exact hash and binding.
Copies of one Result count as one source identity; different Results claiming
one run ID are explicitly ambiguous. History shows only the selected repository
and indicates attempts whose Result is absent from the observed inventory.
