"""Observe native DACLs without changing permissions or caller environment."""
import json
import os
import subprocess


def assert_private_dacl(root, child, outside):
    script = outside / 'inspect-dacl.ps1'
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
""", encoding='utf-8')
    environment = {k: v for k, v in os.environ.items() if k.upper() != 'PSMODULEPATH'}
    engine = environment.get('PATCHHARBOR_WINDOWS_ACCEPTANCE_ENGINE') or 'powershell.exe'
    result = subprocess.run([engine, '-NoLogo', '-NoProfile', '-NonInteractive',
        '-ExecutionPolicy', 'Bypass', '-File', str(script), str(root), str(child)],
        env=environment, capture_output=True, text=True, timeout=120)
    assert result.returncode == 0, result.stderr
    facts = json.loads(result.stdout)
    assert facts['protected'] is True
    for group in ('root', 'child'):
        assert {row['sid'] for row in facts[group]} == {facts['user'], 'S-1-5-32-544'}
        assert all(row['access'] == 'Allow' and row['rights'] & 0x1F01FF == 0x1F01FF for row in facts[group])
    assert all(row['inherited'] for row in facts['child'])
