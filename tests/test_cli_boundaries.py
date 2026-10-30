"""Shared CLI boundaries preserve API arguments and machine error contracts."""
from __future__ import annotations

from io import StringIO
import json
from pathlib import Path

import pytest

from patchharbor import api
from patchharbor.cli import main
from patchharbor.errors import configuration_error
from patchharbor.exit_status import exit_code_for_error


@pytest.mark.parametrize('verbose', [False, True])
@pytest.mark.parametrize(('arguments', 'function', 'values'), [
    (['show'], 'configuration', ()),
    (['exchange-directory', 'space ü;$(literal)'], 'configure_exchange_directory',
     (Path('space ü;$(literal)'),)),
    (['bundle-suffix', '.txt'], 'configure_bundle_suffix', ('.txt',)),
    (['bundle-suffix', '--clear'], 'configure_bundle_suffix', ('',)),
    (['bundle-suffix', ''], 'configure_bundle_suffix', ('',)),
    (['archive-dir', '.archive'], 'configure_archive_directory', ('.archive',)),
    (['archive-dir', '--clear'], 'configure_archive_directory', ('',)),
    (['archive-dir', ''], 'configure_archive_directory', ('',)),
])
def test_configuration_calls_api_once_with_exact_values_and_observer(
    tmp_path, monkeypatch, verbose, arguments, function, values,
):
    calls = []
    def operation(*args, **kwargs):
        calls.append((args, kwargs))
        return api.ConfigurationResult(tmp_path / 'config.json', tmp_path, '.txt', 'Archive')
    monkeypatch.setattr(api, function, operation)
    cwd = Path.cwd()
    flags = ['--verbose', '--plain', '--no-color'] if verbose else []
    code = main([*flags, 'configure', *arguments], stdin=StringIO(), stdout=StringIO(), stderr=StringIO())
    assert code == 0 and len(calls) == 1 and Path.cwd() == cwd
    args, kwargs = calls[0]
    assert args == values and set(kwargs) == {'observer'}
    assert callable(kwargs['observer']) if verbose else kwargs['observer'] is None


@pytest.mark.parametrize('verbose', [False, True])
@pytest.mark.parametrize(('arguments', 'function'), [
    (['show'], 'configuration'),
    (['exchange-directory', 'exchange'], 'configure_exchange_directory'),
    (['bundle-suffix', '--clear'], 'configure_bundle_suffix'),
    (['archive-dir', '--clear'], 'configure_archive_directory'),
])
def test_configuration_error_keeps_status_and_emits_no_success_result(
    monkeypatch, verbose, arguments, function,
):
    calls = []
    error = configuration_error('controlled configuration failure')
    def operation(*args, **kwargs):
        calls.append((args, kwargs))
        raise error
    monkeypatch.setattr(api, function, operation)
    stdout, stderr = StringIO(), StringIO()
    flags = ['--verbose'] if verbose else []
    code = main([*flags, 'configure', *arguments], stdin=StringIO(), stdout=stdout, stderr=stderr)
    assert code == int(exit_code_for_error(error)) and len(calls) == 1
    assert stdout.getvalue() == '' and stderr.getvalue()


@pytest.mark.parametrize('json_output', [False, True])
@pytest.mark.parametrize(('arguments', 'function', 'command', 'version'), [
    (['registry', 'list'], 'repositories', 'registry.list', 1),
    (['context', 'repo'], 'context', 'context', 1),
    (['bundle', 'repo'], 'bundle', 'bundle', 1),
    (['inspect', 'patch.zip'], 'inspect_patch', 'inspect', 2),
    (['validate', 'patch.zip'], 'validate_patch', 'validate', 2),
])
def test_query_failure_preserves_json_version_error_category_and_output_channel(
    monkeypatch, json_output, arguments, function, command, version,
):
    error = configuration_error('controlled query failure')
    calls = []
    def refused(*args, **kwargs):
        calls.append((args, kwargs))
        raise error
    monkeypatch.setattr(api, function, refused)
    stdout, stderr = StringIO(), StringIO()
    code = main([*arguments, *(['--json'] if json_output else [])],
                stdin=StringIO(), stdout=stdout, stderr=stderr)
    assert code == int(exit_code_for_error(error)) and len(calls) == 1
    if json_output:
        document = json.loads(stdout.getvalue())
        assert set(document) == {'output_version', 'command', 'success', 'result', 'error', 'process_exit_code'}
        assert document['output_version'] == version and document['command'] == command
        assert document['success'] is False and document['result'] is None
        assert document['process_exit_code'] == code
        assert document['error']['kind'] == error.error_kind.value
        assert document['error']['patchharbor_error_code'] == code
        assert document['error']['emergency_diagnostics_path'] is None
        assert stdout.getvalue().endswith('\n') and stderr.getvalue() == ''
        assert calls[0][1]['observer'] is None
    else:
        assert stdout.getvalue() == '' and stderr.getvalue()
