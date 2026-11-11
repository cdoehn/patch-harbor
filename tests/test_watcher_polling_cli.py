"""Both command spellings enter the same optional polling component."""
import builtins
from io import StringIO

import pytest

from patchharbor import cli
from patchharbor_watcher import cli as watcher_cli
from tests.registration_support import set_isolated_user_environment


@pytest.mark.parametrize('entry', ['core', 'watcher'])
@pytest.mark.parametrize('arguments,expected', [([], 4), (['--interval', '.5'], .5),
    (['-i', '12'], 12), (['--poll-interval', '1e100'], 1e100)])
def test_poll_commands_share_validated_interval_and_stop_controller(tmp_path, monkeypatch, entry, arguments, expected):
    set_isolated_user_environment(monkeypatch, tmp_path/'user')
    calls = []
    monkeypatch.setattr(watcher_cli, 'run_polling_watcher', lambda **kw: calls.append(kw))
    monkeypatch.setattr(watcher_cli, 'run_repository_watcher', lambda **kw: pytest.fail('native backend used'))
    stdout, stderr = StringIO(), StringIO()
    main, prefix = (cli.main, ['watcher', 'poll']) if entry == 'core' else (watcher_cli.main, ['poll'])
    assert main(prefix + arguments, stdout=stdout, stderr=stderr) == 0
    assert len(calls) == 1 and calls[0]['interval'] == expected
    assert calls[0]['delegate'] is watcher_cli.delegate_to_automatic_execute
    assert calls[0]['log_stream'] is stdout and calls[0]['error_stream'] is stderr
    assert callable(calls[0]['stop_requested']) and callable(calls[0]['wait'])


@pytest.mark.parametrize('entry', ['core', 'watcher'])
@pytest.mark.parametrize('interval', ['0', '-1', 'nan', 'inf', 'not-a-number', '1e999'])
def test_bad_poll_interval_is_usage_error_before_registry_access(monkeypatch, entry, interval):
    monkeypatch.setattr(watcher_cli.api, 'repositories', lambda: pytest.fail('registry accessed'))
    main, prefix = (cli.main, ['watcher', 'poll']) if entry == 'core' else (watcher_cli.main, ['poll'])
    with pytest.raises(SystemExit) as result:
        main(prefix + ['--interval', interval])
    assert result.value.code == 2


def test_poll_cannot_silently_install_event_mode_service(monkeypatch):
    monkeypatch.setattr(watcher_cli, '_install_systemd_user_unit', lambda: pytest.fail('service installed'))
    with pytest.raises(SystemExit) as result:
        watcher_cli.main(['--install-systemd-user-unit', 'poll'])
    assert result.value.code == 2


def test_core_without_optional_watcher_returns_failure_without_loading_other_backend(monkeypatch):
    original = builtins.__import__
    def missing(name, *args, **kwargs):
        if name == 'patchharbor_watcher.cli':
            raise ModuleNotFoundError(name='patchharbor_watcher')
        return original(name, *args, **kwargs)
    monkeypatch.setattr(builtins, '__import__', missing)
    assert cli.main(['watcher', 'poll'], stdout=StringIO(), stderr=StringIO()) == 1
