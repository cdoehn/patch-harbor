from __future__ import annotations

from io import BytesIO, StringIO
from pathlib import Path
import stat
import zipfile

import pytest

from patchharbor.errors import ExitCode, PatchHarborError
import patchharbor.application as script_application
from patchharbor.application import discover_directory_candidates, run_script_path
import patchharbor.bundles as script_bundles
import patchharbor.zip_payloads as zip_payloads
from patchharbor.resource_policy import DEFAULT_RESOURCE_POLICY, ResourcePolicy
from patchharbor.sources import file_input_artifact


REQUIRED_MARKER = "# PATCHHARBOR"


def _write_zip(path: Path, entries: list[tuple[str, str]]) -> None:
    with zipfile.ZipFile(path, "w") as archive:
        for name, content in entries:
            archive.writestr(name, content)


def _write_raw_member_name(
    archive: zipfile.ZipFile,
    member_name: str,
    content: bytes,
) -> None:
    """Write one exact archive member name without host-OS normalization."""
    entry = zipfile.ZipInfo("placeholder")
    entry.filename = member_name
    entry.orig_filename = member_name
    archive.writestr(entry, content)


def _run_path(
    path: Path,
    cwd: Path,
    *,
    timeout_seconds: float = 1,
    resource_policy: ResourcePolicy = DEFAULT_RESOURCE_POLICY,
) -> int:
    return run_script_path(
        path,
        cwd=cwd,
        timeout_seconds=timeout_seconds,
        resource_policy=resource_policy,
    )


def test_directory_discovery_includes_zip_with_valid_script(tmp_path: Path) -> None:
    archive_path = tmp_path / "scripts.zip"
    _write_zip(
        archive_path,
        [("run.sh", f"{REQUIRED_MARKER}\n")],
    )

    candidates = discover_directory_candidates(tmp_path)

    assert [candidate.path for candidate in candidates] == [archive_path]


def test_zip_without_scripts_is_rejected_even_with_binary_payloads(
    tmp_path: Path,
) -> None:
    nested_path = tmp_path / "nested.zip"
    _write_zip(nested_path, [("nested.sh", f"{REQUIRED_MARKER}\n")])

    archive_path = tmp_path / "payloads.zip"
    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.writestr("folder/", b"")
        archive.writestr("notes.txt", "not executable\n")
        archive.writestr("nested.zip", nested_path.read_bytes())

    with pytest.raises(PatchHarborError) as raised:
        _run_path(archive_path, tmp_path)

    assert raised.value.exit_code is ExitCode.NO_VALID_SCRIPT
    assert str(raised.value).startswith("no valid PatchHarbor scripts found")


@pytest.mark.parametrize(
    "entry_type",
    (
        stat.S_IFLNK,
        stat.S_IFCHR,
        stat.S_IFBLK,
        stat.S_IFIFO,
        stat.S_IFSOCK,
    ),
    ids=("symlink", "character-device", "block-device", "fifo", "socket"),
)
def test_zip_rejects_links_and_special_entries_before_any_script_runs(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    entry_type: int,
) -> None:
    archive_path = tmp_path / "linked.zip"
    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.writestr("run.sh", f"{REQUIRED_MARKER}\n")
        special = zipfile.ZipInfo("special.bin")
        special.create_system = 3
        special.external_attr = (entry_type | 0o777) << 16
        archive.writestr(special, b"target")

    executed: list[str] = []
    monkeypatch.setattr(
        script_application,
        "execute_script_text",
        lambda script_text, **kwargs: executed.append(script_text) or 0,
    )

    with pytest.raises(PatchHarborError) as raised:
        _run_path(archive_path, tmp_path)

    assert raised.value.exit_code is ExitCode.SOURCE_ERROR
    assert "unsupported entry type" in str(raised.value)
    assert executed == []


def test_zip_rejects_directory_entries_with_content_before_execution(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    archive_path = tmp_path / "directory-content.zip"
    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.writestr("run.sh", f"{REQUIRED_MARKER}\n")
        archive.writestr("files/", b"not-empty")

    executed: list[str] = []
    monkeypatch.setattr(
        script_application,
        "execute_script_text",
        lambda script_text, **kwargs: executed.append(script_text) or 0,
    )

    with pytest.raises(PatchHarborError) as raised:
        _run_path(archive_path, tmp_path)

    assert raised.value.exit_code is ExitCode.SOURCE_ERROR
    assert executed == []


@pytest.mark.parametrize(
    "member_name",
    (
        "../escape.bin",
        "/absolute.bin",
        "folder\\payload.bin",
        "CON/data.bin",
        ".git/config",
        "files/.PATCHHARBOR/id",
        "folder/./payload.bin",
        "folder/\x1b-control.bin",
        f"{'a' * 129}/payload.bin",
    ),
)
def test_zip_rejects_unsafe_member_paths_before_execution(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    member_name: str,
) -> None:
    archive_path = tmp_path / "unsafe.zip"
    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.writestr("run.sh", f"{REQUIRED_MARKER}\n")
        archive.writestr("safe.bin", b"must-not-be-written")
        _write_raw_member_name(archive, member_name, b"payload")

    executed: list[str] = []
    monkeypatch.setattr(
        script_application,
        "execute_script_text",
        lambda script_text, **kwargs: executed.append(script_text) or 0,
    )

    with pytest.raises(PatchHarborError) as raised:
        _run_path(archive_path, tmp_path)

    assert raised.value.exit_code is ExitCode.SOURCE_ERROR
    assert "invalid PatchBundle" in str(raised.value)
    assert executed == []
    assert not (tmp_path / "safe.bin").exists()


def test_zip_rejects_original_backslash_name_after_host_normalization(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    archive_path = tmp_path / "normalized-unsafe.zip"
    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.writestr("run.sh", f"{REQUIRED_MARKER}\n")
        _write_raw_member_name(archive, r"folder\payload.bin", b"payload")

    real_infolist = zipfile.ZipFile.infolist

    def normalized_infolist(archive: zipfile.ZipFile) -> list[zipfile.ZipInfo]:
        entries = real_infolist(archive)
        for entry in entries:
            entry.filename = entry.filename.replace("\\", "/")
        return entries

    monkeypatch.setattr(zipfile.ZipFile, "infolist", normalized_infolist)

    with pytest.raises(PatchHarborError) as raised:
        _run_path(archive_path, tmp_path)

    assert raised.value.exit_code is ExitCode.SOURCE_ERROR
    assert "invalid PatchBundle" in str(raised.value)


@pytest.mark.parametrize(
    "member_names",
    (
        ("payload.bin", "payload.bin"),
        ("Payload.bin", "payload.bin"),
        ("Assets/one.bin", "assets/two.bin"),
        ("assets", "assets/two.bin"),
    ),
)
def test_zip_rejects_duplicate_and_ambiguous_member_trees(
    tmp_path: Path,
    member_names: tuple[str, str],
) -> None:
    archive_path = tmp_path / "ambiguous.zip"
    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.writestr("run.sh", f"{REQUIRED_MARKER}\n")
        archive.writestr(member_names[0], b"one")
        if member_names[0] == member_names[1]:
            with pytest.warns(UserWarning):
                archive.writestr(member_names[1], b"two")
        else:
            archive.writestr(member_names[1], b"two")

    with pytest.raises(PatchHarborError) as raised:
        _run_path(archive_path, tmp_path)

    assert raised.value.exit_code is ExitCode.SOURCE_ERROR
    assert "invalid PatchBundle" in str(raised.value)


def test_bundle_write_failure_prevents_every_script_execution(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    archive_path = tmp_path / "write-failure.zip"
    _write_zip(
        archive_path,
        [
            ("run.sh", f"{REQUIRED_MARKER}\n"),
            ("payload.txt", "payload"),
        ],
    )
    executed: list[str] = []

    def fail_payload_write(*args: object, **kwargs: object) -> None:
        raise PatchHarborError(
            "cannot write bundle file 'payload.txt': denied",
            ExitCode.PAYLOAD_PREPARATION_ERROR,
        )

    monkeypatch.setattr(
        script_application,
        "write_bundle_payloads",
        fail_payload_write,
    )
    monkeypatch.setattr(
        script_application,
        "execute_script_text",
        lambda script_text, **kwargs: executed.append(script_text) or 0,
    )

    with pytest.raises(PatchHarborError) as raised:
        _run_path(archive_path, tmp_path)

    assert raised.value.exit_code is ExitCode.PAYLOAD_PREPARATION_ERROR
    assert executed == []


@pytest.mark.parametrize(
    ("policy", "entries"),
    [
        (
            ResourcePolicy(
                warning_bytes=1,
                max_content_bytes=20,
                max_zip_total_bytes=40,
                max_zip_entries=1,
            ),
            [("one.txt", "1"), ("two.txt", "2")],
        ),
        (
            ResourcePolicy(
                warning_bytes=1,
                max_content_bytes=4,
                max_zip_total_bytes=8,
            ),
            [("large.txt", "12345")],
        ),
        (
            ResourcePolicy(
                warning_bytes=1,
                max_content_bytes=8,
                max_zip_total_bytes=8,
            ),
            [("one.txt", "12345"), ("two.txt", "67890")],
        ),
    ],
)
def test_zip_resource_budgets_fail_before_execution(
    tmp_path: Path,
    policy: ResourcePolicy,
    entries: list[tuple[str, str]],
) -> None:
    archive_path = tmp_path / "limited.zip"
    _write_zip(archive_path, entries)

    with pytest.raises(PatchHarborError) as raised:
        _run_path(archive_path, tmp_path, resource_policy=policy)

    assert raised.value.exit_code is ExitCode.SOURCE_ERROR
    assert "resource limit exceeded" in str(raised.value)


def test_zip_accepts_exact_entry_and_total_byte_boundaries(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    archive_path = tmp_path / "boundary.zip"
    script_text = f"{REQUIRED_MARKER}\n"
    payload = b"data"
    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.writestr("run.sh", script_text)
        archive.writestr("payload.bin", payload)

    script_size = len(script_text.encode("utf-8"))
    policy = ResourcePolicy(
        warning_bytes=script_size,
        max_content_bytes=script_size,
        max_zip_total_bytes=script_size + len(payload),
        max_zip_entries=2,
    )
    executed: list[str] = []
    monkeypatch.setattr(
        script_application,
        "execute_script_text",
        lambda script_text, **kwargs: executed.append(script_text) or 0,
    )

    result = _run_path(
        archive_path,
        tmp_path,
        resource_policy=policy,
    )

    assert result == 0
    assert executed == [script_text]
    assert (tmp_path / "payload.bin").read_bytes() == payload


@pytest.mark.parametrize(
    ("policy", "observed_payload", "error_fragment"),
    [
        (
            ResourcePolicy(
                warning_bytes=1,
                max_content_bytes=20,
                max_zip_total_bytes=100,
            ),
            b"x" * 21,
            "entry 'payload.bin' exceeds 20 bytes",
        ),
        (
            ResourcePolicy(
                warning_bytes=1,
                max_content_bytes=100,
                max_zip_total_bytes=20,
            ),
            b"x" * 10,
            "uncompressed data exceeds 20 bytes",
        ),
    ],
)
def test_zip_live_bytes_use_the_same_policy_as_preflight(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    policy: ResourcePolicy,
    observed_payload: bytes,
    error_fragment: str,
) -> None:
    archive_path = tmp_path / "misreported.zip"
    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.writestr("run.sh", f"{REQUIRED_MARKER}\n")
        archive.writestr("payload.bin", b"x")

    original_open = zip_payloads.zipfile.ZipFile.open

    def open_with_misreported_payload(
        archive: zipfile.ZipFile,
        member: str | zipfile.ZipInfo,
        mode: str = "r",
        pwd: bytes | None = None,
        *,
        force_zip64: bool = False,
    ) -> object:
        member_name = (
            member.filename if isinstance(member, zipfile.ZipInfo) else member
        )
        if member_name == "payload.bin":
            return BytesIO(observed_payload)
        return original_open(
            archive,
            member,
            mode,
            pwd,
            force_zip64=force_zip64,
        )

    monkeypatch.setattr(
        zip_payloads.zipfile.ZipFile,
        "open",
        open_with_misreported_payload,
    )
    executed: list[str] = []
    monkeypatch.setattr(
        script_application,
        "execute_script_text",
        lambda script_text, **kwargs: executed.append(script_text) or 0,
    )

    with pytest.raises(PatchHarborError) as raised:
        _run_path(archive_path, tmp_path, resource_policy=policy)

    assert raised.value.exit_code is ExitCode.SOURCE_ERROR
    assert error_fragment in str(raised.value)
    assert executed == []
    assert not (tmp_path / "payload.bin").exists()


def test_zip_large_entry_warning_is_preserved_on_bundle(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    archive_path = tmp_path / "large-entry.zip"
    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.writestr("run.sh", f"{REQUIRED_MARKER}\n")
        archive.writestr("payload.bin", b"x" * 21)
    policy = ResourcePolicy(
        warning_bytes=20,
        max_content_bytes=1024,
        max_zip_total_bytes=2048,
    )

    bundle = script_bundles.resolve_patch_bundle(
        file_input_artifact(archive_path),
        policy=policy,
    )

    assert bundle.warnings == (
        "input artifact is large (243 bytes)",
        "ZIP entry 'payload.bin' is large (21 bytes)",
    )


def test_compressed_zip_bomb_like_payload_is_rejected_before_execution(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    archive_path = tmp_path / "compressed-bomb.zip"
    expanded = b"A" * 4096
    with zipfile.ZipFile(
        archive_path,
        "w",
        compression=zipfile.ZIP_DEFLATED,
    ) as archive:
        archive.writestr("run.sh", f"{REQUIRED_MARKER}\n")
        archive.writestr("payload.bin", expanded)

    assert archive_path.stat().st_size < len(expanded)
    policy = ResourcePolicy(
        warning_bytes=1,
        max_content_bytes=8192,
        max_zip_total_bytes=1024,
    )
    executed: list[str] = []
    monkeypatch.setattr(
        script_application,
        "execute_script_text",
        lambda script_text, **kwargs: executed.append(script_text) or 0,
    )

    with pytest.raises(PatchHarborError) as raised:
        _run_path(
            archive_path,
            tmp_path,
            resource_policy=policy,
        )

    assert raised.value.exit_code is ExitCode.SOURCE_ERROR
    assert "resource limit exceeded" in str(raised.value)
    assert "uncompressed data" in str(raised.value)
    assert executed == []
    assert not (tmp_path / "payload.bin").exists()


def test_each_zip_script_receives_its_own_timeout(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    archive_path = tmp_path / "scripts.zip"
    _write_zip(
        archive_path,
        [
            ("first.sh", f"{REQUIRED_MARKER}\n"),
            ("second.sh", f"{REQUIRED_MARKER}\n"),
        ],
    )
    observed: list[tuple[str, float]] = []

    def fake_execute_script_text(
        script_text: str,
        *,
        cwd: Path,
        timeout_seconds: float,
        output: object | None = None,
    ) -> int:
        assert output is None
        observed.append((script_text, timeout_seconds))
        return 0

    monkeypatch.setattr(
        script_application, "execute_script_text", fake_execute_script_text
    )

    result = _run_path(archive_path, tmp_path, timeout_seconds=7.5)

    assert result == 0
    assert len(observed) == 2
    assert [timeout for _, timeout in observed] == [7.5, 7.5]


def test_zip_bundle_preserves_script_entry_names_for_presentation(
    tmp_path: Path,
) -> None:
    archive_path = tmp_path / "named-scripts.zip"
    _write_zip(
        archive_path,
        [
            ("scripts/first.sh", f"{REQUIRED_MARKER}\n"),
            ("scripts/second.ps1", f"{REQUIRED_MARKER}\n"),
        ],
    )

    bundle = script_bundles.resolve_patch_bundle(
        file_input_artifact(archive_path)
    )

    assert [script.display_name for script in bundle.scripts] == [
        "scripts/first.sh",
        "scripts/second.ps1",
    ]
