"""Conservative process/thread and monotonic-to-UTC phase correlation."""
from bisect import bisect_right
from collections import defaultdict


class PhaseIndex:
    """Index once per import; unrelated test phases never scan per syscall."""

    def __init__(self, spans):
        by_thread = defaultdict(list)
        for span in spans:
            by_thread[span['native_thread_id']].append(span)
        self.threads = {}
        for thread, rows in by_thread.items():
            # Preserve the conservative reused-TID rule even if one lifetime has
            # unusable clocks. Filtering must never make its identity seem unique.
            if len({row['process_id'] for row in rows}) != 1:
                continue
            rows = sorted((row for row in rows if abs(
                (row['end_utc_ns'] - row['start_utc_ns']) -
                (row['end_ns'] - row['start_ns'])) <= 50_000_000),
                key=lambda row: row['start_utc_ns'])
            maximum, prefix_ends = -1, []
            for row in rows:
                maximum = max(maximum, row['end_utc_ns'])
                prefix_ends.append(maximum)
            self.threads[thread] = ([row['start_utc_ns'] for row in rows], prefix_ends, rows)

    def assign(self, event):
        indexed = self.threads.get(event['pid'])
        if indexed is None:
            return None
        starts, ends, rows = indexed
        position = bisect_right(starts, event['start_ns']) - 1
        match = None
        while position >= 0 and ends[position] >= event['end_ns']:
            row = rows[position]
            if event['end_ns'] <= row['end_utc_ns']:
                if match is not None:
                    return None
                match = row
            position -= 1
        return match


def assign_phase(event, spans):
    matches = []
    for span in spans:
        if span['native_thread_id'] != event['pid']:
            continue
        # UTC is needed for strace, but monotonic duration detects clock jumps.
        if abs((span['end_utc_ns'] - span['start_utc_ns']) - (span['end_ns'] - span['start_ns'])) > 50_000_000:
            continue
        if span['start_utc_ns'] <= event['start_ns'] and event['end_ns'] <= span['end_utc_ns']:
            matches.append(span)
    if len(matches) != 1:
        return None
    # A reused numeric TID without a proven lifetime is deliberately unassigned.
    if len({s['process_id'] for s in spans if s['native_thread_id'] == event['pid']}) != 1:
        return None
    return matches[0]
