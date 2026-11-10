"""Closed version-1 observation contract shared by publishers and readers."""
from datetime import datetime
import math
from uuid import UUID

from patchharbor.json_document import parse_json_document
from patchharbor.result_reader import _primary
from patchharbor.monitor_activity import HISTORY_LIMIT, STATUSES

MAX_DOCUMENT = 256 * 1024


def _stamp(value):
    if type(value) is not str:
        raise ValueError('invalid observation timestamp')
    result = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if result.tzinfo is None:
        raise ValueError('observation timestamp requires a timezone')
    return result


def _uuid(value):
    if type(value) is not str or str(UUID(value)) != value:
        raise ValueError('observation identity must be a canonical UUID')


def _finite(value):
    return type(value) in (int, float) and math.isfinite(value)


def parse_live(content, name):
    row = parse_json_document(content)
    fields = {'format_version', 'kind', 'instance_id', 'pid', 'process_identity',
              'started_at', 'updated_at', 'facts_updated_at', 'completed', 'phase', 'data', 'log_tail'}
    version = row.get('format_version')
    if version == 2:
        fields |= {'activity', 'history'}
    if set(row) != fields or type(version) is not int or version not in (1, 2):
        raise ValueError('unsupported live observation schema')
    _uuid(row['instance_id'])
    if row['kind'] not in (('apply', 'watcher', 'bundle') if version == 2 else ('apply', 'watcher')) or name != row['kind'] + '-' + row['instance_id'] + '.json':
        raise ValueError('live filename and identity disagree')
    if type(row['pid']) is not int or not 0 < row['pid'] <= 2**32-1:
        raise ValueError('invalid publisher PID')
    if row['process_identity'] is not None and (type(row['process_identity']) is not str or not 0 < len(row['process_identity']) <= 128):
        raise ValueError('invalid publisher birth identity')
    _stamp(row['started_at']); _stamp(row['updated_at']); _stamp(row['facts_updated_at'])
    if type(row['completed']) is not bool or type(row['phase']) is not str or len(row['phase']) > 64:
        raise ValueError('invalid publisher lifecycle')
    if type(row['log_tail']) is not str or len(row['log_tail'].encode('utf-8')) > 3*32768:
        raise ValueError('invalid bounded log tail')
    if version == 2:
        if type(row['history']) is not list or len(row['history']) > HISTORY_LIMIT:
            raise ValueError('invalid bounded activity history')
        sequence = 0
        for event in [*row['history'], row['activity']]:
            if type(event) is not dict or set(event) != {'sequence', 'at', 'since', 'code', 'status', 'message'}:
                raise ValueError('invalid activity record')
            if type(event['sequence']) is not int or not sequence < event['sequence']:
                raise ValueError('invalid activity sequence')
            sequence = event['sequence']
            _stamp(event['at']); _stamp(event['since'])
            if type(event['code']) is not str or not 0 < len(event['code']) <= 64 or type(event['status']) is not str or event['status'] not in STATUSES:
                raise ValueError('invalid activity identity/status')
            if type(event['message']) is not str or len(event['message']) > 512:
                raise ValueError('invalid activity message')
    data = row['data']
    allowed = {'message', 'patch_path', 'repo_id', 'repository_path', 'base_commit', 'fingerprint',
        'run_id', 'origin', 'dry_run', 'requested_timeout_seconds', 'effective_timeout_seconds',
        'entrypoint_started_at', 'entrypoint_exit_code', 'process_state', 'primary_result',
        'result_status', 'result_path', 'patch_sha256', 'subscriptions', 'targets',
        'targets_truncated', 'control_lock', 'control_probe_at', 'last_error', 'completion_unknown'}
    if version == 2:
        allowed |= {'entrypoint_name', 'bundle_number', 'active_exchanges', 'automatic_status'}
        allowed |= {'watcher_mode', 'poll_interval_seconds', 'next_poll_at'}
    if type(data) is not dict or set(data) - allowed:
        raise ValueError('unknown live observation data')
    if 'watcher_mode' in data and (row['kind'] != 'watcher' or data['watcher_mode'] not in ('events', 'poll')):
        raise ValueError('invalid watcher mode')
    if data.get('watcher_mode') == 'poll' or any(key in data for key in ('poll_interval_seconds', 'next_poll_at')):
        interval = data.get('poll_interval_seconds')
        if row['kind'] != 'watcher' or data.get('watcher_mode') != 'poll' or not _finite(interval) or interval <= 0:
            raise ValueError('invalid polling interval')
        deadline = data.get('next_poll_at')
        if deadline is not None and (not _finite(deadline) or deadline <= 0):
            raise ValueError('invalid polling deadline')
    if data.get('automatic_status') is not None and data['automatic_status'] not in ('no_candidate', 'attempted', 'locked', 'dry_run', 'error'):
        raise ValueError('invalid automatic outcome')
    if data.get('entrypoint_name') is not None and (type(data['entrypoint_name']) is not str or len(data['entrypoint_name']) > 512):
        raise ValueError('invalid entrypoint name')
    if data.get('bundle_number') is not None and (type(data['bundle_number']) is not str or len(data['bundle_number']) != 3 or any(c not in '0123456789' for c in data['bundle_number'])):
        raise ValueError('invalid declared bundle number')
    if 'active_exchanges' in data and (type(data['active_exchanges']) is not list or len(data['active_exchanges']) > 128 or any(type(p) is not str for p in data['active_exchanges'])):
        raise ValueError('invalid active Exchange scope')
    for key in ('message', 'patch_path', 'repository_path', 'base_commit', 'fingerprint',
                'result_path', 'last_error', 'process_state'):
        if data.get(key) is not None and type(data[key]) is not str:
            raise ValueError('invalid live text field: ' + key)
    for key in ('run_id', 'repo_id'):
        if data.get(key) is not None:
            _uuid(data[key])
    if data.get('patch_sha256') is not None and (type(data['patch_sha256']) is not str or
            len(data['patch_sha256']) != 64 or any(c not in '0123456789abcdef' for c in data['patch_sha256'])):
        raise ValueError('invalid patch digest')
    for key in ('dry_run', 'targets_truncated', 'completion_unknown'):
        if key in data and type(data[key]) is not bool:
            raise ValueError('invalid live boolean')
    for key in ('requested_timeout_seconds', 'effective_timeout_seconds', 'control_probe_at'):
        if data.get(key) is not None and (not _finite(data[key]) or data[key] <= 0):
            raise ValueError('invalid live duration/deadline')
    if data.get('entrypoint_started_at') is not None:
        _stamp(data['entrypoint_started_at'])
    if data.get('effective_timeout_seconds') is not None and data.get('entrypoint_started_at') is None:
        raise ValueError('effective timeout requires actual entrypoint start')
    if data.get('entrypoint_exit_code') is not None and type(data['entrypoint_exit_code']) is not int:
        raise ValueError('invalid exit code')
    if data.get('primary_result') is not None:
        _primary(data['primary_result'])
    if data.get('result_status') is not None and data['result_status'] not in ('created', 'failed', 'not_attempted'):
        raise ValueError('invalid Result publication status')
    if row['kind'] == 'apply' and (not data.get('run_id') or data.get('origin') not in ('manual', 'automatic') or type(data.get('dry_run')) is not bool):
        raise ValueError('incomplete Apply observation')
    targets, subscriptions = data.get('targets', []), data.get('subscriptions', [])
    if type(targets) is not list or len(targets) > 128 or type(subscriptions) is not list or len(subscriptions) > 1024:
        raise ValueError('invalid watcher target list')
    if any(type(path) is not str for path in subscriptions):
        raise ValueError('invalid watcher subscription')
    for target in targets:
        if type(target) is not dict or type(target.get('directory')) is not str:
            raise ValueError('invalid watcher target')
        for key in ('quiet_until', 'probe_at'):
            if target.get(key) is not None and not _finite(target[key]):
                raise ValueError('invalid watcher deadline')
        ids = target.get('repository_ids', [])
        if type(ids) is not list or len(ids) > 256:
            raise ValueError('invalid watcher repository identities')
        for identity in ids:
            _uuid(identity)
        if 'dirty' in target and type(target['dirty']) is not bool:
            raise ValueError('invalid watcher pending state')
    return row
