"""Bounded native content readers, shared by Exchange facts and selected logs."""
from __future__ import annotations

from collections import OrderedDict
from copy import deepcopy

from patchharbor.errors import PatchHarborError
from patchharbor.exchange import ExchangeArtifact, ExchangeArtifactKind
from patchharbor.exchange_state import ExchangeFileIdentity, ExchangeTaskSelection
from patchharbor.task_package import resolve_task_payloads
from patchharbor.platform.filesystem import (PathKind, path_kind, regular_file_state,
    read_stable_regular_file_with_sha256)
from patchharbor.resource_policy import ResourcePolicy
from patchharbor.result_reader import (capture_result_payloads, read_result_or_task_payloads,
    has_result_marker, parse_result_payloads)
from patchharbor.zip_payloads import ZipPayloadError
from patchharbor.monitor_types import observed_at
from patchharbor.monitor_activity import declared_bundle_number
from patchharbor.json_document import parse_json_document

POLICY = ResourcePolicy(max_input_artifact_bytes=64*1024*1024,
                        max_content_bytes=64*1024*1024, max_zip_total_bytes=128*1024*1024)
ERRORS = (PatchHarborError, OSError, ValueError, RuntimeError, TypeError, KeyError, OverflowError)


class ArtifactCache:
    """One scan only; cache small facts, never ZIP payloads; verify bytes every time."""
    def __init__(self):
        self.entries = OrderedDict()

    def capture(self, path):
        captured = read_stable_regular_file_with_sha256(path, retained_content_limit=POLICY.max_input_artifact_bytes,
            max_bytes=POLICY.max_input_artifact_bytes, expected_identity=path.lstat(), allow_path_identity_fallback=True)
        if captured.sha256 in self.entries:
            self.entries.move_to_end(captured.sha256)
            metadata, selection = self.entries[captured.sha256]
        else:
            metadata, selection = self._parse(path, captured)
            self.entries[captured.sha256] = metadata, selection
            while len(self.entries) > 32:
                self.entries.popitem(last=False)
        artifact = ExchangeArtifact(path, ExchangeFileIdentity(path, captured.sha256), captured.mtime_ns,
                                    ExchangeArtifactKind(metadata['kind']), selection)
        return deepcopy(metadata), artifact, captured.size

    def _parse(self, path, captured):
        try:
            payloads = read_result_or_task_payloads(captured.content, policy=POLICY)
        except ZipPayloadError:
            return {'kind': 'other'}, None
        if has_result_marker(payloads):
            facts = parse_result_payloads(payloads, resource_policy=POLICY)
            run = parse_json_document(next(p.content for p in payloads if p.relative_path == 'logs/run.json'))
            return dict(kind='result_bundle', repo_id=str(facts.context.repo_id), context=binding(facts.context),
                expected=binding(facts.expected), run_id=facts.run_id, operation=facts.operation,
                dry_run=facts.dry_run, primary_result=facts.primary_result.as_document(),
                result_status='created', task_sha256=facts.task_sha256,
                started_at=run['started_at'], ended_at=run['ended_at'],
                completed_commit=str(facts.completed_commit) if facts.completed_commit else None), None
        try:
            package = resolve_task_payloads(payloads, resource_policy=POLICY, package_path=path,
                package_sha256=captured.sha256, package_size=captured.size)
        except PatchHarborError as exc:
            if 'unsupported PatchHarbor package version' in str(exc):
                return {'kind': 'other', 'error': str(exc)}, None
            return {'kind': 'other'}, None
        return {'kind': 'task_bundle', 'bundle_number': declared_bundle_number(package.entrypoint.content),
                'entrypoint_name': package.entrypoint.relative_path}, ExchangeTaskSelection.from_manifest(package.manifest)


def binding(value):
    if value is None:
        return None
    return {name: str(getattr(value, name)) for name in
            ('repo_id', 'base_commit', 'state_fingerprint', 'fingerprint_algorithm')}


def artifact_fact(path, archived, state, cache):
    row = {'path': str(path), 'name': path.name, 'archived': archived, 'kind': 'unknown',
           'sha256': None, 'repo_id': None, 'error': None}
    try:
        if path.resolve(strict=True) != path:
            raise ValueError('artifact path resolves outside the observed directory')
        before = regular_file_state(path)
        if path_kind(path) is not PathKind.REGULAR_FILE:
            raise ValueError('not a regular file; not followed')
        if path.stat().st_size > POLICY.max_input_artifact_bytes:
            raise ValueError('artifact exceeds the 64 MiB observation limit')
        metadata, artifact, size = cache.capture(path)
        row.update(metadata)
        row.update(sha256=artifact.identity.sha256, kind=artifact.kind.value,
                   mtime_ns=artifact.mtime_ns, size=size)
        if artifact.selection is not None:
            expected = binding(artifact.selection)
            identity = artifact.identity
            record = state.record_for(identity)
            if archived and record is None:
                identity = ExchangeFileIdentity(path.parent.parent / path.name, artifact.identity.sha256)
                record = state.record_for(identity)
            if record and (record.kind != 'task_bundle' or record.manifest != artifact.selection):
                raise ValueError('replay classification disagrees with validated package')
            row['replay_source_path'] = str(identity.path) if record else None
            row.update(repo_id=expected['repo_id'], expected=expected,
                       replay_status=record.execute_status.value if record and record.execute_status else None,
                       attempt_run_id=record.attempt_run_id if record else None,
                       result_sha256=record.result_sha256 if record else None,
                       completed_commit=str(record.completed_commit) if record and record.completed_commit else None)
        if regular_file_state(path) != before:
            raise ValueError('artifact changed during observation')
        return row, artifact
    except ERRORS as exc:
        row.pop('primary_result', None)
        row['error'] = str(exc)
        return row, None


def monitor_log(path, expected_sha256):
    if path_kind(path) is not PathKind.REGULAR_FILE:
        raise ValueError('log source must be a regular Result file')
    captured = capture_result_payloads(path, resource_policy=POLICY, expected_identity=path.lstat())
    if captured.sha256 != expected_sha256:
        raise ValueError('selected Result identity changed; refresh the artifact list')
    logs = {p.relative_path: p.content for p in captured.payloads if p.relative_path in ('logs/execution.log', 'logs/run.json')}
    content = logs.get('logs/execution.log', logs.get('logs/run.json', b''))
    tail = content[-64*1024:]
    return {'sha256': captured.sha256, 'run_id': captured.facts.run_id,
            'truncated': len(tail) < len(content), 'text': tail.decode('utf-8', errors='replace'),
            'observed_at': observed_at()}
