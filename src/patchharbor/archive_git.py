"""Read-only original-history proofs for Exchange archival, never age heuristics."""

from __future__ import annotations

from pathlib import Path

from patchharbor.archive_evidence import ArchiveEvidence
from patchharbor.exchange_state import ExchangeApplyStatus, ExchangeStateRecord
from patchharbor.git_commands import run_git_bytes
from patchharbor.git_objects import parse_base_tree_entries
from patchharbor.models import GitObjectId, RepositoryContext, RepositoryPath
from patchharbor.platform.filesystem import PathKind, path_kind


def require_original_history(repository: RepositoryPath) -> None:
    """Refuse incomplete/rewritten ancestry views instead of inferring consumption."""
    def query(*arguments: str) -> bytes:
        return run_git_bytes("--no-replace-objects", *arguments, cwd=repository.value)

    if query("rev-parse", "--is-shallow-repository").strip() != b"false":
        raise ValueError("shallow history is not an archival proof")
    if query("for-each-ref", "--format=%(refname)", "refs/replace/").strip():
        raise ValueError("replacement objects are not an archival proof")
    graft_path = Path(query("rev-parse", "--git-path", "info/grafts").decode("utf-8").strip())
    if not graft_path.is_absolute():
        graft_path = repository.value / graft_path
    if path_kind(graft_path) is not PathKind.MISSING:
        raise ValueError("grafted history is not an archival proof")


def is_ancestor(repository: RepositoryPath, ancestor: GitObjectId, descendant: GitObjectId) -> bool:
    """Prove full-ID ancestry; unknown objects/errors are not negative evidence."""
    if ancestor.object_format != descendant.object_format:
        return False
    for commit in dict.fromkeys((ancestor, descendant)):
        if run_git_bytes("--no-replace-objects", "cat-file", "-t", str(commit),
                         cwd=repository.value).strip() != b"commit":
            return False
    # A merge base equal to ancestor proves ancestry. Return code 1 (no common
    # ancestor) has no stdout; every other Git failure propagates to fail-safe.
    bases = run_git_bytes(
        "--no-replace-objects", "merge-base", "--all", str(ancestor), str(descendant),
        cwd=repository.value, accepted_returncodes=(0, 1),
    ).splitlines()
    return bases == [str(ancestor).encode("ascii")]


def completed_commit_for_context(
    before: RepositoryContext, after: RepositoryContext,
) -> GitObjectId | None:
    """Record only a clean, successful forward transition in the existing ledger."""
    if (
        before.repo_id != after.repo_id
        or before.repository_path != after.repository_path
        or before.base_commit == after.base_commit
        or after.dirty
    ):
        return None
    require_original_history(after.repository_path)
    return after.base_commit if is_ancestor(
        after.repository_path, before.base_commit, after.base_commit,
    ) else None


def is_proven_obsolete(
    evidence: ArchiveEvidence,
    context: RepositoryContext,
    record: ExchangeStateRecord | None,
) -> bool:
    """Use only this repository's full binding, success receipt and actual Git DAG."""
    selection = evidence.selection
    if context.dirty or selection.repo_id != context.repo_id:
        return False
    # Cheap negative decisions keep files in place. They need no Git proof.
    if evidence.kind == "patch_package":
        if (
            record is None or record.kind != evidence.kind
            or record.manifest != selection
            or record.apply_status is not ExchangeApplyStatus.SUCCEEDED
            or record.completed_commit is None
            or selection.base_commit == record.completed_commit
        ):
            return False
        require_original_history(context.repository_path)
        return (
            is_ancestor(context.repository_path, selection.base_commit, record.completed_commit)
            and is_ancestor(context.repository_path, record.completed_commit, context.base_commit)
        )
    if evidence.kind != "result_bundle" or selection.base_commit == context.base_commit:
        return False
    return is_proven_result_state(evidence, context)


def is_proven_result_state(evidence: ArchiveEvidence, context: RepositoryContext) -> bool:
    """Validate the complete result tree against original Git, including HEAD."""
    selection = evidence.selection
    if evidence.kind != "result_bundle" or context.dirty or selection.repo_id != context.repo_id:
        return False
    require_original_history(context.repository_path)
    if not is_ancestor(context.repository_path, selection.base_commit, context.base_commit):
        return False
    tree = parse_base_tree_entries(
        run_git_bytes("--no-replace-objects", "ls-tree", "-r", "-z", "--full-tree",
                      str(selection.base_commit), cwd=context.repository_path.value),
        selection.base_commit.object_format,
    )
    observed = tuple(sorted(
        (entry.path.decoded, entry.mode.decode("ascii"), str(entry.object_id)) for entry in tree
    ))
    return observed == evidence.base_entries
