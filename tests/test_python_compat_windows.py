"""Actual Windows primitives; Linux simulations are not native proof."""
import json
import os
from pathlib import Path
import subprocess

import pytest

from patchharbor.platform import filesystem, private_directory
from patchharbor.platform.file_handles import open_regular_nofollow
from patchharbor.platform.file_times import windows_file_times
from patchharbor import temporary_resources

pytestmark = [pytest.mark.platform, pytest.mark.skipif(os.name != "nt", reason="native Windows primitives")]


def test_native_legacy_handle_adapter_detects_real_change_with_restored_mtime(tmp_path, monkeypatch):
    path = tmp_path / "same-size.bin"
    path.write_bytes(b"original")
    identity = path.stat()
    # Exercise the old-interpreter adapter even in an existing newer CI lane.
    monkeypatch.setattr(filesystem, "legacy_windows_stat", lambda: True)
    descriptor = open_regular_nofollow(path)
    try:
        before = filesystem.capture_descriptor_metadata(descriptor)
        path.write_bytes(b"modified")
        os.utime(path, ns=(identity.st_atime_ns, identity.st_mtime_ns))
        after = filesystem.capture_descriptor_metadata(descriptor)
        assert before.st_size == after.st_size and before.st_mtime_ns == after.st_mtime_ns
        assert os.path.samestat(before, after) and before.st_birthtime_ns == after.st_birthtime_ns
        assert windows_file_times(descriptor).change_ns == after.st_ctime_ns
        assert not filesystem._same_open_file_state(before, after)
        assert filesystem._same_path_and_open_file_state(path.lstat(), after, allow_path_identity_fallback=False)
    finally:
        os.close(descriptor)
    with pytest.raises(OSError):
        os.fstat(descriptor)


def test_native_junction_is_rejected_without_new_pathlib_api(tmp_path, monkeypatch):
    target = tmp_path / "target"
    target.mkdir()
    link = tmp_path / "junction"
    created = subprocess.run(["cmd.exe", "/d", "/c", "mklink", "/J", str(link), str(target)],
                             capture_output=True, timeout=30)
    assert created.returncode == 0, (created.stdout, created.stderr)
    try:
        monkeypatch.delattr(Path, "is_junction", raising=False)
        assert filesystem.path_kind(link) is filesystem.PathKind.JUNCTION
        from tests.runtime_permissions import _owned_paths
        with pytest.raises(ValueError):
            _owned_paths(link, tmp_path)
        from patchharbor.platform.directories import pin_windows_directory
        with pytest.raises(OSError):
            pin_windows_directory(link)
    finally:
        link.rmdir()
    assert target.is_dir()


@pytest.mark.parametrize("kind", ["named", "random"])
def test_native_private_request_dacl_is_protected_and_inherited(tmp_path, monkeypatch, kind):
    monkeypatch.setattr(temporary_resources, "system_temporary_directory", lambda: tmp_path)
    path = temporary_resources.create_private_request_directory(
        **({"name": "private-request"} if kind == "named" else {"prefix": "private-request-"}))
    script = tmp_path / "inspect-dacl.ps1"
    script.write_text("""
$ErrorActionPreference = 'Stop'
$acl = Get-Acl -LiteralPath $args[0]
$child = Get-Acl -LiteralPath $args[1]
$type = [System.Security.Principal.SecurityIdentifier]
[ordered]@{
  protected = $acl.AreAccessRulesProtected
  user = [System.Security.Principal.WindowsIdentity]::GetCurrent().User.Value
  root = @($acl.GetAccessRules($true, $true, $type) | ForEach-Object {
    [ordered]@{ sid = $_.IdentityReference.Value; access = $_.AccessControlType.ToString();
                 rights = [int]$_.FileSystemRights; inherited = $_.IsInherited }
  })
  child = @($child.GetAccessRules($true, $true, $type) | ForEach-Object {
    [ordered]@{ sid = $_.IdentityReference.Value; access = $_.AccessControlType.ToString();
                 rights = [int]$_.FileSystemRights; inherited = $_.IsInherited }
  })
} | ConvertTo-Json -Depth 5 -Compress
""", encoding="utf-8")
    child = path / "child"
    child.write_bytes(b"private")
    environment = {k: v for k, v in os.environ.items() if k.upper() != "PSMODULEPATH"}
    engine = environment.get("PATCHHARBOR_WINDOWS_ACCEPTANCE_ENGINE") or "powershell.exe"
    try:
        result = subprocess.run([engine, "-NoLogo", "-NoProfile", "-NonInteractive",
            "-ExecutionPolicy", "Bypass", "-File", str(script), str(path), str(child)],
            env=environment, capture_output=True, text=True, timeout=120)
        assert result.returncode == 0, result.stderr
        facts = json.loads(result.stdout)
        assert facts["protected"] is True
        for group in ("root", "child"):
            assert {row["sid"] for row in facts[group]} == {facts["user"], "S-1-5-32-544"}
            assert all(row["access"] == "Allow" and row["rights"] & 0x1F01FF == 0x1F01FF
                       for row in facts[group])
        assert all(row["inherited"] for row in facts["child"])
        with pytest.raises(FileExistsError):
            private_directory.create_private_directory(path)
        assert child.read_bytes() == b"private"
    finally:
        temporary_resources.remove_private_request_directory(path)
    assert not path.exists()
