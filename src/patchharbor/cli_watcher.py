"""Lazy CLI bridge to the optional watcher, absent from the Core-only PYZ."""
from __future__ import annotations


def watcher_command(args, *, stdout, stderr):
    try:
        from patchharbor_watcher.cli import main
    except ModuleNotFoundError as exc:
        if exc.name not in ('patchharbor_watcher', 'patchharbor_watcher.cli'):
            raise
        print('patchharbor: watcher requires the full PatchHarbor installation; '
              'install the wheel. The Core-PYZ does not include the watcher.', file=stderr)
        return 1
    return main(['poll', '--interval', str(args.interval)], stdout=stdout, stderr=stderr)
