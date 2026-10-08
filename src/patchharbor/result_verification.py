"""Bounded stabilization of one owned Result, without repeating an Apply."""
from collections.abc import Callable
from pathlib import Path
from time import sleep
from typing import TypeVar

from patchharbor.errors import ErrorKind, FailureReason, PatchHarborError
from patchharbor.platform.cifs import publication_wait_budget
from patchharbor.platform.filesystem import FileChangedDuringRead, MetadataSyncStatus
from patchharbor.progress import activity
from patchharbor.resource_policy import ResultSnapshotLimitError
from patchharbor.zip_payloads import ZipResourceLimitError


RETRY_DELAYS = (2, 3, 5, 10, 20, 20, 30, 30, 60, 60, 60)
_T = TypeVar("_T")


class ResultVerificationError(PatchHarborError):
    """Safe diagnostics also survive the existing run.json error string."""

    def __init__(self, diagnostics: dict[str, object]) -> None:
        self.diagnostics = diagnostics
        fields = ("verification_stage", "verification_error_type", "verification_attempts",
                  "stable_read_mismatch")
        detail = ", ".join(f"{field}={diagnostics[field]}" for field in fields)
        if diagnostics.get("verification_error_detail"):
            detail += ", verification_error_detail=" + str(diagnostics["verification_error_detail"])
        super().__init__(f"Result Bundle integrity verification failed ({detail})",
                         FailureReason.RESULT_BUNDLE_ERROR, error_kind=ErrorKind.RESULT_BUNDLE_ERROR)


def _read_failure(error: BaseException) -> FileChangedDuringRead | None:
    # Follow explicit wrapping only. An unrelated exception raised while handling
    # a read failure must not become retryable through its implicit __context__.
    seen: set[int] = set()
    while id(error) not in seen:
        seen.add(id(error))
        if isinstance(error, FileChangedDuringRead):
            return error
        if not isinstance(error, PatchHarborError) or error.__cause__ is None:
            break
        error = error.__cause__
    return None


def _limit_failure(error: BaseException) -> ZipResourceLimitError | ResultSnapshotLimitError | None:
    """Preserve a typed budget failure through explicit publication wrappers."""
    seen: set[int] = set()
    while id(error) not in seen:
        seen.add(id(error))
        if isinstance(error, (ZipResourceLimitError, ResultSnapshotLimitError)):
            return error
        if not isinstance(error, PatchHarborError) or error.__cause__ is None:
            break
        error = error.__cause__
    return None


class ResultVerification:
    """Share one finite sleep budget across verification and receipt hash reads."""

    def __init__(self, path: Path, *, require_owned: Callable[[], None],
                 synchronize: Callable[[], tuple[MetadataSyncStatus, MetadataSyncStatus]]) -> None:
        budget = publication_wait_budget(path)
        delays = RETRY_DELAYS + ((budget - 300,) if budget > 300 else ())
        self._delays = iter(delays)
        self.budget_seconds = sum(delays)
        self.waited_seconds = 0
        self.sync_outcomes: list[dict[str, object]] = []
        self.require_owned = require_owned
        self.synchronize = synchronize
        self.file_sync = MetadataSyncStatus.UNSUPPORTED
        self.directory_sync = MetadataSyncStatus.UNSUPPORTED

    def run(self, stage: str, operation: Callable[[], _T]) -> _T:
        attempts = 0
        while True:
            attempts += 1
            # Ownership, opens and sync failures are outside the retry boundary.
            self.require_owned()
            self.file_sync, self.directory_sync = self.synchronize()
            self.sync_outcomes.append({"stage": stage, "attempt": attempts,
                                       "file": self.file_sync.name.lower(),
                                       "directory": self.directory_sync.name.lower()})
            self.require_owned()
            try:
                value = operation()
            except (PatchHarborError, FileChangedDuringRead) as exc:
                changed = _read_failure(exc)
                delay = next(self._delays, None) if changed is not None else None
                if changed is None or delay is None:
                    limit = _limit_failure(exc)
                    raise ResultVerificationError({
                        "verification_stage": stage,
                        "verification_error_type": "FileChangedDuringRead" if changed else type(limit).__name__ if limit else "PatchHarborError",
                        "verification_error_detail": str(limit) if limit else str(exc),
                        "resource_limit": ({"resource": limit.resource, "actual": limit.actual,
                                            "limit": limit.limit} if limit else None),
                        "verification_attempts": attempts,
                        "stable_read_mismatch": changed.category if changed else None,
                        "metadata": changed.metadata if changed else {},
                        "waited_seconds": self.waited_seconds,
                        "retry_budget_seconds": self.budget_seconds,
                        "sync_outcomes": self.sync_outcomes,
                    }) from exc
                self.require_owned()
                activity("VERIFY", f"Temporary Result metadata is not stable; retry in {delay} seconds", "warning")
                sleep(delay)
                self.waited_seconds += delay
                continue
            self.require_owned()
            return value
