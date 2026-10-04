param(
    [Parameter(Mandatory = $true)]
    [ValidateSet('deny', 'restore')][string]$Action,
    [Parameter(Mandatory = $true)][string]$Root,
    [Parameter(Mandatory = $true)][string]$Journal
)

# Test fixture only. The Python caller has already checked ownership and links.
# No owner, audit rule, system policy or ACL outside this temporary tree changes.
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$section = [System.Security.AccessControl.AccessControlSections]::Access
$encoding = [System.Text.UTF8Encoding]::new($false)
[Console]::OutputEncoding = $encoding
$rootPath = [System.IO.Path]::GetFullPath($Root).TrimEnd('\')
$journalPath = [System.IO.Path]::GetFullPath($Journal)
$comparison = [System.StringComparison]::OrdinalIgnoreCase
if ($journalPath.Equals($rootPath, $comparison) -or
    $journalPath.StartsWith($rootPath + '\', $comparison)) {
    throw 'ACL journal must be outside the protected fixture'
}

function Assert-FixturePath([string]$path) {
    $full = [System.IO.Path]::GetFullPath($path)
    if (-not ($full.Equals($rootPath, $comparison) -or
              $full.StartsWith($rootPath + '\', $comparison))) {
        throw 'ACL target is outside the protected fixture'
    }
    $item = Get-Item -LiteralPath $full -Force
    if ($item.Attributes -band [System.IO.FileAttributes]::ReparsePoint) {
        throw 'ACL fixture contains a reparse point'
    }
}

if ($Action -eq 'deny') {
    Assert-FixturePath $rootPath
    $items = @((Get-Item -LiteralPath $rootPath -Force)) +
             @(Get-ChildItem -LiteralPath $rootPath -Recurse -Force |
               Sort-Object { $_.FullName.Length }, FullName)
    $records = @(foreach ($item in $items) {
        Assert-FixturePath $item.FullName
        $acl = Get-Acl -LiteralPath $item.FullName
        $sddl = $acl.GetSecurityDescriptorSddlForm($section)
        $descriptor = [System.Security.AccessControl.RawSecurityDescriptor]::new($sddl)
        if ($null -eq $descriptor.DiscretionaryAcl) {
            throw 'ACL fixture must have an explicit DACL'
        }
        @{ path = $item.FullName; sddl = $sddl }
    })
    $document = @{ root = $rootPath; entries = $records } | ConvertTo-Json -Depth 5 -Compress
    $bytes = $encoding.GetBytes($document)
    $stream = [System.IO.File]::Open($journalPath, [System.IO.FileMode]::CreateNew)
    try {
        $stream.Write($bytes, 0, $bytes.Length)
        $stream.Flush($true)
    } finally {
        $stream.Dispose()
    }
    $identity = [System.Security.Principal.WindowsIdentity]::GetCurrent().User
    $rights = [System.Security.AccessControl.FileSystemRights]'Write, Delete, DeleteSubdirectoriesAndFiles'
    # Explicit non-inherited denies on every saved object. Read/execute and
    # ChangePermissions remain available so restoration needs no elevation.
    $rule = [System.Security.AccessControl.FileSystemAccessRule]::new(
        $identity, $rights, [System.Security.AccessControl.AccessControlType]::Deny)
    foreach ($record in $records) {
        Assert-FixturePath $record.path
        $acl = Get-Acl -LiteralPath $record.path
        $acl.AddAccessRule($rule)
        Set-Acl -LiteralPath $record.path -AclObject $acl
    }
} else {
    $saved = [System.IO.File]::ReadAllText($journalPath, $encoding) | ConvertFrom-Json
    if (-not $saved.root.Equals($rootPath, $comparison)) {
        throw 'ACL journal belongs to a different fixture'
    }
    $failures = @()
    foreach ($record in $saved.entries) {
        try {
            Assert-FixturePath $record.path
            $acl = Get-Acl -LiteralPath $record.path
            $acl.SetSecurityDescriptorSddlForm($record.sddl, $section)
            Set-Acl -LiteralPath $record.path -AclObject $acl
        } catch {
            $failures += "restore '$($record.path)': $($_.Exception.Message)"
        }
    }
    $readback = @(foreach ($record in $saved.entries) {
        try {
            $actual = (Get-Acl -LiteralPath $record.path).GetSecurityDescriptorSddlForm($section)
            @{ path = $record.path; sddl = $actual }
        } catch {
            $failures += "verify '$($record.path)': $($_.Exception.Message)"
        }
    })
    if ($failures.Count -ne 0) {
        throw ("ACL restoration failed for $($failures.Count) operations; keep private journal`n" +
               ($failures -join "`n"))
    }
    # The caller verifies every saved DACL against this complete native readback.
    # JSON avoids host formatting/line wrapping and preserves non-ASCII paths.
    @{ root = $rootPath; entries = $readback } | ConvertTo-Json -Depth 5 -Compress
}
