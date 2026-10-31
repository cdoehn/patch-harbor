"""Capture source bytes without Git worktree conversion or index refresh."""
from __future__ import annotations

import os
from pathlib import Path

from patchharbor.git_commands import run_git_bytes, nul_records, read_boolean_config
from patchharbor.git_capture import _parse_index, _read_regular_file
from patchharbor.git_objects import (
    BaseTreeEntry, capture_base_bundle_entries, parse_batch_blob_response,
)
from patchharbor.models import GitObjectId, RepositoryPath
from patchharbor.repository import inspect_repository_root
from patchharbor.repository_paths import validate_repository_paths
from patchharbor.repository_state import capture_repository_snapshot, repository_context_from_snapshot
from patchharbor.result_bundle_capture import CapturedResultBundle
from patchharbor.result_bundle_snapshot import build_result_bundle_snapshot
from patchharbor.safe_export_types import SafeExportError, SafeExportErrorCode
from patchharbor.safe_git_patch import literal_patch


def safe_repository(path: Path) -> RepositoryPath:
    # Resolve without object access first: partial clones must not lazily fetch.
    root = Path(run_git_bytes('-C', str(path), 'rev-parse', '--show-toplevel').decode().strip())
    partial = run_git_bytes('config', '--get-regexp', r'^(extensions\.partialclone|remote\..*\.promisor)$',
                            cwd=root, accepted_returncodes=(0, 1))
    if partial:
        raise SafeExportError(SafeExportErrorCode.REPOSITORY, 'safe capture requires a complete local object store')
    return inspect_repository_root(root)


def require_unconverted(repository: RepositoryPath):
    raw = run_git_bytes('ls-files', '-z', cwd=repository.value)
    names = sorted(set(nul_records(raw, 'index paths')))
    if not names:
        return
    autocrlf = run_git_bytes('config', '--null', '--get', 'core.autocrlf', cwd=repository.value,
                            accepted_returncodes=(0, 1)).lower()
    convert_eol = autocrlf not in (b'', b'false\0', b'no\0', b'off\0', b'0\0')
    for cached in (False, True):
        data = run_git_bytes('check-attr', *(('--cached',) if cached else ()), '--all', '-z', '--stdin',
                             cwd=repository.value, input_bytes=b''.join(n + b'\0' for n in names))
        parts = nul_records(data, 'conversion attributes')
        if len(parts) % 3:
            raise SafeExportError(SafeExportErrorCode.REPOSITORY, 'malformed Git attributes')
        attrs = {name: {} for name in names}
        for offset in range(0, len(parts), 3):
            name, key, value = parts[offset:offset + 3]
            if name not in attrs or key in attrs[name]:
                raise SafeExportError(SafeExportErrorCode.REPOSITORY, 'ambiguous Git attributes')
            attrs[name][key] = value
        for name, attributes in attrs.items():
            active = lambda key: attributes.get(key, b'unspecified') not in (b'unspecified', b'unset')
            if any(active(key) for key in (b'filter', b'working-tree-encoding', b'ident')):
                raise SafeExportError(SafeExportErrorCode.UNSUPPORTED_CONVERSION,
                                      'safe capture refuses active filter, encoding or ident attributes')
            if attributes.get(b'text') == b'unset':
                continue
            if convert_eol or active(b'text') or active(b'eol'):
                path = repository.value / os.fsdecode(name)
                try:
                    path.lstat()
                except FileNotFoundError:
                    continue
                content = _read_regular_file(path, core_file_mode=False).content
                if b'\r\n' in content:
                    raise SafeExportError(SafeExportErrorCode.UNSUPPORTED_CONVERSION,
                                          'safe capture refuses potentially normalized CRLF bytes')


def safe_snapshot(repository: RepositoryPath):
    require_unconverted(repository)
    before = capture_repository_snapshot(repository, read_only=True)
    require_unconverted(repository)
    after = capture_repository_snapshot(repository, read_only=True)
    if before != after:
        raise SafeExportError(SafeExportErrorCode.STALE, 'source changed during safe observation')
    return after


def capture_safe_result(repository, repo_id):
    before = safe_snapshot(repository)
    context = repository_context_from_snapshot(repository, repo_id, before)
    base = capture_base_bundle_entries(repository, before.base_commit)
    index = _parse_index(run_git_bytes('ls-files', '--stage', '-z', cwd=repository.value), before.base_commit.object_format)
    paths = {p.original_bytes: p for p in validate_repository_paths(e.path for e in index)}
    entries = tuple(BaseTreeEntry(paths[e.path], e.mode,
                                 GitObjectId(e.object_name.decode(), before.base_commit.object_format)) for e in index)
    raw = run_git_bytes('cat-file', '--batch', cwd=repository.value,
                        input_bytes=b''.join(str(e.object_id).encode() + b'\n' for e in entries)) if entries else b''
    blobs = parse_batch_blob_response(raw, entries)
    base_tree = {e.path.original_bytes: (e.mode, bytes(e.content)) for e in base}
    index_tree = {e.path.original_bytes: (e.mode, bytes(e.content)) for e in blobs}
    worktree = dict(index_tree)
    file_modes = read_boolean_config(repository.value, 'core.fileMode')
    for record in before.state.unstaged:
        if record.worktree_kind == b'missing':
            del worktree[record.path]
        else:
            mode = record.worktree_mode if file_modes else index_tree[record.path][0]
            worktree[record.path] = (mode, record.worktree_content)
    algorithm = before.base_commit.object_format.value
    snapshot = build_result_bundle_snapshot(
        base_entries=((e.path.original_bytes, e.mode, e.object_id, e.content) for e in base),
        staged_patch=literal_patch(base_tree, index_tree, algorithm=algorithm),
        unstaged_patch=literal_patch(index_tree, worktree, algorithm=algorithm),
        untracked_entries=((r.path, r.mode, r.content) for r in before.state.untracked))
    if safe_snapshot(repository) != before:
        raise SafeExportError(SafeExportErrorCode.STALE, 'source changed during safe capture')
    return CapturedResultBundle(before, context, snapshot)
