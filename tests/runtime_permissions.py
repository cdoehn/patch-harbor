"""Native read-only fixtures, confined to a caller-owned temporary tree."""
from __future__ import annotations

from contextlib import contextmanager
import os
from pathlib import Path
import shutil
import subprocess
import tempfile


def _owned_paths(root: Path, owner: Path) -> list[Path]:
    if not root.is_absolute() or root.is_symlink() or root.is_junction():
        raise ValueError("permission fixture requires an absolute unlinked root")
    resolved, owned = root.resolve(strict=True), owner.resolve(strict=True)
    if resolved == owned or not resolved.is_relative_to(owned) or not root.is_dir():
        raise ValueError("permission fixture must be below its owned temporary root")
    paths = [root, *sorted(root.rglob("*"))]
    if any(p.is_symlink() or p.is_junction() or not (p.is_file() or p.is_dir()) for p in paths):
        raise ValueError("permission fixture contains a link or special file")
    return paths


def _run_acl(action: str, root: Path, journal: Path, environment: dict[str, str]) -> None:
    engine = environment.get("PATCHHARBOR_WINDOWS_ACCEPTANCE_ENGINE", "powershell.exe") or "powershell.exe"
    if engine not in {"powershell.exe", "pwsh"}:
        raise ValueError("unsupported native permission engine")
    executable = shutil.which(engine, path=environment.get("PATH"))
    if executable is None:
        raise RuntimeError("native Windows permission engine is unavailable")
    script = Path(__file__).parent / "fixtures/runtime_readonly.ps1"
    # Python can inherit PowerShell 7's module paths even when launching 5.1.
    # Let each engine construct its own defaults; this fixture needs only its
    # built-in modules. Keep the caller's environment unchanged.
    child_environment = {key: value for key, value in environment.items()
                         if key.upper() != "PSMODULEPATH"}
    result = subprocess.run(
        [executable, "-NoLogo", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
         "-File", str(script), "-Action", action, "-Root", str(root), "-Journal", str(journal)],
        env=child_environment, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=300,
    )
    if result.returncode:
        raise RuntimeError(f"native ACL {action} failed: {result.stdout}{result.stderr}")


@contextmanager
def _windows_readonly(root: Path, environment: dict[str, str]):
    # Persist the original DACLs before changing any of them, including when the
    # setup process fails or times out. The journal lives outside the denied tree.
    private = Path(tempfile.mkdtemp(prefix="runtime-acl-", dir=root.parent))
    journal = private / "original-dacls.json"
    restored = False
    try:
        try:
            _run_acl("deny", root, journal, environment)
            if not journal.is_file():
                raise RuntimeError("native ACL setup did not save its restoration journal")
            yield
        finally:
            if journal.is_file():
                _run_acl("restore", root, journal, environment)
                restored = True
    finally:
        # A failed restoration retains its private journal for diagnosis. Never
        # remove the fixture, unrelated sibling files or any external ACL data.
        if restored or not journal.exists():
            shutil.rmtree(private)


@contextmanager
def _posix_readonly(paths: list[Path]):
    saved = [(path, path.stat().st_mode & 0o7777) for path in paths]
    try:
        for path, mode in saved:
            path.chmod(mode & ~0o222)
        yield
    finally:
        for path, mode in saved:
            path.chmod(mode)


def _require_denied(operation) -> None:
    try:
        operation()
    except PermissionError:
        return
    raise AssertionError("native read-only fixture unexpectedly allowed a write")


@contextmanager
def readonly_tree(root: Path, *, owner: Path, environment: dict[str, str]):
    """Restore original permissions after success, body failure or partial setup.

    Windows denies writes/deletion through DACLs for the current identity; chmod
    is not an ACL substitute. POSIX root can bypass mode bits and is explicitly
    reported as unenforced; it is not a native read-only acceptance result.
    """
    _owned_paths(root, owner)
    with tempfile.TemporaryDirectory(prefix="runtime-permission-probe-", dir=root) as name:
        probe = Path(name)
        existing = probe / "existing"
        existing.write_bytes(b"permission probe\n")
        paths = _owned_paths(root, owner)
        native = os.name == "nt"
        effective = native or os.geteuid() != 0
        guard = _windows_readonly(root, environment) if native else _posix_readonly(paths)
        with guard:
            if effective:
                # Actual filesystem operations in this token, not mode-bit or
                # os.access guesses. Include the installation root itself.
                _require_denied(lambda: (root / (probe.name + "-file")).write_bytes(b"new"))
                _require_denied(lambda: (probe / "new-directory").mkdir())
                _require_denied(lambda: existing.write_bytes(b"modified"))
                _require_denied(lambda: existing.rename(probe / "renamed"))
                _require_denied(existing.unlink)
                assert existing.read_bytes() == b"permission probe\n"
            yield {"enforced": effective, "method": "windows_dacl" if native else "posix_mode"}
