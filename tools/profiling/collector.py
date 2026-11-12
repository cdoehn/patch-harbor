"""Explicit pytest collector. Import alone neither profiles nor writes anything."""
from __future__ import annotations

from contextlib import contextmanager
import cProfile
import json
import os
from pathlib import Path
import pstats
import sys
import threading
import time
import tracemalloc
import uuid

import pytest

from tools.profiling.coverage import collector_coverage

from tools.profiling.profiles import function_rows, memory_record


class Collector:
    def __init__(self, config):
        self.config = config
        self.mode = os.environ['PH_PROFILE_MODE']
        self.directory = Path(os.environ['PH_PROFILE_DIRECTORY'])
        self.measurement = os.environ['PH_PROFILE_MEASUREMENT']
        self.process = str(uuid.uuid4())
        self.sequence = 0
        self.memory_owned = False
        self.memory_error = None
        if self.mode == 'memory':
            try:
                if tracemalloc.is_tracing():
                    raise ValueError('another tracemalloc owner is active')
                tracemalloc.start(8)
                self.memory_owned = True
            except Exception as exc:
                self.memory_error = type(exc).__name__

    def write(self, row):
        path = self.directory / ('collector-' + self.process + '-' + str(self.sequence) + '.json')
        content = json.dumps(row, sort_keys=True, allow_nan=False).encode()
        if len(content) > 4 * 1024 * 1024:
            row.update(status='partial', reason='collector record byte limit', functions=[], memory={})
            content = json.dumps(row, sort_keys=True, allow_nan=False).encode()
        with path.open('xb') as stream:
            stream.write(content)

    @contextmanager
    def span(self, phase, nodeid=None):
        self.sequence += 1
        row = dict(format_version=2, measurement_id=self.measurement, mode=self.mode,
                   process_id=self.process, pid=os.getpid(), parent_pid=os.getppid(),
                   thread_id=threading.get_ident(), native_thread_id=threading.get_native_id(),
                   worker=getattr(self.config, 'workerinput', {}).get('workerid'),
                   nodeid=nodeid, phase=phase, status='complete', reason=None,
                   start_ns=time.perf_counter_ns(), start_utc_ns=time.time_ns(),
                   start_process_cpu_ns=time.process_time_ns(),
                   cpu_scope='whole pytest process, including other threads; excludes children',
                   coverage=collector_coverage(self.mode),
                   thread_id_role='boundary-observer',
                   timer='perf_counter; profile time is not a benchmark or CPU time')
        profiler, snapshot, before = None, None, None
        try:
            if self.mode == 'cprofile':
                if sys.getprofile() is not None:
                    raise ValueError('another Python profiler is active')
                profiler = cProfile.Profile()
                profiler.enable()
            elif self.mode == 'memory':
                if not self.memory_owned or not tracemalloc.is_tracing():
                    raise ValueError(self.memory_error or 'memory collector was stopped')
                before = tracemalloc.get_traced_memory()[0]
                snapshot = tracemalloc.take_snapshot()
                tracemalloc.reset_peak()
        except Exception as exc:
            row.update(status='partial', reason='collector start: ' + type(exc).__name__)
        try:
            yield
        finally:
            row.update(end_ns=time.perf_counter_ns(), end_utc_ns=time.time_ns(),
                       end_process_cpu_ns=time.process_time_ns())
            overhead = time.perf_counter_ns()
            try:
                if profiler is not None:
                    profiler.disable()
                    raw = 'python-' + self.process + '-' + str(self.sequence) + '.prof'
                    profiler.dump_stats(str(self.directory / raw))
                    row['raw_profile'] = raw
                    functions, truncated = function_rows(pstats.Stats(profiler).stats)
                    if truncated:
                        row.update(status='partial', reason='function inventory limit')
                    row['functions'] = functions
                if snapshot is not None:
                    current, peak = tracemalloc.get_traced_memory()
                    after = tracemalloc.take_snapshot()
                    difference = after.compare_to(snapshot, 'traceback')
                    row['memory'] = memory_record(before, current, peak, difference)
            except Exception as exc:
                row.update(status='partial', reason='collector end: ' + type(exc).__name__)
            finally:
                row['serialization_preparation_ns'] = time.perf_counter_ns() - overhead
                try:
                    self.write(row)
                except OSError:
                    # The controller requires every phase record; missing output
                    # remains incomplete without replacing the actual test result.
                    pass


def observer(config):
    collector = getattr(config, '_ph_local_profile', None)
    if collector is None:
        if os.environ.get('PH_PROFILE_MODE') not in ('cprofile', 'memory'):
            raise ValueError('profiling plugin requires an explicit local run')
        collector = config._ph_local_profile = Collector(config)
    return collector


@pytest.hookimpl(hookwrapper=True, tryfirst=True)
def pytest_load_initial_conftests(early_config, parser, args):
    with observer(early_config).span('initial_conftests'):
        yield


@pytest.hookimpl(hookwrapper=True, tryfirst=True)
def pytest_collection(session):
    with observer(session.config).span('collection'):
        yield


@pytest.hookimpl(hookwrapper=True, tryfirst=True)
def pytest_runtest_setup(item):
    with observer(item.config).span('setup', item.nodeid):
        yield


@pytest.hookimpl(hookwrapper=True, tryfirst=True)
def pytest_runtest_call(item):
    with observer(item.config).span('call', item.nodeid):
        yield


@pytest.hookimpl(hookwrapper=True, tryfirst=True)
def pytest_runtest_teardown(item, nextitem):
    with observer(item.config).span('teardown', item.nodeid):
        yield


@pytest.hookimpl(trylast=True)
def pytest_sessionfinish(session, exitstatus):
    collector = getattr(session.config, '_ph_local_profile', None)
    if collector is not None and collector.memory_owned:
        tracemalloc.stop()
