"""Shared exchange fixtures and behavior probes."""
from __future__ import annotations

from hashlib import sha256
import json
import os
from pathlib import Path
import zipfile

from patchharbor.patch_manifest import PATCH_FORMAT_VERSION, PATCH_MARKER
from patchharbor.state_fingerprint import FINGERPRINT_ALGORITHM
from patchharbor.exchange_state import ExchangeFileIdentity, ExchangePatchSelection, ExchangeStateRecord
from patchharbor.models import GitObjectFormat, GitObjectId, RepositoryId

from tests.platform_support import native_script, native_value, run_cli
from tests.registration_support import exchange_state_path, isolated_user_environment


def _configure_user(tmp_path: Path) -> tuple[dict[str, str], Path]:
    environment = isolated_user_environment(tmp_path / "user")
    exchange = tmp_path / "exchange"
    exchange.mkdir(parents=True, exist_ok=True)
    return environment, exchange.resolve()


def _register_context(
    repository: Path,
    environment: dict[str, str],
) -> dict[str, object]:
    registered = run_cli(
        repository,
        "register",
        environment_overrides=environment,
    )
    assert registered.returncode == 0
    user_root = Path(environment["APPDATA"] if os.name == "nt" else environment["XDG_CONFIG_HOME"]).parent
    configured = run_cli(
        repository, "configure", "exchange-directory", str(user_root.parent / "exchange"),
        environment_overrides=environment,
    )
    assert configured.returncode == 0, configured.stderr

    completed = run_cli(
        repository,
        "context",
        "--json",
        environment_overrides=environment,
    )
    assert completed.returncode == 0
    result = json.loads(completed.stdout)["result"]
    assert isinstance(result, dict)
    return result


def _manifest(context: dict[str, object]) -> dict[str, object]:
    return {
        "marker": PATCH_MARKER,
        "format_version": PATCH_FORMAT_VERSION,
        "repo_id": context["repo_id"],
        "base_commit": context["base_commit"],
        "state_fingerprint": context["state_fingerprint"],
        "fingerprint_algorithm": FINGERPRINT_ALGORITHM,
        "entrypoint": native_value("run.sh", "run.ps1"),
    }


def _write_package(
    path: Path,
    context: dict[str, object],
    *,
    result_text: str = "selected",
) -> None:
    entrypoint_name = native_value("run.sh", "run.ps1")
    entrypoint = native_script(
        f"printf {result_text} > automatic-result.txt",
        (
            "[System.IO.File]::WriteAllText("
            f"'automatic-result.txt', '{result_text}')"
        ),
    )
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr(
            "patch.json",
            json.dumps(
                _manifest(context),
                ensure_ascii=False,
                allow_nan=False,
                separators=(",", ":"),
            ).encode("utf-8"),
        )
        archive.writestr(entrypoint_name, entrypoint.encode("utf-8"))
        archive.writestr("files/generated.bin", b"payload")


def _write_custom_package(
    path: Path,
    context: dict[str, object],
    *,
    posix_entrypoint: str,
    powershell_entrypoint: str,
    payloads: dict[str, bytes] | None = None,
) -> None:
    entrypoint_name = native_value("run.sh", "run.ps1")
    entrypoint = native_script(posix_entrypoint, powershell_entrypoint)
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr(
            "patch.json",
            json.dumps(
                _manifest(context),
                ensure_ascii=False,
                allow_nan=False,
                separators=(",", ":"),
            ).encode("utf-8"),
        )
        archive.writestr(entrypoint_name, entrypoint.encode("utf-8"))
        for relative_path, content in (payloads or {}).items():
            archive.writestr(relative_path, content)


def _exchange_records(environment: dict[str, str]) -> list[dict[str, object]]:
    document = json.loads(
        exchange_state_path(environment).read_text(encoding="utf-8")
    )
    assert document["format_version"] == 4
    records = document["entries"]
    assert isinstance(records, list)
    return records


def _identity_record(
    environment: dict[str, str],
    path: Path,
    content_hash: str | None = None,
) -> dict[str, object]:
    expected_hash = content_hash or sha256(path.read_bytes()).hexdigest()
    matches = [
        record
        for record in _exchange_records(environment)
        if record["path"] == str(path.resolve())
        and record["sha256"] == expected_hash
    ]
    assert len(matches) == 1
    return matches[0]


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
