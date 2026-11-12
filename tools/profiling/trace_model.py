"""Conservative process/thread and monotonic-to-UTC phase correlation."""


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
