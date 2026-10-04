"""Permission enforcement and restoration, including partial fixture failures."""
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
from threading import Barrier

import pytest

from tests import runtime_permissions as permissions

pytestmark = pytest.mark.packaging


def _tree(owner, name="installed [fixture] Gr\u00fc\u00dfe ' quote"):
    root = owner / name
    (root / "nested").mkdir(parents=True)
    (root / "module.py").write_bytes(b"test code\n")
    (root / "nested/data").write_bytes(b"test resource\n")
    return root


def _snapshot(root):
    return {path.relative_to(root).as_posix():
            (path.stat().st_mode, path.read_bytes() if path.is_file() else None)
            for path in [root, *root.rglob("*")]}


@pytest.mark.parametrize("body_failure", [False, True])
def test_native_permissions_deny_writes_and_restore(tmp_path, body_failure):
    if os.name != "nt" and os.geteuid() == 0:
        pytest.skip("POSIX root bypasses permission bits; no native denial proof")
    root = _tree(tmp_path)
    before = _snapshot(root)
    entered = False
    try:
        with permissions.readonly_tree(root, owner=tmp_path, environment=os.environ.copy()) as proof:
            entered = True
            assert proof["enforced"] is True
            assert proof["method"] == ("windows_dacl" if os.name == "nt" else "posix_mode")
            assert (root / "nested/data").read_bytes() == b"test resource\n"
            with pytest.raises(PermissionError):
                (root / "nested/data").write_bytes(b"changed")
            with pytest.raises(PermissionError):
                (root / "new-file").write_bytes(b"created")
            if body_failure:
                raise LookupError("consumer failed")
    except LookupError:
        assert body_failure
    else:
        assert not body_failure
    assert entered and _snapshot(root) == before
    (root / "nested/data").write_bytes(b"writable again")
    assert not list(tmp_path.glob("runtime-acl-*"))


def test_concurrent_permission_fixtures_do_not_share_restoration_state(tmp_path):
    roots = [_tree(tmp_path, f"installation-{i}") for i in range(4)]
    snapshots = [_snapshot(root) for root in roots]
    barrier = Barrier(4)
    def capture(root):
        with permissions.readonly_tree(root, owner=tmp_path, environment=os.environ.copy()):
            barrier.wait(timeout=120)
            return (root / "module.py").read_bytes()
    with ThreadPoolExecutor(max_workers=4) as pool:
        assert list(pool.map(capture, roots)) == [b"test code\n"] * 4
    assert [_snapshot(root) for root in roots] == snapshots
    assert not list(tmp_path.glob("runtime-acl-*"))


@pytest.mark.parametrize("kind", ["outside", "owner_itself", "root_link", "child_link"])
def test_permission_fixture_rejects_unowned_or_linked_paths(tmp_path, kind):
    owned = tmp_path / "owned"
    owned.mkdir()
    external = _tree(tmp_path, "external")
    before = _snapshot(external)
    root = external if kind == "outside" else owned if kind == "owner_itself" else _tree(owned)
    if kind.endswith("link"):
        link = owned / "link" if kind == "root_link" else root / "linked"
        try:
            link.symlink_to(external, target_is_directory=True)
        except OSError:
            pytest.skip("symlink creation is unavailable")
        if kind == "root_link":
            root = link
    with pytest.raises(ValueError):
        with permissions.readonly_tree(root, owner=owned, environment=os.environ.copy()):
            pytest.fail("unowned permission fixture was entered")
    assert _snapshot(external) == before


@pytest.mark.skipif(os.name == "nt", reason="POSIX mode restoration")
def test_partial_posix_setup_restores_every_original_mode(tmp_path, monkeypatch):
    root = _tree(tmp_path)
    paths = permissions._owned_paths(root, tmp_path)
    before = _snapshot(root)
    original = Path.chmod
    calls = 0
    def partial(path, mode, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 3:
            raise PermissionError("partial setup failure")
        return original(path, mode, **kwargs)
    monkeypatch.setattr(Path, "chmod", partial)
    with pytest.raises(PermissionError):
        with permissions._posix_readonly(paths):
            pytest.fail("failed setup reached consumer")
    assert _snapshot(root) == before


@pytest.mark.parametrize("failure", ["setup", "body", "missing_journal"])
def test_windows_journal_lifecycle_restores_after_failures(tmp_path, monkeypatch, failure):
    # Controlled subprocess boundary on every platform; this is not a Windows
    # permission proof. The native integration cases exercise the actual script.
    root = _tree(tmp_path)
    before = _snapshot(root)
    calls = []
    def runner(action, target, journal, environment):
        calls.append(action)
        assert target == root and journal.parent.parent == root.parent
        if action == "deny":
            if failure != "missing_journal":
                journal.write_text(json.dumps({"root": str(root)}))
            if failure == "setup":
                raise RuntimeError("setup failed after journal publication")
        else:
            assert json.loads(journal.read_text()) == {"root": str(root)}
    monkeypatch.setattr(permissions, "_run_acl", runner)
    with pytest.raises(RuntimeError):
        with permissions._windows_readonly(root, os.environ.copy()):
            assert failure == "body"
            raise RuntimeError("consumer failed")
    assert calls == (["deny"] if failure == "missing_journal" else ["deny", "restore"])
    assert _snapshot(root) == before
    assert not list(tmp_path.glob("runtime-acl-*"))


def test_failed_windows_restoration_retains_only_its_private_journal(tmp_path, monkeypatch):
    root = _tree(tmp_path)
    sibling = tmp_path / "do-not-delete"
    sibling.write_bytes(b"unrelated")
    def runner(action, target, journal, environment):
        if action == "deny":
            journal.write_bytes(b"saved descriptors")
        else:
            raise RuntimeError("restoration failed")
    monkeypatch.setattr(permissions, "_run_acl", runner)
    with pytest.raises(RuntimeError):
        with permissions._windows_readonly(root, os.environ.copy()):
            pass
    journals = list(tmp_path.glob("runtime-acl-*/original-dacls.json"))
    assert len(journals) == 1 and journals[0].read_bytes() == b"saved descriptors"
    assert sibling.read_bytes() == b"unrelated" and root.is_dir()


def test_ineffective_denial_is_a_failure(tmp_path):
    with pytest.raises(AssertionError):
        permissions._require_denied(lambda: (tmp_path / "writable").write_bytes(b"unexpected"))


@pytest.mark.skipif(os.name != "nt", reason="requires native Windows DACLs")
@pytest.mark.parametrize("engine", ["powershell.exe", "pwsh"])
def test_windows_dacl_restore_after_completed_setup_error(tmp_path, monkeypatch, engine):
    root = _tree(tmp_path)
    before = _snapshot(root)
    environment = {**os.environ, "PATCHHARBOR_WINDOWS_ACCEPTANCE_ENGINE": engine}
    original = permissions._run_acl
    injected = False
    def runner(action, *args):
        nonlocal injected
        original(action, *args)
        if action == "deny":
            with pytest.raises(PermissionError):
                (root / "module.py").write_bytes(b"blocked")
            injected = True
            raise RuntimeError("failure before consumer")
    monkeypatch.setattr(permissions, "_run_acl", runner)
    with pytest.raises(RuntimeError):
        with permissions.readonly_tree(root, owner=tmp_path, environment=environment):
            pytest.fail("failed setup reached consumer")
    assert injected and _snapshot(root) == before
    (root / "nested/data").write_bytes(b"restored")
    assert not list(tmp_path.glob("runtime-acl-*"))
