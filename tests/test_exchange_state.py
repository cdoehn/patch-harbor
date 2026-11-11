from __future__ import annotations

import json
from pathlib import Path

import pytest

from patchharbor.errors import FailureReason
from patchharbor.errors import PatchHarborError
from patchharbor.exchange_state import ExchangeExecuteStatus, load_exchange_state, mark_exchange_execute_finished, mark_exchange_execute_started, merge_exchange_classifications
from patchharbor.models import GitObjectFormat, GitObjectId
from patchharbor.platform.filesystem import FileSystemOperationError
from patchharbor.state_fingerprint import FINGERPRINT_ALGORITHM
from patchharbor.user_paths import registration_user_paths
from tests.registration_support import set_isolated_user_environment
from tests.exchange_support import _identity, _selection, _record


def test_classification_and_execute_lifecycle_are_persisted_in_closed_v5_state(
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
                "execute_status": None,
                "completed_commit": None,
                "attempt_run_id": None,
                "result_sha256": None,
                "kind": "task_bundle",
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
        "format_version": 5,
    }

    verified: list[bool] = []
    mark_exchange_execute_started(
        paths,
        record.identity,
        _selection(),
        verify_identity=lambda: verified.append(True),
    )

    assert verified == [True]
    attempted = load_exchange_state(paths).record_for(record.identity)
    assert attempted is not None
    assert attempted.execute_status is ExchangeExecuteStatus.ATTEMPTED
    mark_exchange_execute_finished(
        paths,
        record.identity,
        _selection(),
        ExchangeExecuteStatus.FAILED,
    )
    failed = load_exchange_state(paths).record_for(record.identity)
    assert failed is not None
    assert failed.execute_status is ExchangeExecuteStatus.FAILED
    with pytest.raises(
        PatchHarborError,
        match="selected exchange patch was already attempted",
    ):
        mark_exchange_execute_started(
            paths,
            record.identity,
            _selection(),
            verify_identity=lambda: None,
        )


def test_failed_apply_can_be_reopened_only_by_an_explicit_retry_transition(
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
    mark_exchange_execute_started(
        paths,
        record.identity,
        _selection(),
        verify_identity=lambda: None,
    )
    mark_exchange_execute_finished(
        paths,
        record.identity,
        _selection(),
        ExchangeExecuteStatus.FAILED,
    )

    with pytest.raises(
        PatchHarborError,
        match="selected exchange patch was already attempted",
    ):
        mark_exchange_execute_started(
            paths,
            record.identity,
            _selection(),
            verify_identity=lambda: None,
        )

    verified: list[bool] = []
    mark_exchange_execute_started(
        paths,
        record.identity,
        _selection(),
        verify_identity=lambda: verified.append(True),
        retry_failed=True,
    )

    assert verified == [True]
    reopened = load_exchange_state(paths).record_for(record.identity)
    assert reopened is not None
    assert reopened.execute_status is ExchangeExecuteStatus.ATTEMPTED


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

    mark_exchange_execute_started(
        paths,
        record.identity,
        _selection(),
        verify_identity=lambda: None,
    )
    mark_exchange_execute_finished(
        paths,
        record.identity,
        _selection(),
        ExchangeExecuteStatus.SUCCEEDED,
    )

    persisted = load_exchange_state(paths).record_for(record.identity)
    assert persisted is not None
    assert persisted.execute_status is ExchangeExecuteStatus.SUCCEEDED
    document = json.loads(paths.exchange_state_path.read_text(encoding="utf-8"))
    assert document["entries"][0]["execute_status"] == "succeeded"


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

    assert loaded.record_for(_identity(patch, "a")).execute_status is None  # type: ignore[union-attr]
    assert (  # type: ignore[union-attr]
        loaded.record_for(_identity(patch, "d")).execute_status
        is ExchangeExecuteStatus.ATTEMPTED
    )

    merge_exchange_classifications(paths, (_record(patch, "e"),))
    migrated = json.loads(paths.exchange_state_path.read_text(encoding="utf-8"))
    assert migrated["format_version"] == 5
    statuses = {
        entry["sha256"]: entry["execute_status"]
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
    mark_exchange_execute_started(
        paths,
        first.identity,
        _selection(),
        verify_identity=lambda: None,
    )

    state = load_exchange_state(paths)
    assert (  # type: ignore[union-attr]
        state.record_for(first.identity).execute_status
        is ExchangeExecuteStatus.ATTEMPTED
    )
    assert state.record_for(second.identity).execute_status is None  # type: ignore[union-attr]


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
        raise PatchHarborError("changed", FailureReason.TASK_BUNDLE_ERROR)

    with pytest.raises(PatchHarborError, match="changed"):
        mark_exchange_execute_started(
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
        mark_exchange_execute_started(
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
        b'{"entries":[],"format_version":99}\n',
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


def test_completion_receipt_is_full_persistent_and_cleared_on_explicit_retry(tmp_path, monkeypatch):
    set_isolated_user_environment(monkeypatch, tmp_path / "user")
    paths = registration_user_paths()
    package = tmp_path / "patch.zip"
    package.write_bytes(b"package")
    record = _record(package)
    merge_exchange_classifications(paths, (record,))
    mark_exchange_execute_started(paths, record.identity, _selection(), verify_identity=lambda: None)
    commit = GitObjectId("d" * 40, GitObjectFormat.SHA1)
    mark_exchange_execute_finished(paths, record.identity, _selection(), ExchangeExecuteStatus.SUCCEEDED,
                                 completed_commit=commit)
    assert load_exchange_state(paths).record_for(record.identity).completed_commit == commit
    mark_exchange_execute_started(paths, record.identity, _selection(), verify_identity=lambda: None,
                                explicitly_selected=True)
    reread = load_exchange_state(paths).record_for(record.identity)
    assert reread.execute_status is ExchangeExecuteStatus.ATTEMPTED
    assert reread.completed_commit is None


@pytest.mark.parametrize("status,commit", [
    (None, "d" * 40), ("attempted", "d" * 40), ("failed", "d" * 40),
    ("succeeded", "b" * 40), ("succeeded", "d" * 64),
    ("succeeded", "abcdef"), ("succeeded", True), ("succeeded", 123),
])
def test_inconsistent_completion_receipts_are_rejected(tmp_path, monkeypatch, status, commit):
    set_isolated_user_environment(monkeypatch, tmp_path / "user")
    paths = registration_user_paths()
    package = tmp_path / "patch.zip"
    package.write_bytes(b"package")
    merge_exchange_classifications(paths, (_record(package),))
    document = json.loads(paths.exchange_state_path.read_bytes())
    document["entries"][0].update(execute_status=status, completed_commit=commit)
    paths.exchange_state_path.write_text(json.dumps(document))
    with pytest.raises(PatchHarborError):
        load_exchange_state(paths)


@pytest.mark.parametrize("old_kind", ["patch_package", "task_package"])
@pytest.mark.parametrize("status", [None, "attempted", "failed", "succeeded"])
def test_v4_ledger_preserves_identity_status_and_receipts_on_v5_write(
    tmp_path, monkeypatch, old_kind, status,
):
    set_isolated_user_environment(monkeypatch, tmp_path / "user")
    paths = registration_user_paths()
    paths.exchange_state_directory.mkdir()
    path = (tmp_path / "task.zip").resolve()
    run_id = "84c316e6-2710-4b9c-9232-229bc02aa8c4" if status else None
    completed = "e" * 40 if status == "succeeded" else None
    result_sha = "f" * 64 if status == "succeeded" else None
    old = dict(path=str(path), sha256="a" * 64, kind=old_kind,
        manifest=dict(repo_id="a3f9c2e1-7b4d-4a91-9d2e-5c6f8a1b2c3d",
            base_commit="b" * 40, state_fingerprint="c" * 16,
            fingerprint_algorithm=FINGERPRINT_ALGORITHM),
        apply_status=status, completed_commit=completed,
        attempt_run_id=run_id, result_sha256=result_sha)
    before = json.dumps(dict(format_version=4, entries=[old])).encode()
    paths.exchange_state_path.write_bytes(before)

    record = load_exchange_state(paths).record_for(_identity(path, "a"))
    assert record.kind == "task_bundle"
    assert record.manifest == _selection()
    assert (record.execute_status.value if record.execute_status else None) == status
    assert record.attempt_run_id == run_id and record.result_sha256 == result_sha
    assert (str(record.completed_commit) if record.completed_commit else None) == completed
    assert paths.exchange_state_path.read_bytes() == before

    merge_exchange_classifications(paths, (_record(tmp_path / "other.zip", "d"),))
    document = json.loads(paths.exchange_state_path.read_bytes())
    assert document["format_version"] == 5
    migrated = next(row for row in document["entries"] if row["sha256"] == "a" * 64)
    expected = {key: value for key, value in old.items() if key not in {"kind", "apply_status"}}
    assert migrated == dict(expected, kind="task_bundle", execute_status=status)
    assert load_exchange_state(paths).record_for(record.identity) == record


@pytest.mark.parametrize("mutation", ["old-status", "mixed-status", "old-kind", "future"])
def test_v5_ledger_rejects_mixed_or_unknown_generations(tmp_path, monkeypatch, mutation):
    set_isolated_user_environment(monkeypatch, tmp_path / "user")
    paths = registration_user_paths()
    merge_exchange_classifications(paths, (_record(tmp_path / "task.zip"),))
    document = json.loads(paths.exchange_state_path.read_bytes())
    row = document["entries"][0]
    if mutation == "old-status":
        row["apply_status"] = row.pop("execute_status")
    elif mutation == "mixed-status":
        row["apply_status"] = row["execute_status"]
    elif mutation == "old-kind":
        row["kind"] = "patch_package"
    else:
        document["format_version"] = 6
    before = json.dumps(document).encode()
    paths.exchange_state_path.write_bytes(before)
    with pytest.raises(PatchHarborError):
        load_exchange_state(paths)
    assert paths.exchange_state_path.read_bytes() == before
