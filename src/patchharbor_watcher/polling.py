"""Explicit timer-driven discovery for filesystems without native notifications."""
from __future__ import annotations

import json
import math
import time

import patchharbor.api as api
from patchharbor_watcher.loop import SharedWatcherEventState, publish_completion

DEFAULT_POLL_INTERVAL = 4.0


def _lifecycle(event, interval, stream):
    stream.write(json.dumps({'event': event, 'scope': 'registered_repositories',
                            'watcher_mode': 'poll', 'poll_interval_seconds': interval}) + '\n')
    stream.flush()


def poll_interval(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError('poll interval must be a number')
    seconds = float(value)
    if not math.isfinite(seconds) or seconds <= 0:
        raise ValueError('poll interval must be finite and greater than zero')
    return seconds


def run_polling_watcher(*, delegate, log_stream, error_stream, stop_requested, wait,
                        interval=DEFAULT_POLL_INTERVAL, target_provider=api.watch_targets,
                        publication_factory=api.watcher_observation,
                        clock=time.monotonic, wall_clock=time.time):
    """Check immediately, then wait after each completed check, with no overlap.

    Core supplies and revalidates every scope. No native event source, directory
    cache, candidate selection, manual retry or alternative Execute path exists
    here. The synchronous worker retains its process group and signal policy.
    """
    interval = poll_interval(interval)
    publication = publication_factory()
    event_state = SharedWatcherEventState()
    last_configuration_error = None
    publication.update(watcher_mode='poll', poll_interval_seconds=interval,
                       next_poll_at=None, subscriptions=[], active_exchanges=[])
    try:
        _lifecycle('watcher_started', interval, log_stream)
        while not stop_requested():
            publication.update(phase='polling', activity_code='polling',
                               activity_message=f'Polling · Exchanges prüfen · Intervall {interval:g} s',
                               next_poll_at=None)
            try:
                targets = target_provider().exchanges
            except (api.PatchHarborError, OSError) as exc:
                message = str(exc)[:1024]
                publication.update(activity_code='configuration-error', activity_status='failure',
                                   targets=[], targets_truncated=False, last_error=message)
                if message != last_configuration_error:
                    error_stream.write(f'patchharbor-watcher: {message}\n')
                    error_stream.flush()
                last_configuration_error = message
            else:
                last_configuration_error = None
                publication.update(targets=[{'directory': str(t.directory),
                    'repository_ids': [str(v) for v in t.repository_ids], 'dirty': False,
                    'quiet_until': None, 'blocked_on': None, 'probe_at': None}
                    for t in targets[:128]], targets_truncated=len(targets) > 128, last_error=None)
                if targets and not stop_requested():
                    publication.update(phase='executing', activity_code='executing',
                                       active_exchanges=[str(t.directory) for t in targets[:128]])
                    result = delegate(exchanges=targets)
                    publish_completion(event_state, result, log_stream, error_stream)
                    progress = result.progress
                    code, status = 'worker-error', 'failure'
                    if progress.status == 'attempted':
                        code = 'execute-completed'
                        status = 'success' if result.process_exit_code == 0 else 'failure'
                    elif progress.status == 'no_candidate':
                        code, status = 'no-candidate', 'waiting'
                    elif progress.status == 'locked':
                        code, status = progress.blocked_on.kind + '-lock', 'waiting'
                    publication.update(activity_code=code, activity_status=status,
                                       active_exchanges=[], automatic_status=progress.status)
                elif not stop_requested():
                    publication.update(activity_code='no-targets', activity_status='waiting')
            if stop_requested():
                break
            deadline = clock() + interval
            publication.update(phase='watching', activity_code='poll-wait', activity_status='waiting',
                               activity_message=f'Polling · wartet auf nächsten Scan · Intervall {interval:g} s',
                               active_exchanges=[], next_poll_at=wall_clock() + interval)
            # Chunk only extremely large waits to respect OS timeout limits;
            # every chunk remains immediately interruptible by the stop event.
            while not stop_requested():
                remaining = deadline - clock()
                if remaining <= 0 or wait(min(remaining, 86400.0)):
                    break
    except BaseException as exc:
        publication.update(last_error=str(exc)[:1024] or type(exc).__name__,
                           activity_code='watcher-error', activity_status='failure')
        raise
    finally:
        publication.update(phase='stopped', active_exchanges=[], next_poll_at=None)
        publication.close()
        _lifecycle('watcher_stopped', interval, log_stream)
