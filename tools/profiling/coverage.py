"""Describe collector coverage without inventing per-thread function ownership."""
import sys


def collector_coverage(mode):
    threads = 'unobserved'
    if mode == 'memory':
        threads = 'all'
    elif mode == 'cprofile':
        # CPython 3.12 replaced the thread-local profile hook with monitoring
        # events for the interpreter. Never infer an unreviewed backend's scope.
        minor = sys.version_info[:2]
        if sys.implementation.name == 'cpython' and (3, 10) <= minor < (3, 12):
            threads = 'current'
        elif sys.implementation.name == 'cpython' and (3, 12) <= minor <= (3, 14):
            threads = 'interpreter'
        else:
            threads = 'unknown'
    return {'python_threads': threads, 'python_thread_attribution': 'not-separated',
            'phase_attribution': 'observer-interval', 'test_exclusive': False,
            'children': 'unobserved', 'rss': 'unobserved',
            'initial_interpreter_imports': 'unobserved', 'phase_includes_hooks': True}
