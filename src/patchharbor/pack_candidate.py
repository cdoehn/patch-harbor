"""Pure target metadata and bounded standard-ZIP construction for packing."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import PurePosixPath, PureWindowsPath
import re
import stat
from typing import BinaryIO
from uuid import UUID
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

from patchharbor.bundle_handoff import (
    ENVIRONMENT_FORMAT_VERSION, ENVIRONMENT_MARKER, MAX_HANDOFF_ENTRY_BYTES,
    PATCH_FILENAME_SCHEMA, RESULT_FILENAME_SCHEMA,
)
from patchharbor.bundle_names import is_browser_temporary_name, validate_bundle_suffix
from patchharbor.bundle_paths import _is_safe_path_segment
from patchharbor.chat_instructions import render_chat_handoff
from patchharbor.errors import FailureReason, PatchHarborError
from patchharbor.json_document import parse_json_document, serialize_json_document
from patchharbor.pack_sources import CapturedSources
from patchharbor.platform.filesystem import FileReadLimitExceeded
from patchharbor.result_reader import CapturedResultReference
from patchharbor.resource_policy import DEFAULT_RESOURCE_POLICY, ResourcePolicy


def _failure(message: str, reason: FailureReason) -> PatchHarborError:
    return PatchHarborError('cannot prepare pack candidate: ' + message, reason)


def _binding(reference: CapturedResultReference) -> dict[str, str]:
    context = reference.facts.context
    return {name: str(getattr(context, name)) for name in
            ('repo_id', 'base_commit', 'state_fingerprint', 'fingerprint_algorithm')}


def _target_environment(reference: CapturedResultReference) -> tuple[dict, tuple[str, ...]]:
    if reference.handoff is not None:
        # These exact immutable bytes came from the complete native reader.
        return parse_json_document(reference.handoff.environment), ()
    context = reference.facts.context
    return {
        'marker': ENVIRONMENT_MARKER, 'format_version': ENVIRONMENT_FORMAT_VERSION,
        'captured_at': None, 'repository_name': None,
        'repository_path': context.repository_path, 'run_id': reference.facts.run_id,
        'exchange_directory': None, 'output_directory': None, 'runtime': None,
    }, ('reference has no recorded environment; unknown target facts remain null',)


def _repository_prefix(document: dict) -> tuple[str, tuple[str, ...]]:
    name = document.get('repository_name')
    if not isinstance(name, str) or not name:
        recorded = document.get('repository_path')
        if isinstance(recorded, str) and recorded:
            syntax = PureWindowsPath if '\\' in recorded or re.match(r'^[A-Za-z]:', recorded) else PurePosixPath
            name = syntax(recorded).name
    if not isinstance(name, str) or not name:
        return 'repository', ('reference has no usable repository name; using repository',)
    prefix = re.sub(r'[^A-Za-z0-9._-]', '_', name).strip('.')[:64].strip('.')
    if not prefix:
        prefix = 'repository'
    elif not _is_safe_path_segment(prefix):
        # Character set, edge dots and length are already constrained above;
        # only a reserved Windows device name can remain here.
        prefix = '_' + prefix
    return prefix, (() if prefix == name else ('repository name adapted for portable package filename',))


@dataclass(frozen=True, slots=True)
class PackMetadata:
    package_id: UUID
    created_at: datetime
    filename: str
    environment: bytes
    warnings: tuple[str, ...]


def prepare_metadata(reference: CapturedResultReference, package_id: UUID,
                     created_at: datetime, *, filename: str | None = None) -> PackMetadata:
    """Use one request identity and only recorded target facts; never host discovery."""
    if not isinstance(package_id, UUID) or package_id.version != 4:
        raise ValueError('package_id must be UUID v4')
    if created_at.tzinfo is None or created_at.utcoffset() != timezone.utc.utcoffset(created_at):
        raise ValueError('created_at must be a timezone-aware UTC datetime')
    suffix = validate_bundle_suffix(reference.bundle_suffix)
    document, warnings = _target_environment(reference)
    if filename is None:
        prefix, adjustments = _repository_prefix(document)
        warnings += adjustments
        filename = f'{prefix}_Patch_{created_at:%H%M%S}_{created_at:%m%d}_{str(package_id)[:6]}.zip{suffix}'
    elif (not filename.endswith('.zip' + suffix) or is_browser_temporary_name(filename)
          or filename in ('.', '..') or any(c in filename for c in '/\\\0')):
        raise _failure('explicit output name must end in .zip plus the reference suffix',
                       FailureReason.PAYLOAD_PREPARATION_ERROR)
    document.update(
        marker=ENVIRONMENT_MARKER, format_version=ENVIRONMENT_FORMAT_VERSION,
        bundle_type='Patch', bundle_filename=filename,
        repository_context=_binding(reference), bundle_suffix=suffix,
        filename_schemas={'Patch': PATCH_FILENAME_SCHEMA, 'Result': RESULT_FILENAME_SCHEMA},
        filename_timezone='UTC',
    )
    raw = serialize_json_document(document).encode('utf-8')
    if len(raw) > MAX_HANDOFF_ENTRY_BYTES:
        raise _failure('environment exceeds handoff budget', FailureReason.SOURCE_ERROR)
    return PackMetadata(package_id, created_at, filename, raw, warnings)


@dataclass(frozen=True, slots=True)
class PackCandidate:
    entries: tuple[tuple[str, bytes, int], ...]
    warnings: tuple[str, ...]


class _BoundedOutput:
    def __init__(self, stream: BinaryIO, maximum: int) -> None:
        self.stream, self.maximum = stream, maximum

    def write(self, data: bytes) -> int:
        if self.stream.tell() + len(data) > self.maximum:
            raise _failure('compressed ZIP exceeds artifact budget', FailureReason.SOURCE_ERROR)
        count = self.stream.write(data)
        if count != len(data):
            raise OSError('short ZIP write')
        return count

    def tell(self) -> int:
        return self.stream.tell()

    def seek(self, *args) -> int:
        return self.stream.seek(*args)

    def flush(self) -> None:
        self.stream.flush()


def prepare_candidate(sources: CapturedSources,
                    reference: CapturedResultReference, metadata: PackMetadata,
                    template: str, *, resource_policy: ResourcePolicy = DEFAULT_RESOURCE_POLICY
                    ) -> PackCandidate:
    """Prepare bounded exact entries before reserving an output file."""
    manifest = {'marker': 'patch-harbor', 'format_version': 1,
                **_binding(reference), 'entrypoint': sources.entrypoint}
    document = parse_json_document(metadata.environment)
    try:
        handoff = render_chat_handoff(document, template=template)
    except PatchHarborError as exc:
        if isinstance(exc.__cause__, FileReadLimitExceeded):
            raise _failure('generated handoff exceeds budget', FailureReason.SOURCE_ERROR) from exc
        if exc.reason is not FailureReason.RESULT_BUNDLE_ERROR:
            raise
        raise _failure('cannot render own canonical template', FailureReason.PAYLOAD_PREPARATION_ERROR) from exc
    except (UnicodeError, ValueError) as exc:
        raise _failure('cannot render own canonical template', FailureReason.PAYLOAD_PREPARATION_ERROR) from exc
    entries = [(file.relative_path, file.content, file.unix_mode) for file in sources.files]
    entries.append(('patch.json', serialize_json_document(manifest).encode('utf-8'), 0o644))
    entries.extend((path, content, 0o644) for path, content in handoff.entries(patch=True))
    if (len(entries) > resource_policy.max_zip_entries
            or any(len(content) > resource_policy.max_content_bytes for _, content, _ in entries)
            or sum(len(content) for _, content, _ in entries) > resource_policy.max_zip_total_bytes):
        raise _failure('generated package exceeds ZIP content budget', FailureReason.SOURCE_ERROR)
    return PackCandidate(tuple(sorted(entries)),
                         tuple(dict.fromkeys((*sources.warnings, *metadata.warnings))))


def write_prepared_candidate(stream: BinaryIO, candidate: PackCandidate, *,
                             resource_policy: ResourcePolicy = DEFAULT_RESOURCE_POLICY) -> None:
    with ZipFile(_BoundedOutput(stream, resource_policy.max_input_artifact_bytes), 'w',
                 compression=ZIP_DEFLATED, compresslevel=6, allowZip64=False) as archive:
        for path, content, mode in candidate.entries:
            info = ZipInfo(path, (1980, 1, 1, 0, 0, 0))
            info.create_system = 3
            info.compress_type = ZIP_DEFLATED
            info.external_attr = (stat.S_IFREG | mode) << 16
            archive.writestr(info, content, compress_type=ZIP_DEFLATED, compresslevel=6)



def write_candidate(stream: BinaryIO, sources: CapturedSources,
                    reference: CapturedResultReference, metadata: PackMetadata,
                    template: str, *, resource_policy: ResourcePolicy = DEFAULT_RESOURCE_POLICY
                    ) -> tuple[str, ...]:
    candidate = prepare_candidate(sources, reference, metadata, template,
                                  resource_policy=resource_policy)
    write_prepared_candidate(stream, candidate, resource_policy=resource_policy)
    return candidate.warnings
