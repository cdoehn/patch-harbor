"""Human and JSON representations of one immutable repository context."""

from __future__ import annotations

from typing import TextIO

from patchharbor.models import RepositoryContext


def write_context_block(context: RepositoryContext, stream: TextIO) -> None:
    """Write the copyable human representation of *context*."""
    print("PATCH_HARBOR_CONTEXT", file=stream)
    print(file=stream)
    print(f"repo_id: {context.repo_id}", file=stream)
    print(f"base_commit: {context.base_commit}", file=stream)
    print(f"dirty: {str(context.dirty).lower()}", file=stream)
    print(f"state_fingerprint: {context.state_fingerprint}", file=stream)
    print(f"fingerprint_algorithm: {context.fingerprint_algorithm}", file=stream)
    print(file=stream)
    print("INSTRUCTIONS:", file=stream)
    print("- Verwende diese Werte unverändert in patch.json.", file=stream)
    print(
        "- Erzeuge bei geändertem Repository-Zustand einen neuen Kontext.",
        file=stream,
    )


def context_json_result(context: RepositoryContext) -> dict[str, object]:
    """Return the closed machine-readable result representation."""
    return {
        "repo_id": str(context.repo_id),
        "repository_path": str(context.repository_path),
        "base_commit": str(context.base_commit),
        "dirty": context.dirty,
        "state_fingerprint": context.state_fingerprint,
        "fingerprint_algorithm": context.fingerprint_algorithm,
    }
