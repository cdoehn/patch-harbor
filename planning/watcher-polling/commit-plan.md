# Explicit polling watcher

User request, 10 November 2026: add `patchharbor watcher poll`, default four
seconds and a freely configurable interval, for filesystems such as CIFS where
native notifications are unavailable.

Bundle 084, one OFF-PLAN commit `WATCH-POLL-084` based on confirmed Apply Result
`e415fbba-fdbe-4cee-a85b-9155343a806d`, clean commit
`9643cdf442853e248c6a4d5d16b74af9ff7f0763`.

The full installation exposes the command and equivalent standalone watcher
subcommand. Polling refreshes Core-supplied scopes, invokes the existing isolated
automatic worker, and waits after completion. Finite positive fractional
intervals, nonoverlap, responsive stop, unavailable-Exchange recovery and the
existing replay/locking boundary are required. Native event mode remains its
own default. The Core-PYZ stays watcher-free through a lazy CLI-only adapter.
Monitor evidence reports mode, interval and the next scheduled poll.

Development validation is a parallel selection of watcher, CLI, architectural,
live observation and relevant PYZ/packaging tests, including real automatic
Apply without native events and failed-identity replay suppression. No full
Development suite and no serial gate. Apply must run the complete parallel
suite before the one actual commit and one normal push to dev. No CI dispatch,
tag, release publication, main update, service replacement or system installation
is part of this bundle. Existing v1.9.0 release assets and tag stay unchanged.

Commit: `feat(watcher): add configurable polling mode [WATCH-POLL-084]`.
Durable selected-test evidence, package verification and actual Apply outcome
belong in the project's Exchange reports. A delivered bundle is not itself an
Apply or installation success claim.
