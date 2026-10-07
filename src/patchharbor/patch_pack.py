"""Synchronous pack orchestration with a single confirmed publication boundary."""
from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
from hashlib import sha256
import os
from pathlib import Path
from uuid import uuid4

from patchharbor.pyz_artifact import PyzProvider, own_pyz_profile_present
from patchharbor.bundle_handoff import CHAT_INSTRUCTIONS_NAME, MAX_HANDOFF_ENTRY_BYTES
from patchharbor.errors import FailureReason, PatchHarborError
from patchharbor.pack_candidate import prepare_metadata, prepare_candidate, write_prepared_candidate
from patchharbor.pack_sources import capture_sources, resolve_content_root, resolve_output_target
from patchharbor.pack_types import PatchPackResult
from patchharbor.patch_inspection import validate_patch_against_reference
from patchharbor.platform.file_handles import open_regular_nofollow
from patchharbor.platform.filesystem import (
    FileChangedDuringRead, FileReadLimitExceeded, UnsupportedFileTypeError,
    read_stable_regular_file_bounded, _same_open_file_state, _same_path_and_open_file_state,
)
from patchharbor.platform.pack_output import open_output_directory
from patchharbor.progress import activity
from patchharbor.result_reader import capture_result_reference
from patchharbor.resource_policy import DEFAULT_RESOURCE_POLICY
from patchharbor.runtime_artifact import RuntimeProvider



def _error(message: str, reason: FailureReason, exc: BaseException) -> PatchHarborError:
    return PatchHarborError(message + ': ' + str(exc), reason)


def capture_pack_template() -> str:
    """Pin the executing producer's verified template without foreign fallback."""
    try:
        selected_pyz = own_pyz_profile_present()
        provision=(PyzProvider() if selected_pyz else RuntimeProvider()).capture()
        if provision.artifact is not None:
            raw=provision.artifact.chat_template
        elif provision.reason=='source_not_prepared' and not selected_pyz:
            # An explicit source checkout has its own canonical source document.
            # Never consult CWD or metadata.distribution for another installation.
            module=Path(__file__).resolve()
            if module.parent.parent.name!='src':
                raise OSError('unprepared installed pack resources')
            raw=read_stable_regular_file_bounded(
                module.parents[2]/CHAT_INSTRUCTIONS_NAME,max_bytes=MAX_HANDOFF_ENTRY_BYTES,
            ).content
        elif provision.reason=='resource_limit':
            raise FileReadLimitExceeded('own runtime resource budget exceeded')
        else:
            raise OSError('own canonical resources unavailable: '+str(provision.reason))
        if len(raw)>MAX_HANDOFF_ENTRY_BYTES:
            raise FileReadLimitExceeded('own template exceeds handoff budget')
        if not raw or raw.startswith(b'\xef\xbb\xbf'):
            raise ValueError('empty or BOM-prefixed canonical template')
        return raw.decode('utf-8')
    except FileReadLimitExceeded as exc:
        raise _error('cannot capture pack template',FailureReason.SOURCE_ERROR,exc) from exc
    except (OSError,ValueError,FileChangedDuringRead,UnsupportedFileTypeError) as exc:
        raise _error('cannot capture own pack template',FailureReason.PAYLOAD_PREPARATION_ERROR,exc) from exc


def pack_patch(content_directory: Path, *, reference_bundle: Path, entrypoint: str,
               output: Path | None, output_directory: Path | None,
               modes: dict[str, int]) -> PatchPackResult:
    """Pack one request; cleanup happens while its output directory is pinned."""
    package_id, created_at = uuid4(), datetime.now(timezone.utc)
    reference_descriptor = None
    try:
        content_root = resolve_content_root(content_directory)
        try:
            reference_path = reference_bundle.resolve(strict=True)
            reference_descriptor = open_regular_nofollow(reference_path)
            reference_metadata = os.fstat(reference_descriptor)
            reference = capture_result_reference(reference_path, expected_identity=reference_metadata)
            if not _same_open_file_state(reference_metadata, os.fstat(reference_descriptor)):
                raise FileChangedDuringRead('reference changed during capture')
        except (OSError, ValueError, FileChangedDuringRead, UnsupportedFileTypeError) as exc:
            raise _error('cannot capture pack reference', FailureReason.SOURCE_ERROR, exc) from exc
        template = capture_pack_template()
        metadata = prepare_metadata(reference, package_id, created_at,
                                    filename=None if output is None else output.name)
        target = resolve_output_target(
            output if output is not None else output_directory / metadata.filename,
            contents_root=content_root,
        )
        activity('CAPTURE', 'Capture explicitly selected pack contents')
        sources = capture_sources(content_root, entrypoint, modes=modes, resolved_root=content_root)
        candidate = prepare_candidate(sources, reference, metadata, template)
        try:
            with open_output_directory(target.parent) as directory:
                owned = None
                result = None
                try:
                    try:
                        owned, stream = directory.reserve()
                        with stream:
                            write_prepared_candidate(stream, candidate)
                            stream.flush()
                    except OSError as exc:
                        raise _error('cannot write temporary pack ZIP', FailureReason.PAYLOAD_PREPARATION_ERROR, exc) from exc
                    try:
                        owned.pin()
                    except (OSError, FileChangedDuringRead, UnsupportedFileTypeError) as exc:
                        raise _error('pack output ownership changed', FailureReason.SOURCE_ERROR, exc) from exc
                    try:
                        owned.sync()
                    except OSError as exc:
                        raise _error('cannot synchronize pack ZIP', FailureReason.PAYLOAD_PREPARATION_ERROR, exc) from exc
                    activity('VERIFY', 'Validate actual pack ZIP bytes against captured reference')
                    validation = validate_patch_against_reference(
                        owned.path, reference, expected_identity=owned.identity,
                    )
                    expected_entries = {name: (len(data), sha256(data).hexdigest(), mode)
                                        for name, data, mode in candidate.entries}
                    actual_entries = {entry.path: (entry.size, entry.sha256, entry.unix_mode)
                                      for entry in validation.inspection.entries}
                    if actual_entries != expected_entries:
                        raise PatchHarborError('written pack contents differ from captured inputs',
                                               FailureReason.SOURCE_ERROR)
                    sources.revalidate()
                    try:
                        if (not _same_path_and_open_file_state(reference_path.lstat(), reference_metadata,
                                                              allow_path_identity_fallback=False)
                                or not _same_open_file_state(reference_metadata, os.fstat(reference_descriptor))):
                            raise FileChangedDuringRead('reference changed before pack finalization')
                        owned.verify_hash(validation.inspection.package_sha256,
                                          DEFAULT_RESOURCE_POLICY.max_input_artifact_bytes)
                        # No required reference I/O remains after publication.
                        descriptor, reference_descriptor = reference_descriptor, None
                        os.close(descriptor)
                    except (OSError, ValueError, FileChangedDuringRead, UnsupportedFileTypeError) as exc:
                        raise _error('pack final identity/hash verification failed', FailureReason.SOURCE_ERROR, exc) from exc
                    warnings = tuple(dict.fromkeys((*candidate.warnings, *validation.inspection.warnings)))
                    result = PatchPackResult(target, package_id, created_at, validation, warnings)
                    try:
                        owned.publish(target.name)
                    except FileChangedDuringRead as exc:
                        raise _error('pack output changed before publication', FailureReason.SOURCE_ERROR, exc) from exc
                    except OSError as exc:
                        raise _error('cannot publish pack ZIP without replacing a target',
                                     FailureReason.PAYLOAD_PREPARATION_ERROR, exc) from exc
                except BaseException as exc:
                    cleanup = () if owned is None else owned.cleanup()
                    if isinstance(exc, KeyboardInterrupt) and owned is not None and owned.published and result is not None:
                        result = replace(result, warnings=(*result.warnings, *cleanup,
                                         'optional cleanup interrupted after pack publication'))
                    else:
                        for warning in cleanup:
                            exc.add_note(warning)
                        raise
                else:
                    result = replace(result, warnings=(*result.warnings, *owned.cleanup()))
            return replace(result, warnings=(*result.warnings, *directory.cleanup_warnings))
        except OSError as exc:
            raise _error('cannot use explicit pack output directory', FailureReason.PAYLOAD_PREPARATION_ERROR, exc) from exc
    except BaseException as exc:
        if reference_descriptor is not None:
            try:
                os.close(reference_descriptor)
            except (OSError, KeyboardInterrupt) as cleanup:
                exc.add_note('cannot close pack reference handle: ' + str(cleanup))
        if isinstance(exc, KeyboardInterrupt):
            error = _error('pack interrupted without confirmed publication; inspect the chosen output before retrying',
                           FailureReason.INTERRUPTED, exc)
            for note in getattr(exc, '__notes__', ()):
                error.add_note(note)
            raise error from exc
        raise
