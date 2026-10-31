"""Configured Exchange targets, scoped discovery and attempt receipts.

The API and watcher share these workflows; neither performs separate discovery.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import stat
import unicodedata

from patchharbor.progress import activity
from patchharbor.exchange_archive import archive_exchange_artifacts
from patchharbor.exchange_recovery import recover_exchange_artifacts
from patchharbor.configuration import (
    RepositoryConfiguration,
    RepositoryConfigurationPaths,
    load_configuration,
    revalidate_exchange_directory,
)
from patchharbor.configuration_context import (
    configuration_paths_for_id,
    configuration_paths_for_repository,
)
from patchharbor.errors import (
    ErrorKind,
    FailureReason,
    PatchHarborError,
    LockBusyError,
    NoEligiblePatchError,
    configuration_error,
    patch_package_error,
    registry_error,
    repository_resolution_error,
)
from patchharbor.exchange import (
    ExchangeArtifact,
    ExchangeArtifactKind,
    ExchangeScanError,
    materialize_exchange_patch,
    require_exchange_identity_unchanged,
    scan_exchange_directory,
)
from patchharbor.exchange_state import (
    _state_lock,
    ExchangeApplyStatus,
    ExchangePatchSelection,
    mark_exchange_apply_finished,
    mark_exchange_apply_started,
    record_exchange_result_digest,
)
from patchharbor.locks import registry_lock, repository_lock
from patchharbor.models import (
    GitObjectId,
    RegistrySnapshot,
    RegistryStatus,
    RepositoryContext,
    RepositoryId,
)
from patchharbor.output import OutputTargets
from patchharbor.patch_manifest import PatchManifest
from patchharbor.patch_package import ValidatedPatchPackage
from patchharbor.registry import load_registry
from patchharbor.repository import registered_repository_status
from patchharbor.repository_state import (
    capture_repository_context,
    capture_repository_context_for_id,
)
from patchharbor.user_paths import (
    RegistrationUserPaths,
    configuration_user_paths,
    registration_user_paths,
)
from patchharbor.watch_contract import (
    ApplyLock,
    ApplyLockKind,
    ApplyReadiness,
    ExchangeWatchTarget,
    WatchControlPaths,
    WatchTargets,
)
from patchharbor.application_configuration import (
    _require_exchange_configuration_allowed,
)


def _manifest_matches_context(
    manifest: PatchManifest,
    context: RepositoryContext,
) -> bool:
    return (
        manifest.repo_id == context.repo_id
        and manifest.base_commit == context.base_commit
        and manifest.fingerprint_algorithm == context.fingerprint_algorithm
        and manifest.state_fingerprint == context.state_fingerprint
    )


@dataclass(frozen=True, slots=True)
class DiscoveredExchangePatch:
    """One selected package plus its persistent attempt boundary."""

    artifact: ExchangeArtifact
    package: ValidatedPatchPackage
    paths: RegistrationUserPaths
    configuration: RepositoryConfiguration
    configuration_paths: RepositoryConfigurationPaths
    retry_failed: bool = False
    explicitly_selected: bool = False
    watch_target: ExchangeWatchTarget | None = None

    def __post_init__(self) -> None:
        if self.artifact.selection is None:
            raise ValueError("discovered Exchange patch requires selection data")
        expected_status = (
            ExchangeApplyStatus.FAILED if self.retry_failed else None
        )
        if not self.explicitly_selected and self.artifact.apply_status is not expected_status:
            raise ValueError(
                "discovered Exchange patch has an ineligible apply status"
            )
        if (
            self.artifact.selection
            != ExchangePatchSelection.from_manifest(self.package.manifest)
        ):
            raise ValueError("discovered Exchange package changed after selection")

    def publish_attempt(self, run_id: str | None = None) -> None:
        """Consume this identity immediately before repository mutation."""
        selection = self.artifact.selection
        if selection is None:
            raise RuntimeError("discovered Exchange patch lost selection data")

        def verify_identity() -> None:
            if self.watch_target is not None:
                _require_watch_target_unchanged(self.watch_target)
            current_configuration = revalidate_exchange_directory(
                load_configuration(self.configuration_paths)
            )
            if current_configuration != self.configuration:
                raise configuration_error(
                    "exchange directory changed before repository mutation"
                )
            require_exchange_identity_unchanged(
                self.artifact.identity,
                directory=self.configuration.exchange_directory,
            )
            if self.watch_target is not None:
                _require_watch_target_unchanged(self.watch_target)

        activity("REPLAY", f"Record attempted run {str(run_id)} before mutation", identifiers=(str(run_id),))
        mark_exchange_apply_started(
            self.paths,
            self.artifact.identity,
            selection,
            verify_identity=verify_identity,
            retry_failed=self.retry_failed,
            explicitly_selected=self.explicitly_selected,
            run_id=run_id,
        )

    def publish_result_digest(self, run_id: str, digest: str) -> None:
        """Persist a byte-exact result receipt before its final publication."""
        assert self.artifact.selection is not None
        activity("RECEIPT", f"Pin Result SHA-256 {str(digest)} "
                 f"for run {str(run_id)} before publication", identifiers=(str(digest), str(run_id),))
        record_exchange_result_digest(
            self.paths, self.artifact.identity, self.artifact.selection,
            run_id=run_id, result_sha256=digest,
        )

    def publish_outcome(self, succeeded: bool, completed_commit: GitObjectId | None = None,
                        *, run_id: str | None = None) -> None:
        """Persist the known terminal result of this started automatic apply."""
        selection = self.artifact.selection
        if selection is None:
            raise RuntimeError("discovered Exchange patch lost selection data")
        activity("REPLAY", f"Record terminal attempt outcome: {'succeeded' if succeeded else 'failed'}")
        mark_exchange_apply_finished(
            self.paths,
            self.artifact.identity,
            selection,
            (
                ExchangeApplyStatus.SUCCEEDED
                if succeeded
                else ExchangeApplyStatus.FAILED
            ),
            completed_commit=completed_commit,
            run_id=run_id,
        )


def _revalidate_exchange_discovery(
    paths: RegistrationUserPaths,
    expected_settings: dict[RepositoryId, tuple[RepositoryConfigurationPaths, RepositoryConfiguration]],
    expected_registry: RegistrySnapshot,
) -> None:
    with registry_lock(paths):
        current_registry = load_registry(paths)
        if current_registry != expected_registry:
            raise registry_error("repository registry changed during automatic patch discovery")
        for repo_id, (local, expected) in expected_settings.items():
            if configuration_paths_for_id(repo_id, current_registry) != local:
                raise repository_resolution_error("repository identity changed during discovery")
            current = revalidate_exchange_directory(load_configuration(local))
            if current != expected:
                raise configuration_error("repository configuration changed during automatic patch discovery")
            _require_exchange_configuration_allowed(
                current.exchange_directory, current_registry, exchange_must_exist=True,
            )


@dataclass(frozen=True, slots=True)
class ExchangeDiscoveryScope:
    """Repository and retry boundaries for one parameterless Apply."""

    repository_context: RepositoryContext | None
    allow_failed_retry: bool
    exchanges: tuple[ExchangeWatchTarget, ...] | None = None

    @property
    def is_repository_scoped(self) -> bool:
        """Whether candidates are restricted to one pre-resolved repository."""
        return self.repository_context is not None


def _manual_exchange_discovery_scope(
    current_directory: Path,
) -> ExchangeDiscoveryScope:
    """Resolve manual parameterless Apply to the current registered repository."""
    try:
        context = capture_repository_context(current_directory)
    except PatchHarborError as exc:
        if exc.error_kind is ErrorKind.REPOSITORY_RESOLUTION_ERROR:
            raise repository_resolution_error(
                "current directory is not inside a uniquely registered "
                "PatchHarbor repository"
            ) from exc
        raise
    return ExchangeDiscoveryScope(
        repository_context=context,
        allow_failed_retry=True,
    )


def _automatic_exchange_discovery_scope(
    exchanges: tuple[ExchangeWatchTarget, ...] | None = None,
) -> ExchangeDiscoveryScope:
    """Keep automatic Apply non-retrying, optionally limited to observed roots."""
    return ExchangeDiscoveryScope(
        repository_context=None,
        allow_failed_retry=False,
        exchanges=exchanges,
    )


def _watch_target(directory: Path, repository_ids: tuple[RepositoryId, ...]) -> ExchangeWatchTarget:
    """Observe directory identity without listing it or reading any bundles."""
    try:
        before = directory.stat(follow_symlinks=False)
        physical = directory.resolve(strict=True)
        after = directory.stat(follow_symlinks=False)
        if (physical != directory or not stat.S_ISDIR(before.st_mode)
                or not stat.S_ISDIR(after.st_mode) or not before.st_ino
                or (before.st_dev, before.st_ino) != (after.st_dev, after.st_ino)):
            raise configuration_error("exchange watch directory identity is unstable")
    except (OSError, RuntimeError) as exc:
        raise configuration_error(f"cannot observe exchange watch directory: {directory}") from exc
    return ExchangeWatchTarget(directory, before.st_dev, before.st_ino, repository_ids)


def _require_watch_target_unchanged(target: ExchangeWatchTarget) -> None:
    if _watch_target(target.directory, target.repository_ids) != target:
        raise configuration_error("exchange watch directory identity changed")


def _exchange_settings(
    registry: RegistrySnapshot, scope: ExchangeDiscoveryScope,
) -> tuple[
    dict[RepositoryId, tuple[RepositoryConfigurationPaths, RepositoryConfiguration]],
    dict[Path, ExchangeWatchTarget],
]:
    """Resolve and validate configuration before any Exchange scan/maintenance."""
    settings: dict[RepositoryId, tuple[RepositoryConfigurationPaths, RepositoryConfiguration]] = {}
    groups: dict[Path, list[RepositoryId]] = {}
    for mapping in registry.repositories:
        scoped = scope.repository_context
        if scoped is not None and mapping.repo_id != scoped.repo_id:
            continue
        if scoped is None and registered_repository_status(
            mapping.repository_path, mapping.repo_id,
        ) is RegistryStatus.MISSING:
            continue
        local = configuration_paths_for_id(mapping.repo_id, registry)
        configuration = load_configuration(local)
        if configuration.exchange_directory is None and scoped is None:
            continue
        revalidate_exchange_directory(configuration)
        _require_exchange_configuration_allowed(
            configuration.exchange_directory, registry, exchange_must_exist=True,
        )
        settings[mapping.repo_id] = local, configuration
        groups.setdefault(configuration.exchange_directory, []).append(mapping.repo_id)
    if scope.repository_context is not None and scope.repository_context.repo_id not in settings:
        raise repository_resolution_error("current repository is no longer registered")
    targets = {
        directory: _watch_target(directory, tuple(sorted(ids)))
        for directory, ids in sorted(groups.items(), key=lambda item: str(item[0]))
    }
    if scope.exchanges is not None:
        if scope.is_repository_scoped or scope.allow_failed_retry:
            raise configuration_error("watch scope is only valid for automatic Apply")
        # Explicit empty scope stays empty. Supplied snapshots are restrictions,
        # never trusted permissions; aliases/fabricated/stale observations fail.
        for target in scope.exchanges:
            if targets.get(target.directory) != target:
                raise configuration_error("exchange watch target is foreign or stale")
        allowed = {target.directory for target in scope.exchanges}
        targets = {path: target for path, target in targets.items() if path in allowed}
        settings = {repo_id: pair for repo_id, pair in settings.items()
                    if pair[1].exchange_directory in allowed}
    return settings, targets


def _watch_control_paths(paths: RegistrationUserPaths, registry: RegistrySnapshot) -> WatchControlPaths:
    # Advisory restoration paths only. A missing Exchange cannot be an approved
    # WatchTarget, but its nearest existing parent can reveal its return. Broken
    # settings still fail watch_targets()/Apply; they are never repaired here.
    exchanges = set()
    for mapping in registry.repositories:
        try:
            local = configuration_paths_for_id(mapping.repo_id, registry)
            settings = load_configuration(local, validate_directory=False)
        except PatchHarborError:
            continue
        if settings.exchange_directory is not None:
            exchanges.add(settings.exchange_directory)
    return WatchControlPaths(
        paths.registry_path,
        tuple(sorted({mapping.repository_path.value / ".patchharbor" / "config.json"
                      for mapping in registry.repositories}, key=str)),
        tuple(sorted(exchanges, key=str)),
    )


def watch_control_paths() -> WatchControlPaths:
    """Resolve control paths from registry even if local configuration is broken."""
    paths = registration_user_paths(create_configuration_directory=False)
    with registry_lock(paths):
        return _watch_control_paths(paths, load_registry(paths))


def watch_targets() -> WatchTargets:
    """Return validated physical roots, with no bundle discovery or state capture."""
    paths = registration_user_paths(create_configuration_directory=False)
    with registry_lock(paths):
        registry = load_registry(paths)
        _, targets = _exchange_settings(registry, _automatic_exchange_discovery_scope())
        controls = _watch_control_paths(paths, registry)
        return WatchTargets(tuple(targets.values()), controls.registry_path, controls.configuration_paths)


def apply_readiness(lock: ApplyLock) -> ApplyReadiness:
    """Probe only the named technical lock; no candidate work or reservation."""
    paths = registration_user_paths(create_configuration_directory=False)
    try:
        if lock.kind is ApplyLockKind.EXCHANGE_STATE:
            with _state_lock(paths):
                pass
        else:
            with registry_lock(paths):
                if lock.kind is ApplyLockKind.REPOSITORY:
                    registry = load_registry(paths)
                    if not any(mapping.repo_id == lock.repo_id for mapping in registry.repositories):
                        raise repository_resolution_error("lock repository is no longer registered")
                    with repository_lock(paths, lock.repo_id):
                        pass
    except LockBusyError as exc:
        return ApplyReadiness(blocked_on=exc.lock)
    return ApplyReadiness()


def _candidate_filename_key(artifact: ExchangeArtifact) -> tuple[str, str]:
    """Return one deterministic Unicode-normalized filename tie-break key."""
    filename = artifact.path.name
    return unicodedata.normalize("NFC", filename), filename


def _select_exchange_candidate(
    matches: list[ExchangeArtifact],
) -> ExchangeArtifact:
    """Select newest mtime_ns, then the lexicographically first filename."""
    return min(
        matches,
        key=lambda artifact: (
            -artifact.mtime_ns,
            *_candidate_filename_key(artifact),
            str(artifact.path),
        ),
    )


def _context_for_exchange_candidate(
    selection: ExchangePatchSelection,
    scope: ExchangeDiscoveryScope,
    contexts: dict[RepositoryId, RepositoryContext | None],
) -> RepositoryContext | None:
    """Resolve one candidate inside the requested repository scope."""
    scoped_context = scope.repository_context
    if scoped_context is not None:
        if selection.repo_id != scoped_context.repo_id:
            return None
        return scoped_context

    repo_id = selection.repo_id
    if repo_id not in contexts:
        contexts[repo_id] = capture_repository_context_for_id(repo_id)
    return contexts[repo_id]


def discover_exchange_patch(
    scope: ExchangeDiscoveryScope,
    *,
    archive: bool = True,
    output: OutputTargets | None = None,
) -> DiscoveredExchangePatch:
    """Return the newest eligible package inside one selection scope."""
    activity("DISCOVER", "Load Exchange configuration and repository registry", "heading")
    paths = configuration_user_paths()
    with registry_lock(paths):
        registry = load_registry(paths)
        settings, targets = _exchange_settings(registry, scope)

    found: list[ExchangeArtifact] = []
    # Shared physical paths are scanned once. Maintenance is still strictly per repo.
    for directory, target in targets.items():
        _require_watch_target_unchanged(target)
        try:
            artifacts = scan_exchange_directory(directory, paths=paths)
        except ExchangeScanError as exc:
            raise configuration_error(f"cannot scan exchange directory: {directory}") from exc
        _require_watch_target_unchanged(target)
        if archive:
            for repo_id in target.repository_ids:
                _require_watch_target_unchanged(target)
                local, configuration = settings[repo_id]
                artifacts = recover_exchange_artifacts(
                    artifacts, configuration=configuration, paths=paths, repository_id=repo_id,
                )
                maintenance = archive_exchange_artifacts(
                    artifacts, configuration=configuration, paths=paths, repository_id=repo_id,
                )
                artifacts = maintenance.remaining
                if output is not None:
                    output.write_warnings(maintenance.warnings)
        found.extend(artifacts)
    artifacts = tuple(found)

    matches: list[ExchangeArtifact] = []
    contexts: dict[RepositoryId, RepositoryContext | None] = {}
    if scope.repository_context is not None:
        contexts[scope.repository_context.repo_id] = scope.repository_context
    for artifact in artifacts:
        activity("SELECT", f"Evaluate candidate: {artifact.path.name}")
        if artifact.kind is not ExchangeArtifactKind.PATCH_PACKAGE:
            activity("SKIP", f"{artifact.path.name}: {artifact.kind.value}, not a patch", "detail")
            continue
        selection = artifact.selection
        if selection is None:
            raise RuntimeError("Patch Package artifact has no selection data")
        target_settings = settings.get(selection.repo_id)
        if target_settings is None or artifact.path.parent != target_settings[1].exchange_directory:
            activity("SKIP", f"{artifact.path.name}: not in its repository's configured Exchange", "detail")
            continue
        context = _context_for_exchange_candidate(selection, scope, contexts)
        if context is None:
            activity("SKIP", f"{artifact.path.name}: repository outside scope or unavailable", "detail")
            continue
        if not selection.matches_context(context):
            activity("SKIP", f"{artifact.path.name}: repository state does not match "
                     f"(expected base {str(selection.base_commit)}, "
                     f"state {str(selection.state_fingerprint)}; "
                     f"actual base {str(context.base_commit)}, "
                     f"state {str(context.state_fingerprint)})", "detail", identifiers=(str(selection.base_commit), str(selection.state_fingerprint), str(context.base_commit), str(context.state_fingerprint),))
            continue
        if artifact.apply_status is not None and not (
            scope.allow_failed_retry
            and artifact.apply_status is ExchangeApplyStatus.FAILED
        ):
            activity("SKIP", f"{artifact.path.name}: replay status {artifact.apply_status.value} blocks this origin", "detail")
            continue
        activity("MATCH", f"{artifact.path.name}: eligible, mtime_ns={artifact.mtime_ns}", "success")
        matches.append(artifact)

    _revalidate_exchange_discovery(paths, settings, registry)
    for target in targets.values():
        _require_watch_target_unchanged(target)

    if not matches:
        activity("SELECT", "No eligible patch remains after content, scope, state and replay checks", "warning")
        message = (
            "no state-bound patch package matches the current registered "
            "repository"
            if scope.is_repository_scoped
            else "no state-bound patch package matches a registered repository"
        )
        if not scope.is_repository_scoped:
            raise NoEligiblePatchError(
                message, FailureReason.PATCH_PACKAGE_ERROR, error_kind=ErrorKind.PATCH_PACKAGE_ERROR,
            )
        raise patch_package_error(message)

    artifact = _select_exchange_candidate(matches)
    activity("SELECT", f"Selected newest eligible patch: {artifact.path.name} "
             f"from {len(matches)} match(es); mtime_ns={artifact.mtime_ns}", "success")
    assert artifact.selection is not None
    local, configuration = settings[artifact.selection.repo_id]
    package = materialize_exchange_patch(
        artifact, directory=configuration.exchange_directory,
    )
    _revalidate_exchange_discovery(paths, settings, registry)
    target = targets[configuration.exchange_directory]
    _require_watch_target_unchanged(target)
    context = contexts.get(package.manifest.repo_id)
    if context is None or not _manifest_matches_context(package.manifest, context):
        raise patch_package_error(
            "selected exchange patch changed during automatic discovery"
        )
    return DiscoveredExchangePatch(
        artifact=artifact,
        package=package,
        paths=paths,
        configuration=configuration,
        configuration_paths=local,
        retry_failed=(artifact.apply_status is ExchangeApplyStatus.FAILED),
        watch_target=target,
    )


def _maintain_explicit_exchange(
    package: ValidatedPatchPackage, path: Path, *, output: OutputTargets | None,
) -> DiscoveredExchangePatch | None:
    """Optional maintenance for the manifest's repository, never for the CWD."""
    try:
        paths = configuration_user_paths()
        with registry_lock(paths):
            registry = load_registry(paths)
            local = configuration_paths_for_id(package.manifest.repo_id, registry)
            configuration = load_configuration(local)
            if configuration.exchange_directory is None:
                return None
            _require_exchange_configuration_allowed(
                configuration.exchange_directory, registry, exchange_must_exist=True,
            )
        selected = path.resolve(strict=True)
        artifacts = scan_exchange_directory(configuration.exchange_directory, paths=paths)
        artifacts = recover_exchange_artifacts(
            artifacts, configuration=configuration, paths=paths, repository_id=package.manifest.repo_id,
        )
        maintenance = archive_exchange_artifacts(
            artifacts, configuration=configuration, paths=paths,
            repository_id=package.manifest.repo_id, excluded_paths=frozenset({selected}),
        )
        if output is not None:
            output.write_warnings(maintenance.warnings)
        for artifact in maintenance.remaining:
            if artifact.path == selected and artifact.selection == ExchangePatchSelection.from_manifest(package.manifest):
                materialized = materialize_exchange_patch(artifact, directory=configuration.exchange_directory)
                if materialized != package:
                    return None
                return DiscoveredExchangePatch(
                    artifact, package, paths, configuration, local, explicitly_selected=True,
                )
    except (PatchHarborError, ExchangeScanError, OSError, ValueError):
        # Mandatory config validation happens in the target preflight; never bypass it.
        pass
    return None


def _maintain_bundle_exchange(path: Path) -> None:
    """Maintain only the selected repository before creating its Result Bundle."""
    try:
        paths = configuration_user_paths()
        with registry_lock(paths):
            registry = load_registry(paths)
            local = configuration_paths_for_repository(path, registry)
            configuration = load_configuration(local)
            if configuration.exchange_directory is None:
                return
            _require_exchange_configuration_allowed(
                configuration.exchange_directory, registry, exchange_must_exist=True,
            )
        artifacts = scan_exchange_directory(configuration.exchange_directory, paths=paths)
        artifacts = recover_exchange_artifacts(
            artifacts, configuration=configuration, paths=paths, repository_id=local.repo_id,
        )
        archive_exchange_artifacts(
            artifacts, configuration=configuration, paths=paths, repository_id=local.repo_id,
        )
    except (PatchHarborError, ExchangeScanError, OSError, ValueError):
        pass
