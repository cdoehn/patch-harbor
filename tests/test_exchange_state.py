from __future__ import annotations

import json
from pathlib import Path

import pytest

from patchharbor.errors import PatchHarborError
from patchharbor.exchange_state import (
    ExchangeApplyStatus,
    ExchangeFileIdentity,
    ExchangePatchSelection,
    ExchangeStateRecord,
    load_exchange_state,
    mark_exchange_apply_finished,
    mark_exchange_apply_started,
    merge_exchange_classifications,
)
from patchharbor.models import GitObjectFormat, GitObjectId, RepositoryId
from patchharbor.platform.filesystem import FileSystemOperationError
from patchharbor.state_fingerprint import FINGERPRINT_ALGORITHM
from patchharbor.user_paths import registration_user_paths
from tests.registration_support import set_isolated_user_environment


def _identity(path: Path, character: str = "a") -> ExchangeFileIdentity:
    return ExchangeFileIdentity(path=path.resolve(), sha256=character * 64)


def _selection() -> ExchangePatchSelection:
    return ExchangePatchSelection(
        repo_id=RepositoryId("a3f9c2e1-7b4d-4a91-9d2e-5c6f8a1b2c3d"),
        base_commit=GitObjectId("b" * 40, GitObjectFormat.SHA1),
        state_fingerprint="c" * 16,
        fingerprint_algorithm=FINGERPRINT_ALGORITHM,
    )


def _record(path: Path, character: str = "a") -> ExchangeStateRecord:
    return ExchangeStateRecord(
        identity=_identity(path, character),
        kind="patch_package",
        manifest=_selection(),
    )


def test_classification_and_apply_lifecycle_are_persisted_in_closed_v2_state(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    set_isolated_user_environment(monkeypatch, tmp_path / "user")
    paths = registration_user_paths()
    patch = tmp_path / "exchange" / "patch.zip"
    patch.parent.mkdir()
    patch.write_bytes(b"package")
    record = _record(patch)

    merged = merge_exchange_classifications(paths, (record,))

    assert merged.record_for(record.identity) == record
    document = json.loads(paths.exchange_state_path.read_text(encoding="utf-8"))
    assert document == {
        "entries": [
            {
                "apply_status": None,
                "kind": "patch_package",
                "manifest": {
                    "base_commit": "b" * 40,
                    "fingerprint_algorithm": FINGERPRINT_ALGORITHM,
                    "repo_id": "a3f9c2e1-7b4d-4a91-9d2e-5c6f8a1b2c3d",
                    "state_fingerprint": "c" * 16,
                },
                "path": str(patch.resolve()),
                "sha256": "a" * 64,
            }
        ],
        "format_version": 2,
    }

    verified: list[bool] = []
    mark_exchange_apply_started(
        paths,
        record.identity,
        _selection(),
        verify_identity=lambda: verified.append(True),
    )

    assert verified == [True]
    attempted = load_exchange_state(paths).record_for(record.identity)
    assert attempted is not None
    assert attempted.apply_status is ExchangeApplyStatus.ATTEMPTED
    mark_exchange_apply_finished(
        paths,
        record.identity,
        _selection(),
        ExchangeApplyStatus.FAILED,
    )
    failed = load_exchange_state(paths).record_for(record.identity)
    assert failed is not None
    assert failed.apply_status is ExchangeApplyStatus.FAILED
    with pytest.raises(
        PatchHarborError,
        match="selected exchange patch was already attempted",
    ):
        mark_exchange_apply_started(
            paths,
            record.identity,
            _selection(),
            verify_identity=lambda: None,
        )


def test_successful_apply_is_persisted_as_a_distinct_terminal_state(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    set_isolated_user_environment(monkeypatch, tmp_path / "user")
    paths = registration_user_paths()
    patch = tmp_path / "exchange" / "patch.zip"
    patch.parent.mkdir()
    patch.write_bytes(b"package")
    record = _record(patch)
    merge_exchange_classifications(paths, (record,))

    mark_exchange_apply_started(
        paths,
        record.identity,
        _selection(),
        verify_identity=lambda: None,
    )
    mark_exchange_apply_finished(
        paths,
        record.identity,
        _selection(),
        ExchangeApplyStatus.SUCCEEDED,
    )

    persisted = load_exchange_state(paths).record_for(record.identity)
    assert persisted is not None
    assert persisted.apply_status is ExchangeApplyStatus.SUCCEEDED
    document = json.loads(paths.exchange_state_path.read_text(encoding="utf-8"))
    assert document["entries"][0]["apply_status"] == "succeeded"


def test_legacy_attempt_flags_load_conservatively_and_migrate_on_next_write(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    set_isolated_user_environment(monkeypatch, tmp_path / "user")
    paths = registration_user_paths()
    paths.exchange_state_directory.mkdir()
    patch = (tmp_path / "exchange" / "legacy.zip").resolve()
    legacy_entries = []
    for character, attempted in (("a", False), ("d", True)):
        legacy_entries.append(
            {
                "attempted": attempted,
                "kind": "patch_package",
                "manifest": {
                    "base_commit": "b" * 40,
                    "fingerprint_algorithm": FINGERPRINT_ALGORITHM,
                    "repo_id": "a3f9c2e1-7b4d-4a91-9d2e-5c6f8a1b2c3d",
                    "state_fingerprint": "c" * 16,
                },
                "path": str(patch),
                "sha256": character * 64,
            }
        )
    paths.exchange_state_path.write_text(
        json.dumps(
            {"entries": legacy_entries, "format_version": 1},
            separators=(",", ":"),
        )
        + "\n",
        encoding="utf-8",
    )

    loaded = load_exchange_state(paths)

    assert loaded.record_for(_identity(patch, "a")).apply_status is None  # type: ignore[union-attr]
    assert (  # type: ignore[union-attr]
        loaded.record_for(_identity(patch, "d")).apply_status
        is ExchangeApplyStatus.ATTEMPTED
    )

    merge_exchange_classifications(paths, (_record(patch, "e"),))
    migrated = json.loads(paths.exchange_state_path.read_text(encoding="utf-8"))
    assert migrated["format_version"] == 2
    statuses = {
        entry["sha256"]: entry["apply_status"]
        for entry in migrated["entries"]
    }
    assert statuses == {
        "a" * 64: None,
        "d" * 64: "attempted",
        "e" * 64: None,
    }


def test_changed_bytes_at_the_same_path_form_an_independent_identity(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    set_isolated_user_environment(monkeypatch, tmp_path / "user")
    paths = registration_user_paths()
    patch = tmp_path / "exchange" / "patch.zip"
    patch.parent.mkdir()
    patch.write_bytes(b"first")
    first = _record(patch, "a")
    second = _record(patch, "d")

    merge_exchange_classifications(paths, (first, second))
    mark_exchange_apply_started(
        paths,
        first.identity,
        _selection(),
        verify_identity=lambda: None,
    )

    state = load_exchange_state(paths)
    assert (  # type: ignore[union-attr]
        state.record_for(first.identity).apply_status
        is ExchangeApplyStatus.ATTEMPTED
    )
    assert state.record_for(second.identity).apply_status is None  # type: ignore[union-attr]


def test_identity_verification_failure_does_not_consume_the_record(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    set_isolated_user_environment(monkeypatch, tmp_path / "user")
    paths = registration_user_paths()
    patch = tmp_path / "exchange" / "patch.zip"
    patch.parent.mkdir()
    patch.write_bytes(b"package")
    record = _record(patch)
    merge_exchange_classifications(paths, (record,))

    def fail_verification() -> None:
        raise PatchHarborError("changed", 10)

    with pytest.raises(PatchHarborError, match="changed"):
        mark_exchange_apply_started(
            paths,
            record.identity,
            _selection(),
            verify_identity=fail_verification,
        )

    observed = load_exchange_state(paths).record_for(record.identity)
    assert observed is not None and observed.attempted is False


def test_failed_atomic_attempt_publication_preserves_the_previous_state(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from patchharbor import exchange_state as state_module

    set_isolated_user_environment(monkeypatch, tmp_path / "user")
    paths = registration_user_paths()
    patch = tmp_path / "exchange" / "patch.zip"
    patch.parent.mkdir()
    patch.write_bytes(b"package")
    record = _record(patch)
    merge_exchange_classifications(paths, (record,))
    original = paths.exchange_state_path.read_bytes()

    def fail_replace(_target: Path, _content: bytes) -> None:
        raise FileSystemOperationError(
            "cannot replace target",
            OSError("simulated failure"),
        )

    monkeypatch.setattr(state_module, "atomic_replace_bytes", fail_replace)
    with pytest.raises(
        PatchHarborError,
        match="cannot write exchange processing state",
    ):
        mark_exchange_apply_started(
            paths,
            record.identity,
            _selection(),
            verify_identity=lambda: None,
        )

    assert paths.exchange_state_path.read_bytes() == original


@pytest.mark.parametrize(
    "content",
    (
        b"{}\n",
        b'{"entries":[],"entries":[],"format_version":1}\n',
        b'{"entries":[],"format_version":3}\n',
        b'{"entries":[{}],"format_version":1}\n',
        b'{"entries":[{}],"format_version":2}\n',
    ),
)
def test_invalid_or_ambiguous_state_is_rejected(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    content: bytes,
) -> None:
    set_isolated_user_environment(monkeypatch, tmp_path / "user")
    paths = registration_user_paths()
    paths.exchange_state_directory.mkdir()
    paths.exchange_state_path.write_bytes(content)

    with pytest.raises(PatchHarborError, match="exchange processing state"):
        load_exchange_state(paths)


def test_exchange_state_uses_the_platform_state_directory_and_lock_directory(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    set_isolated_user_environment(monkeypatch, tmp_path / "user")
    paths = registration_user_paths()

    assert paths.exchange_state_directory == paths.state_directory / "exchange"
    assert paths.exchange_state_path == paths.exchange_state_directory / "state.json"
    assert paths.exchange_state_lock_path == paths.lock_directory / "exchange.lock"
