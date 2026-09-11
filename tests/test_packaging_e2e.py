from __future__ import annotations

from configparser import ConfigParser
from email.parser import BytesParser
from email.policy import default as default_email_policy
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import tomllib
import zipfile

import pytest

from patchharbor import __version__
from tests.platform_support import PROJECT_ROOT, native_script, native_value
from tests.registration_support import isolated_user_environment


pytestmark = pytest.mark.packaging

MAX_WHEEL_BYTES = 256 * 1024
RELEASE_VERSION = "1.1.1"
EXPECTED_RUNTIME_FILES = {
    "patchharbor/__init__.py",
    "patchharbor/application.py",
    "patchharbor/archive_policy.py",
    "patchharbor/archive_evidence.py",
    "patchharbor/archive_git.py",
    "patchharbor/archive_files.py",
    "patchharbor/exchange_archive.py",
    "patchharbor/exchange_recovery.py",
    "patchharbor/platform/archive.py",
    "patchharbor/apply_mutation.py",
    "patchharbor/apply_preflight.py",
    "patchharbor/apply_repository.py",
    "patchharbor/bundle_paths.py",
    "patchharbor/bundle_names.py",
    "patchharbor/bundle_handoff.py",
    "patchharbor/chat_instructions.py",
    "patchharbor/result_bundle_handoff.py",
    "patchharbor/platform/environment.py",
    "patchharbor/bundles.py",
    "patchharbor/cli.py",
    "patchharbor/configuration.py",
    "patchharbor/context_output.py",
    "patchharbor/errors.py",
    "patchharbor/execution.py",
    "patchharbor/exchange.py",
    "patchharbor/exchange_paths.py",
    "patchharbor/exchange_state.py",
    "patchharbor/git_capture.py",
    "patchharbor/git_objects.py",
    "patchharbor/git_patches.py",
    "patchharbor/git_commands.py",
    "patchharbor/identifier_presentation.py",
    "patchharbor/interpreters.py",
    "patchharbor/json_document.py",
    "patchharbor/models.py",
    "patchharbor/output.py",
    "patchharbor/parser.py",
    "patchharbor/patch_manifest.py",
    "patchharbor/patch_package.py",
    "patchharbor/payload_files.py",
    "patchharbor/presentation.py",
    "patchharbor/progress.py",
    "patchharbor/registration.py",
    "patchharbor/registry.py",
    "patchharbor/repository.py",
    "patchharbor/repository_paths.py",
    "patchharbor/repository_state.py",
    "patchharbor/result_bundle.py",
    "patchharbor/result_bundle_capture.py",
    "patchharbor/result_bundle_publication.py",
    "patchharbor/result_bundle_snapshot.py",
    "patchharbor/result_bundle_target.py",
    "patchharbor/result_bundle_writer.py",
    "patchharbor/locks.py",
    "patchharbor/resource_policy.py",
    "patchharbor/run_log.py",
    "patchharbor/run_report.py",
    "patchharbor/sources.py",
    "patchharbor/state_fingerprint.py",
    "patchharbor/temporary_resources.py",
    "patchharbor/user_paths.py",
    "patchharbor_watcher/__init__.py",
    "patchharbor_watcher/loop.py",
    "patchharbor_watcher/cli.py",
    "patchharbor_watcher/lifecycle.py",
    "patchharbor_watcher/apply_boundary.py",
    "patchharbor_watcher/systemd_linux.py",
    "patchharbor/zip_payloads.py",
    "patchharbor/platform/__init__.py",
    "patchharbor/platform/errors.py",
    "patchharbor/platform/filesystem.py",
    "patchharbor/platform/lifecycle.py",
    "patchharbor/platform/locking.py",
    "patchharbor/platform/paths.py",
    "patchharbor/platform/posix.py",
    "patchharbor/platform/runtime.py",
    "patchharbor/platform/windows.py",
}


def _distribution_metadata_contract(
    raw_metadata: bytes,
) -> tuple[tuple[tuple[str, tuple[str, ...]], ...], tuple[str, ...]]:
    message = BytesParser(policy=default_email_policy).parsebytes(raw_metadata)
    names = sorted({name.lower() for name in message.keys()})
    headers = tuple(
        (
            name,
            tuple(str(value) for value in message.get_all(name, [])),
        )
        for name in names
    )
    payload = message.get_payload()
    assert isinstance(payload, str)
    return headers, tuple(payload.splitlines())


def _wheel_entry_points(raw_entry_points: bytes) -> tuple[tuple[str, str], ...]:
    parser = ConfigParser(interpolation=None)
    parser.optionxform = str
    parser.read_string(raw_entry_points.decode("utf-8"))
    assert parser.sections() == ["console_scripts"]
    return tuple(sorted(parser.items("console_scripts")))


def _run(
    command: list[str],
    *,
    cwd: Path,
    environment: dict[str, str] | None = None,
    timeout: int = 180,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=cwd,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def _copy_project_for_release(tmp_path: Path) -> Path:
    source_tree = tmp_path / "release-source"
    shutil.copytree(
        PROJECT_ROOT,
        source_tree,
        ignore=shutil.ignore_patterns(
            ".git",
            ".venv",
            "build",
            "dist",
            "*.egg-info",
            "__pycache__",
            "*.pyc",
            "*.pyo",
            "*.log",
            "*_Patch_*.zip",
            "*_Result_*.zip",
        ),
    )

    stale_package = source_tree / "build" / "lib" / "patchharbor"
    stale_package.mkdir(parents=True)
    (stale_package / "input.py").write_text(
        "raise RuntimeError('stale legacy module')\n",
        encoding="utf-8",
    )
    (stale_package / "files.py").write_text(
        "raise RuntimeError('stale legacy module')\n",
        encoding="utf-8",
    )
    stale_egg_info = source_tree / "src" / "patchharbor.egg-info"
    stale_egg_info.mkdir()
    (stale_egg_info / "SOURCES.txt").write_text(
        "src/patchharbor/removed_release_module.py\n",
        encoding="utf-8",
    )
    stale_bytecode = source_tree / "src" / "patchharbor" / "__pycache__"
    stale_bytecode.mkdir()
    (stale_bytecode / "removed_release_module.pyc").write_bytes(
        b"stale-bytecode"
    )
    return source_tree


def _git(repository: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
    completed = _run(["git", *arguments], cwd=repository)
    assert completed.returncode == 0, completed.stdout + completed.stderr
    return completed


def _create_release_repository(path: Path) -> Path:
    path.mkdir()
    _git(path, "init", "--quiet")
    _git(path, "config", "user.name", "PatchHarbor Release Test")
    _git(path, "config", "user.email", "patchharbor@example.invalid")
    _git(path, "config", "core.autocrlf", "false")
    (path / "tracked.txt").write_bytes(b"release-base\n")
    _git(path, "add", "tracked.txt")
    _git(path, "commit", "--quiet", "-m", "release base")
    return path


def _successful_json_result(
    completed: subprocess.CompletedProcess[str],
) -> dict[str, object]:
    assert completed.returncode == 0, completed.stdout + completed.stderr
    document = json.loads(completed.stdout)
    assert document["success"] is True
    result = document["result"]
    assert isinstance(result, dict)
    return result


def _write_release_patch_package(
    path: Path,
    context: dict[str, object],
) -> str:
    entrypoint_name = native_value("run.sh", "run.ps1")
    manifest = {
        "marker": "patch-harbor",
        "format_version": 1,
        "repo_id": context["repo_id"],
        "base_commit": context["base_commit"],
        "state_fingerprint": context["state_fingerprint"],
        "fingerprint_algorithm": "patchharbor-state-v1",
        "entrypoint": entrypoint_name,
    }
    entrypoint = native_script(
        'printf "%s\n" "installed-apply"\n'
        'printf "%s" "entrypoint-ok" > release-applied.txt',
        '[Console]::Out.WriteLine("installed-apply")\n'
        '[System.IO.File]::WriteAllText("release-applied.txt", "entrypoint-ok")',
    )
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr(
            "patch.json",
            json.dumps(
                manifest,
                ensure_ascii=False,
                allow_nan=False,
                separators=(",", ":"),
            ).encode("utf-8"),
        )
        archive.writestr(entrypoint_name, entrypoint.encode("utf-8"))
        archive.writestr("nested/release.bin", b"\x00release-payload\xff")
    return entrypoint_name


def test_release_metadata_is_complete_and_runtime_has_no_dependencies() -> None:
    project = tomllib.loads(
        (PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    )["project"]

    assert __version__ == RELEASE_VERSION
    assert project["name"] == "patchharbor"
    assert project["dynamic"] == ["version"]
    assert project["requires-python"] == ">=3.12"
    assert project["license"] == "MIT"
    assert project["license-files"] == ["LICENSE"]
    assert project["dependencies"] == []
    assert project["scripts"] == {
        "patchharbor": "patchharbor.cli:main",
        "patchharbor-watcher": "patchharbor_watcher.cli:main",
    }
    assert "Development Status :: 5 - Production/Stable" in project["classifiers"]
    assert (PROJECT_ROOT / "LICENSE").is_file()


def test_release_distributions_run_after_pipx_installation(tmp_path: Path) -> None:
    release_source = _copy_project_for_release(tmp_path)
    distribution_dir = tmp_path / "dist"
    build = _run(
        [
            sys.executable,
            str(release_source / "scripts" / "build_release.py"),
            "--outdir",
            str(distribution_dir),
        ],
        cwd=release_source,
    )

    assert build.returncode == 0, build.stdout + build.stderr
    wheels = list(distribution_dir.glob("patchharbor-*.whl"))
    source_distributions = list(distribution_dir.glob("patchharbor-*.tar.gz"))
    assert [path.name for path in wheels] == [
        f"patchharbor-{RELEASE_VERSION}-py3-none-any.whl"
    ]
    assert [path.name for path in source_distributions] == [
        f"patchharbor-{RELEASE_VERSION}.tar.gz"
    ]
    assert wheels[0].stat().st_size <= MAX_WHEEL_BYTES

    wheel_metadata_contract: tuple[
        tuple[tuple[str, tuple[str, ...]], ...],
        tuple[str, ...],
    ]
    wheel_scripts: tuple[tuple[str, str], ...]
    with zipfile.ZipFile(wheels[0]) as wheel:
        names = set(wheel.namelist())
        runtime_files = {
            name
            for name in names
            if name.startswith(("patchharbor/", "patchharbor_watcher/"))
        }
        assert runtime_files == EXPECTED_RUNTIME_FILES
        assert "patchharbor/input.py" not in names
        assert "patchharbor/files.py" not in names

        metadata_name = next(
            name for name in names if name.endswith(".dist-info/METADATA")
        )
        raw_metadata = wheel.read(metadata_name)
        wheel_metadata_contract = _distribution_metadata_contract(raw_metadata)
        metadata_lines = raw_metadata.decode("utf-8").splitlines()
        assert f"Version: {RELEASE_VERSION}" in metadata_lines
        assert "License-Expression: MIT" in metadata_lines
        runtime_requirements = [
            line
            for line in metadata_lines
            if line.startswith("Requires-Dist:") and 'extra == "dev"' not in line
        ]
        assert runtime_requirements == []
        assert any(name.endswith(".dist-info/licenses/LICENSE") for name in names)
        chat_data_name = (
            f"patchharbor-{RELEASE_VERSION}.data/data/share/patchharbor/"
            "CHAT_INSTRUCTIONS.md"
        )
        assert wheel.read(chat_data_name) == (
            release_source / "CHAT_INSTRUCTIONS.md"
        ).read_bytes()

        entry_points_name = next(
            name for name in names if name.endswith(".dist-info/entry_points.txt")
        )
        raw_entry_points = wheel.read(entry_points_name)
        wheel_scripts = _wheel_entry_points(raw_entry_points)
        assert wheel_scripts == (
            ("patchharbor", "patchharbor.cli:main"),
            ("patchharbor-watcher", "patchharbor_watcher.cli:main"),
        )
        assert not any(
            name.startswith(("repo_assist/", "promptbridge/"))
            for name in names
        )

    with tarfile.open(source_distributions[0], "r:gz") as source_distribution:
        names = set(source_distribution.getnames())
        root = f"patchharbor-{RELEASE_VERSION}"
        pkg_info = source_distribution.extractfile(f"{root}/PKG-INFO")
        pyproject_file = source_distribution.extractfile(
            f"{root}/pyproject.toml"
        )
        assert pkg_info is not None and pyproject_file is not None
        assert (
            _distribution_metadata_contract(pkg_info.read())
            == wheel_metadata_contract
        )
        source_project = tomllib.loads(
            pyproject_file.read().decode("utf-8")
        )["project"]
        assert tuple(sorted(source_project["scripts"].items())) == wheel_scripts
        for required in (
            f"{root}/CHAT_INSTRUCTIONS.md",
            f"{root}/LICENSE",
            f"{root}/README.md",
            f"{root}/pyproject.toml",
            f"{root}/src/patchharbor/cli.py",
            f"{root}/src/patchharbor_watcher/__init__.py",
            f"{root}/src/patchharbor_watcher/loop.py",
            f"{root}/src/patchharbor_watcher/cli.py",
            f"{root}/src/patchharbor_watcher/lifecycle.py",
            f"{root}/src/patchharbor_watcher/apply_boundary.py",
            f"{root}/src/patchharbor_watcher/systemd_linux.py",
        ):
            assert required in names
        for forbidden in (
            f"{root}/MANIFEST.in",
            f"{root}/scripts/",
            f"{root}/tests/",
            f"{root}/planning/",
            f"{root}/.github/",
            f"{root}/docker/",
            f"{root}/build/",
            f"{root}/dist/",
        ):
            assert not any(name.startswith(forbidden) for name in names)
        chat_member = source_distribution.extractfile(
            f"{root}/CHAT_INSTRUCTIONS.md"
        )
        assert chat_member is not None
        assert chat_member.read() == (
            release_source / "CHAT_INSTRUCTIONS.md"
        ).read_bytes()
        readme_member = source_distribution.extractfile(f"{root}/README.md")
        assert readme_member is not None
        assert readme_member.read() == (release_source / "README.md").read_bytes()
        assert not any(name.endswith(".log") for name in names)
        assert f"{root}/src/patchharbor/input.py" not in names
        assert f"{root}/src/patchharbor/files.py" not in names
        generated_sources = source_distribution.extractfile(
            f"{root}/src/patchharbor.egg-info/SOURCES.txt"
        )
        assert generated_sources is not None
        assert "removed_release_module" not in generated_sources.read().decode(
            "utf-8"
        )
        assert not any("__pycache__" in name for name in names)
        assert not any(name.endswith((".pyc", ".pyo")) for name in names)
        assert not any(
            name.startswith((f"{root}/repo_assist/", f"{root}/promptbridge/"))
            for name in names
        )

    pipx_home = tmp_path / "pipx-home"
    pipx_bin = tmp_path / "pipx-bin"
    environment = os.environ.copy()
    environment.pop("PYTHONPATH", None)
    environment.pop("PYTHONHOME", None)
    environment.update(
        {
            "PIPX_HOME": str(pipx_home),
            "PIPX_BIN_DIR": str(pipx_bin),
            "PIPX_MAN_DIR": str(tmp_path / "pipx-man"),
            "PIPX_DEFAULT_PYTHON": sys.executable,
            "PIPX_DEFAULT_BACKEND": "pip",
            "PIPX_DISABLE_SHARED_LIBS_AUTO_UPGRADE": "1",
            "PIP_DISABLE_PIP_VERSION_CHECK": "1",
            "PIP_NO_INDEX": "1",
        }
    )
    shared_environment = pipx_home / "shared"
    environment["PIPX_SHARED_LIBS"] = str(shared_environment)
    seed_shared_environment = _run(
        [
            sys.executable,
            "-m",
            "venv",
            str(shared_environment),
        ],
        cwd=tmp_path,
        environment=environment,
    )
    assert seed_shared_environment.returncode == 0, (
        seed_shared_environment.stdout + seed_shared_environment.stderr
    )

    install = _run(
        [
            sys.executable,
            "-m",
            "pipx",
            "install",
            "--python",
            sys.executable,
            str(wheels[0]),
        ],
        cwd=tmp_path,
        environment=environment,
    )

    assert install.returncode == 0, install.stdout + install.stderr

    executable_name = native_value("patchharbor", "patchharbor.exe")
    executable = pipx_bin / executable_name
    watcher_executable_name = native_value(
        "patchharbor-watcher",
        "patchharbor-watcher.exe",
    )
    watcher_executable = pipx_bin / watcher_executable_name
    empty_workdir = tmp_path / "empty-workdir"
    empty_workdir.mkdir()
    assert list(empty_workdir.iterdir()) == []

    assert watcher_executable.is_file()

    help_outputs: dict[tuple[str, ...], str] = {}
    for help_arguments in (
        ("--help",),
        ("configure", "--help"),
        ("configure", "exchange-directory", "--help"),
        ("configure", "show", "--help"),
        ("register", "--help"),
        ("registry", "--help"),
        ("registry", "list", "--help"),
        ("unregister", "--help"),
        ("context", "--help"),
        ("bundle", "--help"),
        ("apply", "--help"),
        ("fs", "--help"),
        ("fs", "run", "--help"),
    ):
        help_result = _run(
            [str(executable), *help_arguments],
            cwd=empty_workdir,
            environment=environment,
        )
        assert help_result.returncode == 0
        help_outputs[help_arguments] = " ".join(help_result.stdout.split())

    assert "Register local Git repository instances" in help_outputs[("--help",)]
    assert "one user-specific config.json" in help_outputs[("configure", "--help")]
    assert "committed HEAD" in help_outputs[("register", "--help")]
    assert "current working directory to one registered repository" in (
        help_outputs[("apply", "--help")]
    )
    assert "newest eligible Exchange package by mtime_ns" in (
        help_outputs[("apply", "--help")]
    )
    assert "deterministic normalized-filename tie-breaker" in (
        help_outputs[("apply", "--help")]
    )
    assert "watcher's internal automatic mode remains global" in (
        help_outputs[("apply", "--help")]
    )

    watcher_help = _run(
        [str(watcher_executable), "--help"],
        cwd=empty_workdir,
        environment=environment,
    )
    assert watcher_help.returncode == 0
    watcher_help_text = " ".join(watcher_help.stdout.split())
    assert "PatchHarbor config.json" in watcher_help_text
    assert "patchharbor configure exchange-directory DIRECTORY" in (
        watcher_help_text
    )
    assert "Termux/Android" in watcher_help_text

    for excluded_command in (
        "websocket",
        "clipboard",
        "ssh",
        "save",
        "plugins",
        "watcher",
    ):
        excluded = _run(
            [str(executable), excluded_command, "--help"],
            cwd=empty_workdir,
            environment=environment,
        )
        assert excluded.returncode == 2

    version_result = _run(
        [str(executable), "--version"],
        cwd=empty_workdir,
        environment=environment,
    )
    assert version_result.returncode == 0

    source_dir = tmp_path / "source"
    source_dir.mkdir()
    script_suffix = native_value(".sh", ".ps1")
    script_path = source_dir / f"release-smoke{script_suffix}"
    script_path.write_text(
        native_script(
            'printf "%s\\n" "release-smoke"\n'
            'printf "%s" "cwd-ok" > release-cwd.txt',
            'Write-Output "release-smoke"\n'
            '[System.IO.File]::WriteAllText("release-cwd.txt", "cwd-ok")',
        ),
        encoding="utf-8",
    )

    run_result = _run(
        [str(executable), "fs", "run", str(script_path)],
        cwd=empty_workdir,
        environment=environment,
    )

    assert run_result.returncode == 0
    assert (empty_workdir / "release-cwd.txt").read_text(encoding="utf-8") == (
        "cwd-ok"
    )

    runtime_environment = environment.copy()
    runtime_environment.update(
        isolated_user_environment(tmp_path / "patchharbor-user")
    )

    invalid_core_invocations = (
        ("register", "--new", str(tmp_path / "missing-repository")),
        ("registry", "list", "--js"),
        ("context", "--js", str(tmp_path / "missing-repository")),
        (
            "bundle",
            "--out",
            str(tmp_path / "invalid-results"),
            str(tmp_path / "missing-repository"),
        ),
        ("apply", "--dry", str(tmp_path / "missing-package.zip")),
        ("fs", "run", "--pla", str(tmp_path / "missing-script.sh")),
        ("register", "--json", str(tmp_path / "missing-repository")),
        ("apply", "--log", str(tmp_path / "missing-package.zip")),
    )
    for arguments in invalid_core_invocations:
        rejected = _run(
            [str(executable), *arguments],
            cwd=empty_workdir,
            environment=runtime_environment,
        )
        assert rejected.returncode == 2

    watcher_input = tmp_path / "watcher-abbreviation-input"
    watcher_input.mkdir()
    for arguments in (
        ("--conf", str(watcher_input)),
        ("--json",),
    ):
        rejected = _run(
            [str(watcher_executable), *arguments],
            cwd=empty_workdir,
            environment=runtime_environment,
        )
        assert rejected.returncode == 2

    repository = _create_release_repository(tmp_path / "release-repository")

    registered = _run(
        [str(executable), "register", str(repository)],
        cwd=empty_workdir,
        environment=runtime_environment,
    )
    assert registered.returncode == 0

    exchange_directory = tmp_path / "exchange"
    configured_exchange = _run(
        [
            str(executable),
            "configure",
            "exchange-directory",
            str(exchange_directory),
        ],
        cwd=empty_workdir,
        environment=runtime_environment,
    )
    assert configured_exchange.returncode == 0

    context = _successful_json_result(
        _run(
            [str(executable), "context", "--json", str(repository)],
            cwd=empty_workdir,
            environment=runtime_environment,
        )
    )
    assert context["dirty"] is False

    manual_result = _successful_json_result(
        _run(
            [
                str(executable),
                "bundle",
                "--json",
                str(repository),
            ],
            cwd=empty_workdir,
            environment=runtime_environment,
        )
    )
    manual_bundle = Path(str(manual_result["result_bundle_path"]))
    assert manual_bundle.parent == exchange_directory.resolve()
    assert manual_bundle.is_file()
    with zipfile.ZipFile(manual_bundle) as archive:
        assert archive.read("base/tracked.txt") == b"release-base\n"
        assert "logs/execution.log" not in archive.namelist()
        assert archive.namelist().count("CHAT_INSTRUCTIONS.md") == 1
        assert archive.namelist().count("environment.json") == 1
        assert archive.read("CHAT_INSTRUCTIONS.md").endswith(
            (release_source / "CHAT_INSTRUCTIONS.md").read_bytes()
        )
        handoff = json.loads(archive.read("environment.json"))
        assert handoff["repository_path"] == str(repository.resolve())
        assert handoff["exchange_directory"] == str(exchange_directory.resolve())
        assert handoff["runtime"]["patchharbor_version"] == RELEASE_VERSION

    package_path = tmp_path / "release-package.zip"
    entrypoint_name = _write_release_patch_package(package_path, context)
    dry_result = _successful_json_result(
        _run(
            [
                str(executable),
                "apply",
                "--dry-run",
                "--json",
                "--timeout",
                "30",
                "--output-dir",
                str(tmp_path / "dry-results"),
                str(package_path),
            ],
            cwd=empty_workdir,
            environment=runtime_environment,
        )
    )
    assert dry_result["primary_result"]["kind"] == "dry_run_success"
    assert not (repository / "nested").exists()
    assert not (repository / "release-applied.txt").exists()

    apply_result = _successful_json_result(
        _run(
            [
                str(executable),
                "apply",
                "--json",
                "--plain",
                "--no-color",
                "--timeout",
                "30",
                str(package_path),
            ],
            cwd=empty_workdir,
            environment=runtime_environment,
        )
    )
    assert apply_result["primary_result"]["kind"] == "success"
    assert (repository / "nested" / "release.bin").read_bytes() == (
        b"\x00release-payload\xff"
    )
    assert (repository / "release-applied.txt").read_text(
        encoding="utf-8"
    ) == "entrypoint-ok"
    assert not (repository / entrypoint_name).exists()
    apply_bundle = Path(str(apply_result["result_bundle"]["path"]))
    assert apply_bundle.parent == exchange_directory.resolve()
    assert apply_bundle.is_file()
    with zipfile.ZipFile(apply_bundle) as archive:
        assert "logs/execution.log" in archive.namelist()
        assert archive.read("untracked/nested/release.bin") == (
            b"\x00release-payload\xff"
        )

    watcher_help = _run(
        [str(watcher_executable), "--help"],
        cwd=empty_workdir,
        environment=runtime_environment,
    )
    assert watcher_help.returncode == 0
    assert "--install-systemd-user-unit" in watcher_help.stdout
    assert "--poll-interval" in watcher_help.stdout
    assert "--configure" not in watcher_help.stdout
    assert "INPUT_DIRECTORY" not in watcher_help.stdout

    legacy_watcher = _run(
        [str(watcher_executable), "--configure", str(tmp_path / "incoming")],
        cwd=empty_workdir,
        environment=runtime_environment,
    )
    assert legacy_watcher.returncode == 2
