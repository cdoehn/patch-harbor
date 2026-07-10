from __future__ import annotations

from pathlib import Path
from typing import Iterable, Mapping

from patchharbor.public_audit import (
    PublicAuditFinding,
    PublicAuditModelError,
    PublicAuditPattern,
    PublicAuditResult,
    PublicAuditTarget,
    public_audit_pattern_index,
)


class PublicAuditCheckError(ValueError):
    pass


def is_probably_binary(raw: bytes, *, sample_size: int = 4096) -> bool:
    if not isinstance(raw, bytes):
        raise PublicAuditCheckError("public audit binary check requires bytes")
    if not isinstance(sample_size, int) or sample_size < 1:
        raise PublicAuditCheckError("public audit binary sample_size must be a positive integer")
    return b"\0" in raw[:sample_size]


def scan_public_audit_text(
    path: str,
    text: str,
    patterns: Iterable[PublicAuditPattern | Mapping[str, object]],
    *,
    target_type: str = "text",
    label: str | None = None,
    metadata_mode: str = "text",
) -> PublicAuditResult:
    if not isinstance(text, str):
        raise PublicAuditCheckError("public audit text scan requires text")
    target = PublicAuditTarget(path, target_type=target_type, label=label)
    normalized_patterns = tuple(public_audit_pattern_index(patterns).values())
    findings: list[PublicAuditFinding] = []

    for line_number, line in enumerate(text.splitlines(), start=1):
        for pattern in normalized_patterns:
            column = line.find(pattern.value)
            if column >= 0:
                findings.append(
                    PublicAuditFinding(
                        target=target,
                        pattern=pattern,
                        line=line_number,
                        column=column + 1,
                        text=line.strip() or line,
                    )
                )

    return PublicAuditResult(tuple(findings), scanned_targets=1, metadata={"mode": metadata_mode})


def scan_public_audit_bytes(
    path: str,
    raw: bytes,
    patterns: Iterable[PublicAuditPattern | Mapping[str, object]],
    *,
    target_type: str = "text",
    label: str | None = None,
    encoding: str = "utf-8",
) -> PublicAuditResult:
    if not isinstance(raw, bytes):
        raise PublicAuditCheckError("public audit bytes scan requires bytes")
    if not isinstance(encoding, str) or not encoding:
        raise PublicAuditCheckError("public audit encoding must be a non-empty string")
    if is_probably_binary(raw):
        return PublicAuditResult(
            (),
            scanned_targets=0,
            skipped_targets=1,
            metadata={"mode": "bytes", "skip_reason": "binary"},
        )
    text = raw.decode(encoding, errors="replace")
    return scan_public_audit_text(
        path,
        text,
        patterns,
        target_type=target_type,
        label=label,
        metadata_mode="bytes",
    )


def scan_public_audit_file(
    base_path: Path | str,
    target: PublicAuditTarget | Mapping[str, object],
    patterns: Iterable[PublicAuditPattern | Mapping[str, object]],
    *,
    encoding: str = "utf-8",
) -> PublicAuditResult:
    base = _base_path(base_path)
    normalized_target = _target_from(target)
    file_path = base / normalized_target.path

    if not file_path.exists() or not file_path.is_file():
        return PublicAuditResult(
            (),
            scanned_targets=0,
            skipped_targets=1,
            metadata={"mode": "file", "skip_reason": "missing"},
        )

    raw = file_path.read_bytes()
    result = scan_public_audit_bytes(
        normalized_target.path,
        raw,
        patterns,
        target_type=normalized_target.target_type,
        label=normalized_target.label,
        encoding=encoding,
    )
    if result.skipped_targets:
        return PublicAuditResult(
            result.findings,
            scanned_targets=0,
            skipped_targets=1,
            metadata={"mode": "file", "skip_reason": "binary"},
        )
    return PublicAuditResult(result.findings, scanned_targets=1, metadata={"mode": "file"})


def scan_public_audit_targets(
    base_path: Path | str,
    targets: Iterable[PublicAuditTarget | Mapping[str, object]],
    patterns: Iterable[PublicAuditPattern | Mapping[str, object]],
    *,
    encoding: str = "utf-8",
) -> PublicAuditResult:
    if isinstance(targets, (str, bytes, bytearray)):
        raise PublicAuditCheckError("public audit targets must be an iterable of targets")
    base = _base_path(base_path)
    normalized_targets = tuple(_target_from(target) for target in targets)
    normalized_patterns = tuple(public_audit_pattern_index(patterns).values())

    findings: list[PublicAuditFinding] = []
    scanned_targets = 0
    skipped_targets = 0
    for target in normalized_targets:
        result = scan_public_audit_file(base, target, normalized_patterns, encoding=encoding)
        findings.extend(result.findings)
        scanned_targets += result.scanned_targets
        skipped_targets += result.skipped_targets

    return PublicAuditResult(
        tuple(findings),
        scanned_targets=scanned_targets,
        skipped_targets=skipped_targets,
        metadata={"mode": "targets"},
    )


def _base_path(value: Path | str) -> Path:
    if not isinstance(value, (str, Path)):
        raise PublicAuditCheckError("public audit base path must be a path-like value")
    return Path(value)


def _target_from(value: PublicAuditTarget | Mapping[str, object]) -> PublicAuditTarget:
    if isinstance(value, PublicAuditTarget):
        return value
    if isinstance(value, Mapping):
        return PublicAuditTarget.from_mapping(value)
    raise PublicAuditCheckError("public audit target must be PublicAuditTarget or mapping")
