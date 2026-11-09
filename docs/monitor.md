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
Queries run in a bounded isolated child; default interval 5 seconds, query budget
10 seconds. Unsupported Git conversions are reported as unknown without running
filters. The existing safe capture primitives are reused; the separate source-safe
export host contract is not extended by this viewer.

Tab switches focus, arrows/j/k select a target, 1/2 switch views, / searches,
s reverses order, r requests refresh, ? shows help, q closes this viewer.
`--plain`, `--no-color` and NO_COLOR disable colors. JSON requires --once.
Watcher live status and bundle views are the later VIEW-02/03 steps; unknown
watcher status in this stage does not assert a stopped watcher.
