"""Pytest timing adapter; failures stay separate from acceptance evidence."""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
import os
from time import perf_counter_ns

import pytest

from tools.timing_model import MAX_EVENTS, PHASES, case_timings, duration


def utc_now():
    return datetime.now(timezone.utc).isoformat()


PLUGIN = 'patchharbor-development-timing'


def install_timing(config, evidence):
    """An observer initialization error is never an acceptance decision."""
    try:
        observer = TimingCapture(config, run_id=evidence['run_id'], binding=evidence['binding'])
        config.pluginmanager.register(observer, PLUGIN)
    except Exception as exc:
        config._ph_timing_error = 'timing initialization: ' + type(exc).__name__


def finish_timing(config, evidence, exitstatus):
    """Keep the optional measurement boundary outside strict report validation."""
    try:
        observer = config.pluginmanager.getplugin(PLUGIN)
        if observer is None:
            raise RuntimeError('timing observer unavailable')
        return observer.finish(evidence, exitstatus)
    except Exception as exc:
        if hasattr(config, 'workerinput'):
            config.workeroutput.pop('ph_telemetry', None)
            return None
        return {'format_version': 1, 'run_id': evidence['run_id'], 'binding': evidence['binding'],
                'status': 'partial', 'errors': [getattr(config, '_ph_timing_error',
                                                       'timing publication: ' + type(exc).__name__)],
                'phases': [], 'missing_workers': list(evidence['started']),
                'workers': {}, 'controller': None}


class TimingCapture:
    """Observe supported pytest hooks; never replace outcomes or fixture values."""

    def __init__(self, config, *, run_id, binding):
        self.config, self.run_id, self.binding = config, run_id, binding
        self.worker = hasattr(config, 'workerinput')
        self.worker_key = config.workerinput['workerid'] if self.worker else 'serial'
        self.origin_ns, self.started_utc = perf_counter_ns(), utc_now()
        self.errors, self.phases, self.fixtures = [], [], []
        self.active_fixtures, self.active_spans, self.workers, self.worker_starts = {}, {}, {}, {}
        self.active_node = None
        self.collection = None
        self.session_start_ns = None
        self.sequence = 0

    def error(self, message):
        if len(self.errors) < 100 and message not in self.errors:
            self.errors.append(message)

    @contextmanager
    def observing(self, label):
        # Exceptions in the observed test/fixture are always outside this guard.
        # Observer errors must never turn a test red or conceal its real failure.
        try:
            yield
        except Exception as exc:
            self.error(label + ': ' + type(exc).__name__)

    def now(self):
        return perf_counter_ns() - self.origin_ns

    def pytest_sessionstart(self, session):
        with self.observing('session start'):
            self.session_start_ns = self.now()

    @pytest.hookimpl(hookwrapper=True, tryfirst=True)
    def pytest_collection(self, session):
        start = None
        with self.observing('collection start'):
            start = self.now()
        yield
        with self.observing('collection end'):
            self.collection = {'start_ns': start, 'end_ns': self.now(), 'inclusive': True}

    @pytest.hookimpl(hookwrapper=True, tryfirst=True)
    def pytest_runtest_protocol(self, item, nextitem):
        self.active_node = item.nodeid
        yield
        self.active_node = None

    @contextmanager
    def phase_span(self, item, phase):
        with self.observing('phase start'):
            self.active_spans[item.nodeid, phase] = {'start_ns': self.now(), 'end_ns': None}
        try:
            yield
        finally:
            with self.observing('phase end'):
                self.active_spans[item.nodeid, phase]['end_ns'] = self.now()

    @pytest.hookimpl(hookwrapper=True, tryfirst=True)
    def pytest_runtest_setup(self, item):
        with self.phase_span(item, 'setup'):
            yield

    @pytest.hookimpl(hookwrapper=True, tryfirst=True)
    def pytest_runtest_call(self, item):
        with self.phase_span(item, 'call'):
            yield

    @pytest.hookimpl(hookwrapper=True, tryfirst=True)
    def pytest_runtest_teardown(self, item, nextitem):
        with self.phase_span(item, 'teardown'):
            yield

    def fixture_consumers(self, item):
        # Read only the resolved cache, never getfixturevalue(): observation must
        # not instantiate fixtures. This guarded adapter is pytest-specific.
        request = getattr(item, '_request', None)
        resolved = getattr(request, '_fixture_defs', None)
        if not isinstance(resolved, dict):
            self.error('fixture consumer cache unavailable')
            return
        for definition in resolved.values():
            row = self.active_fixtures.get(id(definition))
            if row is not None and item.nodeid not in row['consumers']:
                row['consumers'].append(item.nodeid)

    @pytest.hookimpl(hookwrapper=True, tryfirst=True)
    def pytest_runtest_makereport(self, item, call):
        outcome = yield
        with self.observing('phase report'):
            report = outcome.get_result()
            key = item.nodeid, call.when
            candidate = self.active_spans.get(key)
            span = None
            # Subtests request reports while the parent phase is still running.
            # Its interval belongs to the final parent report, after phase end.
            if candidate is not None and candidate['end_ns'] is not None:
                span = self.active_spans.pop(key)
            # Extra report attributes are carried by pytest/xdist serialization.
            # Do not modify duration, outcome, longrepr or strict evidence rows.
            report.ph_timing = {'run_id': self.run_id, 'worker': self.worker_key, 'span': span}
            self.fixture_consumers(item)

    def pytest_runtest_logreport(self, report):
        with self.observing('phase observation'):
            if report.when not in PHASES:
                self.error('non-phase report: ' + str(report.when))
                return
            if len(self.phases) >= MAX_EVENTS:
                self.error('phase event limit reached')
                return
            node = getattr(report, 'node', None)
            worker = node.gateway.id if node is not None else self.worker_key
            meta = getattr(report, 'ph_timing', None)
            subtest = getattr(report, 'context', None) is not None
            span = None
            if (isinstance(meta, dict) and meta.get('run_id') == self.run_id
                    and meta.get('worker') == worker and not subtest):
                span = meta.get('span')
            if isinstance(span, dict):
                start, end = span.get('start_ns'), span.get('end_ns')
                if type(start) is not int or type(end) is not int or start < 0 or end < start:
                    self.error('phase interval incomplete')
                    span = None
            value, missing = None, None
            try:
                value = duration(report.duration)
            except (AttributeError, ValueError, TypeError):
                missing = 'pytest duration unavailable'
                self.error(missing)
            if not subtest and not isinstance(span, dict):
                self.error('phase interval unavailable')
            self.phases.append({'nodeid': report.nodeid, 'worker': worker,
                                'phase': report.when, 'outcome': report.outcome, 'subtest': subtest,
                                'duration_s': value, 'missing_reason': missing,
                                'start_ns': span.get('start_ns') if span else None,
                                'end_ns': span.get('end_ns') if span else None,
                                'interval_scope': 'worker_local_hooks', 'duration_scope': 'pytest_phase'})

    @pytest.hookimpl(hookwrapper=True, tryfirst=True)
    def pytest_fixture_setup(self, fixturedef, request):
        row = None
        with self.observing('fixture start'):
            if len(self.fixtures) >= MAX_EVENTS:
                self.error('fixture event limit reached')
            else:
                self.sequence += 1
                row = {'id': f'{self.worker_key}:{self.sequence}', 'name': fixturedef.argname,
                       'worker': self.worker_key, 'scope': request.scope, 'scope_nodeid': request.node.nodeid,
                       'parameterized': hasattr(request, 'param'),
                       'parameter_index': getattr(request, 'param_index', None),
                       'setup_start_ns': self.now(), 'setup_end_ns': None, 'setup_outcome': None,
                       'finalized_ns': None, 'teardown_s': None,
                       'teardown_reason': 'post-finalizer hook has no start boundary',
                       'inclusive': True, 'consumers': [self.active_node] if self.active_node else []}
                self.fixtures.append(row)
                self.active_fixtures[id(fixturedef)] = row
        outcome = yield
        with self.observing('fixture end'):
            if row is not None:
                row['setup_end_ns'] = self.now()
                row['setup_outcome'] = 'raised' if outcome.excinfo is not None else 'returned'

    def pytest_fixture_post_finalizer(self, fixturedef, request):
        with self.observing('fixture finalizer'):
            row = self.active_fixtures.pop(id(fixturedef), None)
            if row is not None:
                row['finalized_ns'] = self.now()

    @pytest.hookimpl(optionalhook=True)
    def pytest_configure_node(self, node):
        with self.observing('worker start'):
            self.worker_starts[node.gateway.id] = self.now()

    @pytest.hookimpl(optionalhook=True)
    def pytest_testnodedown(self, node, error):
        with self.observing('worker completion'):
            worker = node.gateway.id
            value = getattr(node, 'workeroutput', {}).get('ph_telemetry')
            if (not isinstance(value, dict) or value.get('run_id') != self.run_id
                    or value.get('binding') != self.binding or value.get('worker') != worker
                    or worker in self.workers):
                self.error('missing, duplicate or foreign worker timing: ' + worker)
                return
            if error:
                self.error('worker terminated: ' + worker)
            value['controller_start_ns'] = self.worker_starts.get(worker)
            value['controller_end_ns'] = self.now()
            self.workers[worker] = value
            for issue in value.get('errors', []):
                self.error(worker + ': ' + issue)

    def local_summary(self, exitstatus):
        launch, launched_utc = None, None
        # Inherited markers in nested pytest processes belong to another launch.
        if (not self.worker
                and os.environ.get('PH_TEST_PROCESS_PARENT_PID') == str(os.getppid())):
            launch = os.environ.get('PH_TEST_PROCESS_START_NS')
            launched_utc = os.environ.get('PH_TEST_PROCESS_START_UTC')
        startup = None
        if launch is not None:
            try:
                start = int(launch)
                if 0 <= start <= self.origin_ns:
                    startup = (self.origin_ns - start) / 1_000_000_000
            except ValueError:
                self.error('invalid launcher start timestamp')
        return {'run_id': self.run_id, 'binding': self.binding, 'worker': self.worker_key,
                'pid': os.getpid(), 'started_utc': self.started_utc,
                'clock': 'perf_counter_ns, origin at observer registration, local to this process',
                'observed_elapsed_ns': self.now(), 'session_start_ns': self.session_start_ns,
                'collection': self.collection, 'fixtures': self.fixtures,
                'exitstatus': int(exitstatus), 'errors': list(self.errors),
                'process_start_utc': launched_utc,
                'launch_to_registration_s': startup,
                'startup_scope': 'local launcher before process creation; absent for direct pytest and workers',
                'session_end_s': None, 'session_end_reason': 'remaining session hooks and report publication unmeasured'}

    def finish(self, evidence, exitstatus):
        """Called before evidence publication, with failures kept in this channel."""
        with self.observing('timing completion'):
            local = self.local_summary(exitstatus)
            if self.worker:
                self.config.workeroutput['ph_telemetry'] = local
                return None
            missing = sorted(set(evidence['started']) - set(self.workers))
            if missing:
                self.error('worker timings incomplete')
            data = {'format_version': 1, 'run_id': self.run_id, 'binding': self.binding,
                    'status': 'partial' if self.errors else 'complete', 'errors': list(self.errors),
                    'missing_workers': missing, 'controller': local,
                    'workers': self.workers, 'phases': self.phases,
                    'walltime_scope': 'controller observation only; never sum worker intervals'}
            candidate = dict(evidence, telemetry=data)
            if any(p['state'] == 'missing' for c in case_timings(candidate) for p in c['phases'].values()):
                data['status'] = 'partial'
            return data
        return {'format_version': 1, 'run_id': self.run_id, 'binding': self.binding,
                'status': 'partial', 'errors': list(self.errors), 'phases': [],
                'missing_workers': list(evidence['started']), 'workers': {}, 'controller': None}
