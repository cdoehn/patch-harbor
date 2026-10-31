"""Export the loaded producer through the existing pinned no-replace boundary."""
from dataclasses import replace
from pathlib import Path

from patchharbor.compat import add_exception_note
from patchharbor.platform.filesystem import (
    FileChangedDuringRead, FileReadLimitExceeded, UnsupportedFileTypeError,
)
from patchharbor.platform.pack_output import open_output_directory
from patchharbor.pyz_artifact import PyzProvider
from patchharbor.runtime_pyz import MAX_PYZ_BYTES, PROFILE
from patchharbor.runtime_export_types import (
    RuntimeExportError, RuntimeExportErrorCode as Code, RuntimeExportResult,
)


def export_runtime(output_directory: Path) -> RuntimeExportResult:
    """Capture once before any write; publish only the synced, verified bytes."""
    owned = None
    target = None
    try:
        provision = PyzProvider().capture()
        if provision.artifact is None:
            raise RuntimeExportError(Code.UNAVAILABLE, 'own runtime unavailable: '+str(provision.reason),
                                     unavailable_reason=provision.reason)
        artifact = provision.artifact
        recipe = artifact.recipe
        try:
            root = output_directory.absolute()
            # The native directory opener rejects every linked/reparse parent.
            # Resolve is only a comparison, never a way to admit a redirected path.
            if root.resolve(strict=True) != root:
                raise OSError('output directory must not contain links or parent traversal')
            scope = open_output_directory(root)
            target = root / recipe.pyz_name
        except (OSError, ValueError, RuntimeError) as exc:
            raise RuntimeExportError(Code.UNSAFE_PATH, 'invalid runtime output directory: '+str(exc)) from exc
        with scope as directory:
            try:
                try:
                    directory.child_stat(target.name)
                except FileNotFoundError:
                    pass
                else:
                    raise RuntimeExportError(Code.COLLISION, 'runtime output already exists')
                owned, stream = directory.reserve()
                with stream:
                    if stream.write(artifact.pyz_bytes) != len(artifact.pyz_bytes):
                        raise OSError('short runtime write')
                    stream.flush()
                owned.pin()
                owned.sync()
                owned.verify_hash(artifact.pyz_sha256, MAX_PYZ_BYTES)
                result = RuntimeExportResult(target, recipe.version, len(artifact.pyz_bytes),
                    artifact.pyz_sha256, PROFILE, recipe.requires_python,
                    recipe.content_id, recipe.source_commit)
                owned.publish(target.name)
            finally:
                cleanup = () if owned is None else owned.cleanup()
                # On failure preserve diagnostics without changing the primary error.
                import sys
                pending = sys.exc_info()[1]
                if pending is not None:
                    for warning in cleanup:
                        add_exception_note(pending, warning)
        return replace(result, warnings=(*cleanup, *directory.cleanup_warnings))
    except RuntimeExportError:
        raise
    except (KeyboardInterrupt, SystemExit) as exc:
        raise RuntimeExportError(Code.INTERRUPTED,
            'runtime export interrupted; inspect the explicit destination before retrying',
            published_path=target if owned is not None and owned.published else None) from exc
    except FileExistsError as exc:
        raise RuntimeExportError(Code.COLLISION, 'runtime output already exists') from exc
    except (OSError, ValueError, FileChangedDuringRead, FileReadLimitExceeded, UnsupportedFileTypeError) as exc:
        raise RuntimeExportError(Code.IO, 'cannot publish runtime: '+str(exc),
            published_path=target if owned is not None and owned.published else None) from exc
