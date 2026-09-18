"""Real format-1 apply and dry-run must enforce the core permission contract."""
from __future__ import annotations

import json
import os
from pathlib import Path
import stat
import shlex
import sys
import zipfile

import pytest

from patchharbor.application import apply_patch_package, dry_run_patch_package, register_repository
from patchharbor.errors import PatchHarborError
from patchharbor.exit_status import ExitCode, exit_code_for_error
from patchharbor.patch_package import resolve_patch_package
from tests.registration_support import create_repository, git

pytestmark = [pytest.mark.e2e, pytest.mark.skipif(os.name != "posix", reason="native POSIX modes")]


def package_for(path: Path, context, *, new_mode: int = 0o755, existing_mode: int = 0o644):
    document = {
        "marker": "patch-harbor", "format_version": 1,
        "repo_id": str(context.repo_id), "base_commit": str(context.base_commit),
        "state_fingerprint": context.state_fingerprint,
        "fingerprint_algorithm": context.fingerprint_algorithm, "entrypoint": "run.sh",
    }
    script = f'''#!/bin/bash
# PATCHHARBOR
set -eu
{shlex.quote(sys.executable)} - <<'MODE_CHECK'
from pathlib import Path
import stat
assert stat.S_IMODE(Path("tracked.txt").stat().st_mode) == {existing_mode!r}
assert stat.S_IMODE(Path("tools/new.sh").stat().st_mode) == 0o755
assert Path("tracked.txt").read_bytes() == b"changed\\n"
MODE_CHECK
test "$(tools/new.sh)" = executed
'''.encode()
    with zipfile.ZipFile(path, "w") as archive:
        for name, data, mode in (("patch.json", json.dumps(document).encode(), 0o644),
                                 ("run.sh", script, 0o755),
                                 ("tracked.txt", b"changed\n", 0o600),
                                 ("tools/new.sh", b"#!/bin/sh\nprintf executed\n", new_mode)):
            info = zipfile.ZipInfo(name)
            info.create_system = 3
            info.external_attr = (stat.S_IFREG | mode) << 16
            archive.writestr(info, data)
    return resolve_patch_package(path)


@pytest.mark.parametrize("mode", (0o644, 0o664, 0o666, 0o755, 0o775, 0o777))
def test_entrypoint_observes_correct_modes_after_core_mutation(tmp_path: Path, mode: int) -> None:
    repo = create_repository(tmp_path / "repo")
    target = repo / "tracked.txt"
    target.chmod(mode)
    git(repo, "add", "tracked.txt")
    git(repo, "commit", "--quiet", "--allow-empty", "-m", "fixture permissions")
    context = register_repository(repo)
    package = package_for(tmp_path / "patch.zip", context, existing_mode=mode)
    report = apply_patch_package(package, output_directory=tmp_path / "results")
    assert report.process_exit_code == 0
    assert report.primary_result.entrypoint_started
    assert stat.S_IMODE(target.stat().st_mode) == mode
    assert stat.S_IMODE((repo / "tools/new.sh").stat().st_mode) == 0o755
    assert stat.S_IMODE((repo / ".patchharbor/config.json").stat().st_mode) == 0o600


@pytest.mark.parametrize("mode", (0o644, 0o664, 0o666, 0o777))
def test_dry_run_preserves_bytes_modes_and_missing_directories(tmp_path: Path, mode: int) -> None:
    repo = create_repository(tmp_path / "repo")
    target = repo / "tracked.txt"
    target.chmod(mode)
    git(repo, "add", "tracked.txt")
    git(repo, "commit", "--quiet", "--allow-empty", "-m", "fixture permissions")
    context = register_repository(repo)
    package = package_for(tmp_path / "patch.zip", context)
    report = dry_run_patch_package(package, output_directory=tmp_path / "results")
    assert report.process_exit_code == 0
    assert not report.primary_result.entrypoint_started
    assert target.read_bytes() == b"base\n"
    assert stat.S_IMODE(target.stat().st_mode) == mode
    assert not (repo / "tools").exists()


@pytest.mark.parametrize("dry_run", (False, True))
@pytest.mark.parametrize("mode", (0o4644, 0o2664, 0o1777))
def test_special_existing_target_rejected_without_entrypoint(tmp_path: Path, dry_run: bool, mode: int) -> None:
    repo = create_repository(tmp_path / "repo")
    target = repo / "tracked.txt"
    target.chmod(mode)
    git(repo, "add", "tracked.txt")
    git(repo, "commit", "--quiet", "--allow-empty", "-m", "fixture permissions")
    context = register_repository(repo)
    package = package_for(tmp_path / "patch.zip", context)
    operation = dry_run_patch_package if dry_run else apply_patch_package
    with pytest.raises(PatchHarborError) as raised:
        operation(package, output_directory=tmp_path / "results")
    assert exit_code_for_error(raised.value) == ExitCode.PAYLOAD_PREPARATION_ERROR
    assert not raised.value.run_report.primary_result.entrypoint_started
    assert target.read_bytes() == b"base\n"
    assert stat.S_IMODE(target.stat().st_mode) == mode
    assert not (repo / "tools").exists()


def test_unsafe_zip_rejected_before_any_apply_mutation(tmp_path: Path) -> None:
    repo = create_repository(tmp_path / "repo")
    context = register_repository(repo)
    with pytest.raises(PatchHarborError) as raised:
        package_for(tmp_path / "patch.zip", context, new_mode=0o777)
    assert exit_code_for_error(raised.value) == ExitCode.SOURCE_ERROR
    assert (repo / "tracked.txt").read_bytes() == b"base\n"
    assert not (repo / "tools").exists()
