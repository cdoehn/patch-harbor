"""Prepare one validated patch package outside its target repository."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path

from patchharbor.errors import ExitCode, PatchHarborError
from patchharbor.interpreters import ResolvedInterpreter, resolve_script_interpreter
from patchharbor.parser import ParsedScript, ScriptFormatError, parse_script
from patchharbor.patch_package import ValidatedPatchPackage
from patchharbor.physical_paths import is_physically_within
from patchharbor.platform.errors import describe_os_error
from patchharbor.temporary_resources import (
    private_request_directory,
    system_temporary_directory,
    write_private_bytes,
)


@dataclass(frozen=True, slots=True)
class PreparedEntrypoint:
    """One parsed entrypoint with a resolved interpreter and private path."""

    path: Path
    script: ParsedScript
    interpreter: ResolvedInterpreter
    size_bytes: int
    sha256_hex: str


@dataclass(frozen=True, slots=True)
class PreparedPayload:
    """One byte-verified payload staged outside the target repository."""

    relative_path: str
    path: Path
    size_bytes: int
    sha256_hex: str


@dataclass(frozen=True, slots=True)
class PreparedPatchPackage:
    """Immutable checked inputs ready for a later mutation boundary."""

    entrypoint: PreparedEntrypoint
    payloads: tuple[PreparedPayload, ...]

    @property
    def warnings(self) -> tuple[str, ...]:
        return self.entrypoint.script.warnings


def _preflight_error(message: str, exit_code: ExitCode) -> PatchHarborError:
    return PatchHarborError(message, exit_code)


def _private_resource_path(root: Path, relative_path: str) -> Path:
    return root.joinpath(*relative_path.split("/"))


def _verified_private_resource(
    root: Path,
    relative_path: str,
    content: bytes,
    *,
    failure_exit: ExitCode,
) -> tuple[Path, bytes]:
    target = _private_resource_path(root, relative_path)
    expected_hash = sha256(content).digest()
    try:
        write_private_bytes(target, content)
        observed = target.read_bytes()
    except OSError as exc:
        raise _preflight_error(
            f"cannot prepare private package resource: {describe_os_error(exc)}",
            failure_exit,
        ) from exc
    if len(observed) != len(content) or sha256(observed).digest() != expected_hash:
        raise _preflight_error(
            "private package resource does not match the validated ZIP entry",
            failure_exit,
        )
    return target, observed


def _prepare_entrypoint(
    package: ValidatedPatchPackage,
    private_root: Path,
) -> PreparedEntrypoint:
    path, observed = _verified_private_resource(
        private_root / "entrypoint",
        package.entrypoint.relative_path,
        package.entrypoint.content,
        failure_exit=ExitCode.EXECUTION_ERROR,
    )
    try:
        script = parse_script(observed.decode("utf-8"))
    except (UnicodeError, ScriptFormatError) as exc:
        raise _preflight_error(
            "patch package entrypoint is not a valid PatchHarbor script",
            ExitCode.NO_VALID_SCRIPT,
        ) from exc

    interpreter = resolve_script_interpreter(script.text)
    return PreparedEntrypoint(
        path=path,
        script=script,
        interpreter=interpreter,
        size_bytes=len(observed),
        sha256_hex=sha256(observed).hexdigest(),
    )


def _prepare_payloads(
    package: ValidatedPatchPackage,
    private_root: Path,
) -> tuple[PreparedPayload, ...]:
    prepared: list[PreparedPayload] = []
    payload_root = private_root / "payloads"
    for payload in package.payloads:
        path, observed = _verified_private_resource(
            payload_root,
            payload.relative_path,
            payload.content,
            failure_exit=ExitCode.PAYLOAD_PREPARATION_ERROR,
        )
        prepared.append(
            PreparedPayload(
                relative_path=payload.relative_path,
                path=path,
                size_bytes=len(observed),
                sha256_hex=sha256(observed).hexdigest(),
            )
        )
    return tuple(prepared)


@contextmanager
def prepare_patch_package(
    package: ValidatedPatchPackage,
    *,
    repository: Path,
) -> Iterator[PreparedPatchPackage]:
    """Yield checked private resources and own their complete cleanup."""
    try:
        temporary_root = system_temporary_directory()
    except (OSError, RuntimeError) as exc:
        raise _preflight_error(
            f"cannot resolve the private system temporary directory: {exc}",
            ExitCode.EXECUTION_ERROR,
        ) from exc

    if is_physically_within(
        temporary_root,
        repository,
        candidate_must_exist=True,
        root_must_exist=True,
    ):
        raise _preflight_error(
            "private apply temporary directory is inside the repository",
            ExitCode.EXECUTION_ERROR,
        )

    try:
        with private_request_directory(prefix="patchharbor-apply-") as private_root:
            entrypoint = _prepare_entrypoint(package, private_root)
            payloads = _prepare_payloads(package, private_root)
            yield PreparedPatchPackage(
                entrypoint=entrypoint,
                payloads=payloads,
            )
    except PatchHarborError:
        raise
    except OSError as exc:
        raise _preflight_error(
            f"cannot prepare private patch resources: {describe_os_error(exc)}",
            ExitCode.EXECUTION_ERROR,
        ) from exc
