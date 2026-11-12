"""Local full-suite capacity estimates with tenfold headroom, not allocations."""
from dataclasses import asdict, dataclass, replace
import math


HEADROOM = 10
# Conservative planning envelope for 5,000 tests, three phases, instrumented
# startup and subprocess-heavy tests. These are estimates, not host measurements.
EXPECTED = {
    'timeout_s': 12 * 3600,
    'artifact_bytes': 32 * 1024**3,
    'artifact_files': 150_000,
    'report_bytes': 64 * 1024**2,
    'collector_records': 20_000,
    'record_bytes': 4 * 1024**2,
    'functions': 10_000,
    'callers': 10_000,
    'profile_rows': 15_000_000,
    'trace_events': 100_000_000,
    'trace_rows': 1_000_000,
}


@dataclass(frozen=True)
class Limits:
    timeout_s: float
    artifact_bytes: int
    artifact_files: int
    report_bytes: int
    collector_records: int
    record_bytes: int
    functions: int
    callers: int
    profile_rows: int
    trace_events: int
    trace_rows: int

    def __post_init__(self):
        for name, value in asdict(self).items():
            if name == 'timeout_s':
                valid = type(value) in (float, int) and math.isfinite(value) and value > 0
            else:
                valid = type(value) is int and value > 0
            if not valid:
                raise ValueError('invalid profiling budget: ' + name)
        if self.artifact_bytes < 1024:
            raise ValueError('artifact budget must be at least 1 KiB')


def default_limits(scale=1):
    if type(scale) is not int or scale < 1:
        raise ValueError('budget scale must be a positive integer')
    return Limits(**{name: value * HEADROOM * scale for name, value in EXPECTED.items()})


def requested_limits(args):
    overrides = {name: getattr(args, option) for name, option in (
        ('timeout_s', 'timeout'), ('artifact_bytes', 'max_bytes'), ('artifact_files', 'max_files'))
        if getattr(args, option) is not None}
    return replace(default_limits(args.budget_scale), **overrides)


def exceeded(label, observed, limit, option='--budget-scale'):
    if observed > limit:
        return f'{label} budget exceeded: observed={observed}, limit={limit}; increase {option}'
    return None


def require_budget(label, observed, limit, option='--budget-scale'):
    reason = exceeded(label, observed, limit, option)
    if reason:
        raise ValueError(reason)
