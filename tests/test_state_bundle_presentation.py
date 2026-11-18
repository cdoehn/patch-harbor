"""User-facing State names remain distinct from Execute outcomes in every view."""
from io import StringIO
import json
from pathlib import Path

import pytest

from patchharbor.cli import main
from patchharbor.monitor_activity import activity_event
from patchharbor.monitor_display import render
from patchharbor.monitor_session import MonitorSession, VIEWS
from patchharbor.progress import ActivityEvent
from tests.test_monitor import registered
from tests.test_monitor_activity import document, NOW, event


@pytest.mark.parametrize('json_output', [False, True])
def test_bundle_command_publishes_and_reports_state(tmp_path, monkeypatch, json_output):
    (repository, _), = registered(tmp_path, monkeypatch)
    output, error = StringIO(), StringIO()
    options = ['--json'] if json_output else []
    assert main(['bundle', str(repository), *options], stdout=output, stderr=error) == 0
    if json_output:
        envelope = json.loads(output.getvalue())
        assert envelope['output_version'] == 2 and envelope['command'] == 'bundle'
        assert envelope['result']['state_bundle_status'] == 'created'
        assert 'result_bundle_path' not in envelope['result']
        path = Path(envelope['result']['state_bundle_path'])
    else:
        line = next(line for line in output.getvalue().splitlines() if line.startswith('State Bundle created: '))
        path = Path(line.removeprefix('State Bundle created: '))
    assert path.is_file() and '_State_Bundle_' in path.name


@pytest.mark.parametrize('view', VIEWS)
def test_state_timeline_keeps_state_label_in_every_view(view):
    doc = document()
    row = doc['live_view']['instances'][0]
    row['kind'] = 'bundle'
    row['data'].update(task_sha256=None, bundle_number=None, entrypoint_name=None)
    row['history'] = []
    row['activity'] = event('result-write', 'running', 'State-Bundle wird geschrieben', 1, -10)
    screen = render(doc, MonitorSession(view=view), now=NOW, width=140, height=35)
    timeline = '\n'.join(screen.splitlines()[2:7])
    assert 'State-Bundle' in timeline and 'Result-Bundle' not in timeline


@pytest.mark.parametrize('operation_kind,label', [('bundle', 'State'), ('execute', 'Result')])
def test_publication_event_uses_known_operation_kind(operation_kind, label):
    item = ActivityEvent('PUBLISH', 'publication completed', 'success')
    _, status, text = activity_event(item, operation_kind=operation_kind)
    assert status == 'success' and text == label + '-Bundle veröffentlicht'
