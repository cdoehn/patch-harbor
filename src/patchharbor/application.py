"""Application orchestration for one PatchHarbor runner request."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import ExitStack, contextmanager
from dataclasses import dataclass, replace
from pathlib import Path
import unicodedata
from typing import TextIO

from patchharbor.progress import activity

from patchharbor.apply_mutation import (
    ApplyMutationGate,
    MutationFailureKind,
    apply_payload_mutation,
)
from patchharbor.apply_preflight import prepare_patch_package
from patchharbor.apply_repository import (
    SafeResolvedRepository,
    safely_resolved_repository,
)
from patchharbor.archive_git import completed_commit_for_context
from patchharbor.archive_policy import validate_archive_directory
from patchharbor.exchange_archive import archive_exchange_artifacts
from patchharbor.exchange_recovery import recover_exchange_artifacts
from patchharbor.bundle_names import validate_bundle_suffix
from patchharbor.bundles import resolve_patch_bundle
from patchharbor.configuration import (
    UserConfiguration,
    load_configuration,
    load_configuration_if_present,
    prepare_exchange_directory,
    resolve_exchange_directory_candidate,
    revalidate_exchange_directory,
    write_prepared_configuration,
)
from patchharbor.errors import (
    ErrorKind,
    ExitCode,
    PatchHarborError,
    configuration_error,
    patch_package_error,
    registry_error,
    repository_resolution_error,
    state_mismatch_error,
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
    ExchangeApplyStatus,
    ExchangePatchSelection,
    mark_exchange_apply_finished,
    mark_exchange_apply_started,
    record_exchange_result_digest,
)
from patchharbor.exchange_paths import (
    ExchangePathPolicyError,
    require_exchange_outside_registry,
)
from patchharbor.execution import (
    DEFAULT_TIMEOUT_SECONDS,
    ScriptExecutionResult,
    execute_prepared_script_with_log,
    execute_script_text,
)
from patchharbor.identifier_presentation import shorten_identifier
from patchharbor.locks import registry_lock
from patchharbor.models import (
    BundleScript,
    GitObjectId,
    InputArtifact,
    RegistryListResult,
    RegistrySnapshot,
    RepositoryContext,
    RepositoryId,
    RepositoryPath,
)
from patchharbor.output import OutputTargets
from patchharbor.parser import parse_script
from patchharbor.patch_manifest import PatchManifest
from patchharbor.patch_package import (
    ValidatedPatchPackage,
    resolve_patch_package as _resolve_patch_package,
    validate_patch_package as _validate_patch_package,
)
from patchharbor.payload_files import (
    validate_bundle_payload_targets,
    write_bundle_payloads,
)
from patchharbor.presentation import ConsolePresentation, PresentedFile
from patchharbor.registration import (
    list_registered_repositories,
    register_local_repository,
    unregister_local_repository,
)
from patchharbor.registry import load_registry
from patchharbor.repository_state import (
    capture_consistent_repository_snapshot,
    repository_context_from_snapshot,
    capture_repository_context,
    capture_repository_context_for_id,
    require_clean_repository,
)
from patchharbor.resource_policy import DEFAULT_RESOURCE_POLICY, ResourcePolicy
from patchharbor.result_bundle import (
    ManualResultBundle,
    create_apply_result_bundle,
    create_manual_result_bundle,
)
from patchharbor.run_report import (
    ApplyPrimaryOutcome,
    RunReport,
    RunSession,
    unresolved_apply_report,
)
from patchharbor.sources import (
    DirectoryCandidate,
    file_input_artifact,
    list_directory_entries,
    select_directory_candidate,
    stdin_input_artifact,
)
from patchharbor.user_paths import (
    RegistrationUserPaths,
    configuration_user_paths,
)


def _require_exchange_configuration_allowed(
    exchange_directory: Path,
    registry_snapshot: RegistrySnapshot,
    *,
    exchange_must_exist: bool,
) -> None:
    try:
        require_exchange_outside_registry(
            exchange_directory,
            registry_snapshot,
            exchange_must_exist=exchange_must_exist,
        )
    except ExchangePathPolicyError as exc:
        raise configuration_error(str(exc)) from exc


def configure_exchange_directory(path: Path) -> tuple[Path, UserConfiguration]:
    """Persist one registry-safe shared exchange directory under the global lock."""
    paths = configuration_user_paths()
    candidate = resolve_exchange_directory_candidate(path)
    with registry_lock(paths):
        expected_registry = load_registry(paths)
        _require_exchange_configuration_allowed(
            candidate,
            expected_registry,
            exchange_must_exist=False,
        )
        configuration = prepare_exchange_directory(paths, path)
        _require_exchange_configuration_allowed(
            configuration.exchange_directory,
            expected_registry,
            exchange_must_exist=True,
        )

        current_registry = load_registry(paths)
        if current_registry != expected_registry:
            raise registry_error(
                "repository registry changed while configuring exchange directory"
            )
        configuration = revalidate_exchange_directory(configuration)
        _require_exchange_configuration_allowed(
            configuration.exchange_directory,
            current_registry,
            exchange_must_exist=True,
        )
        return (
            paths.configuration_path,
            write_prepared_configuration(paths, configuration),
        )


def configure_bundle_suffix(suffix: str) -> tuple[Path, UserConfiguration]:
    """Update only the suffix, under the shared registry/configuration lock."""
    try:
        suffix = validate_bundle_suffix(suffix)
    except ValueError as exc:
        raise configuration_error(str(exc)) from exc
    paths = configuration_user_paths()
    with registry_lock(paths):
        configuration = replace(load_configuration(paths), bundle_suffix=suffix)
        registry = load_registry(paths)
        _require_exchange_configuration_allowed(
            configuration.exchange_directory, registry, exchange_must_exist=True,
        )
        return paths.configuration_path, write_prepared_configuration(paths, configuration)


def configure_archive_directory(name: str) -> tuple[Path, UserConfiguration]:
    """Persist one archive child name using the existing shared config workflow."""
    try:
        name = validate_archive_directory(name)
    except ValueError as exc:
        raise configuration_error(str(exc)) from exc
    paths = configuration_user_paths()
    with registry_lock(paths):
        configuration = replace(load_configuration(paths), archive_directory=name)
        _require_exchange_configuration_allowed(
            configuration.exchange_directory, load_registry(paths), exchange_must_exist=True,
        )
        return paths.configuration_path, write_prepared_configuration(paths, configuration)


def shared_configuration() -> tuple[Path, UserConfiguration]:
    """Return the currently persisted shared user configuration."""
    paths = configuration_user_paths()
    return paths.configuration_path, load_configuration(paths)


def resolve_patch_package(
    path: Path,
    *,
    resource_policy: ResourcePolicy = DEFAULT_RESOURCE_POLICY,
) -> ValidatedPatchPackage:
    """Resolve one complete patch package through the package boundary."""
    return _resolve_patch_package(path, resource_policy=resource_policy)


def validate_patch_package(
    path: Path,
    *,
    resource_policy: ResourcePolicy = DEFAULT_RESOURCE_POLICY,
) -> PatchManifest:
    """Validate one complete patch package through the package boundary."""
    return _validate_patch_package(path, resource_policy=resource_policy)


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
    configuration: UserConfiguration
    retry_failed: bool = False
    explicitly_selected: bool = False

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
            current_configuration = revalidate_exchange_directory(
                load_configuration(self.paths)
            )
            if current_configuration != self.configuration:
                raise configuration_error(
                    "exchange directory changed before repository mutation"
                )
            require_exchange_identity_unchanged(
                self.artifact.identity,
                directory=self.configuration.exchange_directory,
            )

        activity("REPLAY", f"Record attempted run {shorten_identifier(run_id)} before mutation")
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
        activity("RECEIPT", f"Pin Result SHA-256 {shorten_identifier(digest)} "
                 f"for run {shorten_identifier(run_id)} before publication")
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
    expected_configuration: UserConfiguration,
    expected_registry: RegistrySnapshot,
) -> None:
    current_configuration = revalidate_exchange_directory(
        load_configuration(paths)
    )
    if current_configuration != expected_configuration:
        raise configuration_error(
            "exchange directory changed during automatic patch discovery"
        )
    with registry_lock(paths):
        current_registry = load_registry(paths)
        if current_registry != expected_registry:
            raise registry_error(
                "repository registry changed during automatic patch discovery"
            )
        _require_exchange_configuration_allowed(
            current_configuration.exchange_directory,
            current_registry,
            exchange_must_exist=True,
        )


@dataclass(frozen=True, slots=True)
class ExchangeDiscoveryScope:
    """Repository and retry boundaries for one parameterless Apply."""

    repository_context: RepositoryContext | None
    allow_failed_retry: bool

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


def _automatic_exchange_discovery_scope() -> ExchangeDiscoveryScope:
    """Keep watcher-triggered parameterless Apply global and non-retrying."""
    return ExchangeDiscoveryScope(
        repository_context=None,
        allow_failed_retry=False,
    )


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
    configuration = revalidate_exchange_directory(load_configuration(paths))
    with registry_lock(paths):
        registry = load_registry(paths)
        _require_exchange_configuration_allowed(
            configuration.exchange_directory,
            registry,
            exchange_must_exist=True,
        )

    try:
        artifacts = scan_exchange_directory(
            configuration.exchange_directory,
            paths=paths,
        )
    except ExchangeScanError as exc:
        raise configuration_error("cannot scan exchange directory") from exc

    if archive:
        artifacts = recover_exchange_artifacts(
            artifacts, configuration=configuration, paths=paths,
            repository_id=(scope.repository_context.repo_id if scope.repository_context else None),
        )
        maintenance = archive_exchange_artifacts(
            artifacts, configuration=configuration, paths=paths,
            repository_id=(scope.repository_context.repo_id if scope.repository_context else None),
        )
        artifacts = maintenance.remaining
        if output is not None:
            output.write_warnings(maintenance.warnings)

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
        context = _context_for_exchange_candidate(selection, scope, contexts)
        if context is None:
            activity("SKIP", f"{artifact.path.name}: repository outside scope or unavailable", "detail")
            continue
        if not selection.matches_context(context):
            activity("SKIP", f"{artifact.path.name}: repository state does not match "
                     f"(expected base {shorten_identifier(selection.base_commit)}, "
                     f"state {shorten_identifier(selection.state_fingerprint)}; "
                     f"actual base {shorten_identifier(context.base_commit)}, "
                     f"state {shorten_identifier(context.state_fingerprint)})", "detail")
            continue
        if artifact.apply_status is not None and not (
            scope.allow_failed_retry
            and artifact.apply_status is ExchangeApplyStatus.FAILED
        ):
            activity("SKIP", f"{artifact.path.name}: replay status {artifact.apply_status.value} blocks this origin", "detail")
            continue
        activity("MATCH", f"{artifact.path.name}: eligible, mtime_ns={artifact.mtime_ns}", "success")
        matches.append(artifact)

    _revalidate_exchange_discovery(paths, configuration, registry)

    if not matches:
        activity("SELECT", "No eligible patch remains after content, scope, state and replay checks", "warning")
        message = (
            "no state-bound patch package matches the current registered "
            "repository"
            if scope.is_repository_scoped
            else "no state-bound patch package matches a registered repository"
        )
        raise patch_package_error(message)

    artifact = _select_exchange_candidate(matches)
    activity("SELECT", f"Selected newest eligible patch: {artifact.path.name} "
             f"from {len(matches)} match(es); mtime_ns={artifact.mtime_ns}", "success")
    package = materialize_exchange_patch(
        artifact,
        directory=configuration.exchange_directory,
    )
    _revalidate_exchange_discovery(paths, configuration, registry)
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
        retry_failed=(artifact.apply_status is ExchangeApplyStatus.FAILED),
    )


def _maintain_explicit_exchange(
    package: ValidatedPatchPackage, path: Path, *, output: OutputTargets | None,
) -> DiscoveredExchangePatch | None:
    """Maintain this explicit target's scope without ever archiving the chosen ZIP.

    Track direct Exchange packages in the same lifecycle ledger, but an explicit
    path remains a deliberate selection and bypasses automatic retry filtering.
    No configuration/scan is required for packages outside Exchange.
    """
    try:
        paths = configuration_user_paths()
        configuration = load_configuration_if_present(paths)
        if configuration is None:
            return None
        with registry_lock(paths):
            _require_exchange_configuration_allowed(
                configuration.exchange_directory, load_registry(paths), exchange_must_exist=True,
            )
        selected = path.resolve(strict=True)
        artifacts = scan_exchange_directory(configuration.exchange_directory, paths=paths)
        artifacts = recover_exchange_artifacts(
            artifacts, configuration=configuration, paths=paths,
            repository_id=package.manifest.repo_id,
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
                return DiscoveredExchangePatch(artifact, package, paths, configuration,
                                               explicitly_selected=True)
    except (PatchHarborError, ExchangeScanError, OSError, ValueError):
        # Optional maintenance must not impose discovery on the explicit API.
        pass
    return None


def _maintain_bundle_exchange(path: Path) -> None:
    """Archive only this registered repository before creating a fresh bundle."""
    try:
        paths = configuration_user_paths()
        configuration = load_configuration_if_present(paths)
        if configuration is None:
            return
        context = capture_repository_context(path)
        with registry_lock(paths):
            _require_exchange_configuration_allowed(
                configuration.exchange_directory, load_registry(paths), exchange_must_exist=True,
            )
        artifacts = scan_exchange_directory(configuration.exchange_directory, paths=paths)
        artifacts = recover_exchange_artifacts(
            artifacts, configuration=configuration, paths=paths, repository_id=context.repo_id,
        )
        archive_exchange_artifacts(artifacts, configuration=configuration, paths=paths,
                                   repository_id=context.repo_id)
    except (PatchHarborError, ExchangeScanError, OSError, ValueError):
        pass


def _complete_apply_result_bundle(
    resolved: SafeResolvedRepository,
    package: ValidatedPatchPackage,
    *,
    session: RunSession,
    dry_run: bool,
    warnings: tuple[str, ...],
    primary_outcome: ApplyPrimaryOutcome,
    execution_log: bytes | None = None,
    actual_context: RepositoryContext | None = None,
    before_result_publication: Callable[[str], None] | None = None,
) -> RunReport:
    activity("BUNDLE", "Capture and publish the current Apply Result Bundle", "heading")
    return create_apply_result_bundle(
        resolved.repository,
        resolved.repo_id,
        resolved.registry_snapshot,
        actual_context if actual_context is not None else resolved.context,
        package.manifest,
        target=resolved.result_target,
        publication=resolved.result_publication,
        warnings=warnings,
        session=session,
        dry_run=dry_run,
        primary_outcome=primary_outcome,
        execution_log=execution_log,
        package_sha256=package.package_sha256,
        before_publish=before_result_publication,
    )


def _complete_mutation_result_bundle(
    mutation_gate: ApplyMutationGate,
    *,
    primary_outcome: ApplyPrimaryOutcome,
    execution_log: bytes | None = None,
    actual_context: RepositoryContext | None = None,
    before_result_publication: Callable[[str], None] | None = None,
) -> RunReport:
    """Complete one apply result from the single checked mutation gate."""
    return _complete_apply_result_bundle(
        mutation_gate.resolved,
        mutation_gate.package,
        session=mutation_gate.session,
        dry_run=mutation_gate.dry_run,
        warnings=mutation_gate.warnings,
        primary_outcome=primary_outcome,
        execution_log=execution_log,
        actual_context=actual_context,
        before_result_publication=before_result_publication,
    )


@contextmanager
def preflight_patch_package_repository(
    package: ValidatedPatchPackage,
    *,
    output_directory: Path | None = None,
    session: RunSession | None = None,
    dry_run: bool = True,
    output: OutputTargets | None = None,
    presentation: ConsolePresentation | None = None,
    before_mutation: Callable[[], None] | None = None,
) -> Iterator[ApplyMutationGate]:
    """Yield the explicit mutation gate while private inputs and locks live."""
    actual_session = session or RunSession.start()
    manifest = package.manifest
    with ExitStack() as repository_scope:
        try:
            resolved = repository_scope.enter_context(
                safely_resolved_repository(
                    manifest,
                    session=actual_session,
                    output_directory=output_directory,
                )
            )
        except PatchHarborError as error:
            report = unresolved_apply_report(
                session=actual_session,
                dry_run=dry_run,
                warnings=package.warnings,
                error=error,
            )
            raise report.reported_error() from error

        if presentation is not None:
            presentation.update_repository(
                repository_name=str(resolved.repository),
                repository_context=(
                    f"repo_id: {shorten_identifier(resolved.repo_id)} · "
                    f"base: {shorten_identifier(resolved.context.base_commit)} · "
                    f"state: {shorten_identifier(resolved.context.state_fingerprint)}"
                ),
            )

        activity("BINDING", f"Compare full manifest binding: base {shorten_identifier(manifest.base_commit)}, "
                 f"state {shorten_identifier(manifest.state_fingerprint)}")
        if not resolved.matches_manifest_state(manifest):
            activity("BINDING", "Manifest and repository state differ; mutation refused", "error")
            error = state_mismatch_error(
                "patch package does not match the resolved repository state"
            )
            report = _complete_apply_result_bundle(
                resolved,
                package,
                session=actual_session,
                dry_run=dry_run,
                warnings=package.warnings,
                primary_outcome=ApplyPrimaryOutcome.from_tool_error(error),
            )
            raise report.reported_error()

        activity("BINDING", "Repository binding matches", "success")
        with ExitStack() as private_resources:
            try:
                prepared_package = private_resources.enter_context(
                    prepare_patch_package(
                        package,
                        repository=resolved.repository.value,
                    )
                )
                validate_bundle_payload_targets(
                    prepared_package.payloads,
                    cwd=resolved.repository.value,
                )
            except PatchHarborError as error:
                report = _complete_apply_result_bundle(
                    resolved,
                    package,
                    session=actual_session,
                    dry_run=dry_run,
                    warnings=package.warnings,
                    primary_outcome=ApplyPrimaryOutcome.from_tool_error(error),
                )
                raise report.reported_error() from error

            if output is not None:
                output.write_warnings(prepared_package.warnings)

            if presentation is not None:
                presentation.begin_script(
                    script_name=package.entrypoint.relative_path,
                    script_index=1,
                    script_total=1,
                    messages=tuple(
                        (message.name, message.text)
                        for message in prepared_package.entrypoint.script.messages
                    ),
                    warnings=prepared_package.warnings,
                )

            yield ApplyMutationGate(
                session=actual_session,
                resolved=resolved,
                package=package,
                prepared_package=prepared_package,
                dry_run=dry_run,
                before_mutation=before_mutation,
            )


def dry_run_patch_package(
    package: ValidatedPatchPackage,
    *,
    output_directory: Path | None = None,
    output: OutputTargets | None = None,
    session: RunSession | None = None,
    presentation: ConsolePresentation | None = None,
) -> RunReport:
    """Complete one safe dry-run and publish its unchanged Result Bundle."""
    actual_session = session or RunSession.start()
    with preflight_patch_package_repository(
        package,
        output_directory=output_directory,
        session=actual_session,
        dry_run=True,
        output=output,
        presentation=presentation,
    ) as mutation_gate:
        activity("DRY-RUN", "Validation complete; no payload write or entrypoint execution", "success")
        report = _complete_mutation_result_bundle(
            mutation_gate,
            primary_outcome=ApplyPrimaryOutcome.dry_run_success(),
        )
        if report.process_exit_code != 0:
            raise report.reported_error()
        return report


def _publish_attempt_outcome(
    mutation_gate: ApplyMutationGate,
    publisher: Callable[[bool, GitObjectId | None], None] | None,
    *,
    succeeded: bool,
    execution_log: bytes | None = None,
    actual_context: RepositoryContext | None = None,
    completed_report: RunReport | None = None,
) -> None:
    """Persist one automatic outcome or complete it as a PatchHarbor failure."""
    if publisher is None:
        return
    try:
        completed_commit = None
        if succeeded:
            # This optional receipt must never turn execution success into a
            # claim that a commit exists when state/history capture is unclear.
            try:
                resolved = mutation_gate.resolved
                after = repository_context_from_snapshot(
                    resolved.repository, resolved.repo_id,
                    capture_consistent_repository_snapshot(resolved.repository),
                )
                completed_commit = completed_commit_for_context(resolved.context, after)
            except (PatchHarborError, OSError, ValueError):
                pass
        publisher(succeeded, completed_commit)
    except PatchHarborError as error:
        if completed_report is not None:
            # The successful execution bundle is already published and pinned.
            # Do not overwrite it or attempt another bundle with the same name.
            report = RunReport.completed_apply(
                timing=completed_report.timing, dry_run=completed_report.dry_run,
                context=completed_report.context, repository=completed_report.repository,
                repo_id=completed_report.repo_id, warnings=completed_report.warnings,
                primary_outcome=ApplyPrimaryOutcome.from_tool_error(error),
                result_bundle=completed_report.result_bundle,
            )
        else:
            report = _complete_mutation_result_bundle(
                mutation_gate,
                primary_outcome=ApplyPrimaryOutcome.from_tool_error(error),
                execution_log=execution_log,
                actual_context=actual_context,
            )
        raise report.reported_error() from error


def _require_payload_mutation(
    mutation_gate: ApplyMutationGate,
    *,
    publish_attempt_outcome: Callable[[bool, GitObjectId | None], None] | None = None,
) -> None:
    """Complete a failed mutation as the primary apply result."""
    try:
        result = apply_payload_mutation(mutation_gate)
    except PatchHarborError as error:
        report = _complete_mutation_result_bundle(
            mutation_gate,
            primary_outcome=ApplyPrimaryOutcome.from_tool_error(error),
        )
        raise report.reported_error() from error

    if result.success:
        return
    if result.failure_kind is not MutationFailureKind.STATE_MISMATCH:
        _publish_attempt_outcome(
            mutation_gate,
            publish_attempt_outcome,
            succeeded=False,
            actual_context=result.context,
        )
    error = result.error
    if error is None:
        raise RuntimeError("failed mutation result has no error")
    report = _complete_mutation_result_bundle(
        mutation_gate,
        primary_outcome=ApplyPrimaryOutcome.from_tool_error(error),
        actual_context=result.context,
    )
    raise report.reported_error()


def _complete_entrypoint_execution(
    mutation_gate: ApplyMutationGate,
    execution: ScriptExecutionResult,
    *,
    publish_attempt_outcome: Callable[[bool, GitObjectId | None], None] | None = None,
    before_result_publication: Callable[[str], None] | None = None,
) -> RunReport:
    """Publish one execution result before unwinding the shared apply scope."""
    primary_outcome = ApplyPrimaryOutcome.from_execution_result(
        entrypoint_started=execution.entrypoint_started,
        entrypoint_exit_code=execution.entrypoint_exit_code,
        patchharbor_error=execution.patchharbor_error,
    )
    report = _complete_mutation_result_bundle(
        mutation_gate,
        primary_outcome=primary_outcome,
        execution_log=(execution.output if execution.entrypoint_started else None),
        before_result_publication=before_result_publication,
    )
    _publish_attempt_outcome(
        mutation_gate,
        publish_attempt_outcome,
        succeeded=primary_outcome.result.success,
        execution_log=(execution.output if execution.entrypoint_started else None),
        completed_report=report,
    )

    if execution.patchharbor_error is not None:
        raise report.reported_error()
    if primary_outcome.result.success and report.process_exit_code != 0:
        raise report.reported_error()
    return report


def apply_patch_package(
    package: ValidatedPatchPackage,
    *,
    output_directory: Path | None = None,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    output: OutputTargets | None = None,
    session: RunSession | None = None,
    presentation: ConsolePresentation | None = None,
    before_mutation: Callable[[], None] | None = None,
    publish_attempt_outcome: Callable[[bool, GitObjectId | None], None] | None = None,
    before_result_publication: Callable[[str], None] | None = None,
) -> RunReport:
    """Write one validated package, run its private entrypoint, and bundle it."""
    actual_session = session or RunSession.start()
    with preflight_patch_package_repository(
        package,
        output_directory=output_directory,
        session=actual_session,
        dry_run=False,
        output=output,
        presentation=presentation,
        before_mutation=before_mutation,
    ) as mutation_gate:
        _require_payload_mutation(
            mutation_gate,
            publish_attempt_outcome=publish_attempt_outcome,
        )
        prepared_package = mutation_gate.prepared_package
        execution = execute_prepared_script_with_log(
            prepared_package.entrypoint.path,
            interpreter=prepared_package.entrypoint.interpreter,
            cwd=mutation_gate.resolved.repository.value,
            timeout_seconds=timeout_seconds,
            execution_log_path=prepared_package.execution_log_path,
            output=output,
        )
        return _complete_entrypoint_execution(
            mutation_gate,
            execution,
            publish_attempt_outcome=publish_attempt_outcome,
            before_result_publication=before_result_publication,
        )


def run_apply_path(
    path: Path | None,
    *,
    dry_run: bool,
    output_directory: Path | None = None,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    output: OutputTargets | None = None,
    session: RunSession | None = None,
    presentation: ConsolePresentation | None = None,
    automatic: bool = False,
) -> RunReport:
    """Run one Apply request through a single public application boundary."""
    actual_session = session or RunSession.start()
    try:
        discovered: DiscoveredExchangePatch | None = None
        if path is None:
            scope = (
                _automatic_exchange_discovery_scope()
                if automatic
                else _manual_exchange_discovery_scope(Path.cwd())
            )
            discovered = discover_exchange_patch(scope, archive=not dry_run, output=output)
            selected_path = discovered.artifact.path
            package = discovered.package
        else:
            selected_path = path
            package = resolve_patch_package(selected_path)
            if not dry_run:
                discovered = _maintain_explicit_exchange(package, selected_path, output=output)
    except PatchHarborError as error:
        return unresolved_apply_report(
            session=actual_session,
            dry_run=dry_run,
            error=error,
        )

    if presentation is not None:
        presentation.begin_request(
            source_name=str(selected_path),
            repository_name="resolving…",
            repository_context=(
                f"repo_id: {shorten_identifier(package.manifest.repo_id)}"
            ),
            bundle_files=(
                PresentedFile(
                    name=package.entrypoint.relative_path,
                    size_bytes=len(package.entrypoint.content),
                    kind="entrypoint",
                ),
                *(
                    PresentedFile(
                        name=payload.relative_path,
                        size_bytes=len(payload.content),
                        kind="payload",
                    )
                    for payload in package.payloads
                ),
            ),
            script_total=1,
            warnings=package.warnings,
        )
    if output is not None:
        output.write_warnings(package.warnings)

    try:
        if dry_run:
            return dry_run_patch_package(
                package,
                output_directory=output_directory,
                output=output,
                session=actual_session,
                presentation=presentation,
            )
        return apply_patch_package(
            package,
            output_directory=output_directory,
            timeout_seconds=timeout_seconds,
            output=output,
            session=actual_session,
            presentation=presentation,
            before_mutation=(
                (lambda: discovered.publish_attempt(str(actual_session.run_id)))
                if discovered is not None
                else None
            ),
            before_result_publication=(
                (lambda digest: discovered.publish_result_digest(str(actual_session.run_id), digest))
                if discovered is not None else None
            ),
            publish_attempt_outcome=(
                (lambda succeeded, commit: discovered.publish_outcome(
                    succeeded, commit, run_id=str(actual_session.run_id),
                ))
                if discovered is not None
                else None
            ),
        )
    except PatchHarborError as error:
        report = error.run_report
        if isinstance(report, RunReport):
            return report
        return unresolved_apply_report(
            session=actual_session,
            dry_run=dry_run,
            warnings=package.warnings,
            error=error,
        )


def register_repository(
    path: Path,
    *,
    new_id: bool = False,
) -> RepositoryContext:
    """Register one local Git repository and return its current context."""
    repository = require_clean_repository(path)
    _repo_id, repository_path = register_local_repository(
        repository.value,
        new_id=new_id,
    )
    return capture_repository_context(repository_path.value)


def repository_context(path: Path) -> RepositoryContext:
    """Return the current reproducible context of one registered repository."""
    return capture_repository_context(path)


def bundle_repository(
    path: Path,
    *,
    output_directory: Path | None = None,
) -> ManualResultBundle:
    """Create one manual Result Bundle for a registered repository."""
    _maintain_bundle_exchange(path)
    return create_manual_result_bundle(
        path,
        output_directory=output_directory,
    )


def registered_repositories() -> RegistryListResult:
    """Return one structured view of all registered local instances."""
    return list_registered_repositories()


def unregister_repository(
    selector: str,
    *,
    cwd: Path,
) -> tuple[RepositoryId, RepositoryPath]:
    """Remove one central repository mapping."""
    return unregister_local_repository(selector, cwd=cwd)


def _execute_bundle_script(
    bundle_script: BundleScript,
    *,
    script_index: int,
    script_total: int,
    cwd: Path,
    timeout_seconds: float,
    output: OutputTargets | None = None,
    presentation: ConsolePresentation | None = None,
) -> int:
    parsed_script = parse_script(bundle_script.text)
    script_warnings = parsed_script.warnings
    if presentation is not None:
        presentation.begin_script(
            script_name=bundle_script.display_name,
            script_index=script_index,
            script_total=script_total,
            messages=tuple(
                (message.name, message.text)
                for message in parsed_script.messages
            ),
            warnings=script_warnings,
        )
    if output is not None:
        output.write_warnings(script_warnings)
    return execute_script_text(
        parsed_script.text,
        cwd=cwd,
        timeout_seconds=timeout_seconds,
        output=output,
    )


def run_input_artifact(
    artifact: InputArtifact,
    *,
    cwd: Path,
    timeout_seconds: float,
    output: OutputTargets | None = None,
    presentation: ConsolePresentation | None = None,
    resource_policy: ResourcePolicy = DEFAULT_RESOURCE_POLICY,
) -> int:
    """Resolve and execute every script in one input artifact."""
    bundle = resolve_patch_bundle(artifact, policy=resource_policy)
    if presentation is not None:
        presentation.begin_request(
            source_name=artifact.display_name,
            bundle_files=tuple(
                PresentedFile(
                    name=payload.relative_path,
                    size_bytes=len(payload.content),
                    kind="bundle",
                )
                for payload in bundle.payloads
            ),
            script_total=len(bundle.scripts),
            warnings=bundle.warnings,
        )
    if output is not None:
        output.write_warnings(bundle.warnings)
    write_bundle_payloads(bundle.payloads, cwd=cwd)
    last_exit_code = 0
    script_total = len(bundle.scripts)
    for script_index, bundle_script in enumerate(bundle.scripts, start=1):
        last_exit_code = _execute_bundle_script(
            bundle_script,
            script_index=script_index,
            script_total=script_total,
            cwd=cwd,
            timeout_seconds=timeout_seconds,
            output=output,
            presentation=presentation,
        )
        if last_exit_code != 0:
            return last_exit_code
    return last_exit_code


def run_standard_input(
    stream: TextIO,
    *,
    cwd: Path,
    timeout_seconds: float,
    output: OutputTargets | None = None,
    presentation: ConsolePresentation | None = None,
    resource_policy: ResourcePolicy = DEFAULT_RESOURCE_POLICY,
) -> int:
    """Own the temporary stdin artifact for exactly one runner request."""
    with stdin_input_artifact(stream, policy=resource_policy) as artifact:
        return run_input_artifact(
            artifact,
            cwd=cwd,
            timeout_seconds=timeout_seconds,
            output=output,
            presentation=presentation,
            resource_policy=resource_policy,
        )


def _is_directory_candidate(
    path: Path,
    resource_policy: ResourcePolicy,
) -> bool:
    try:
        resolve_patch_bundle(
            file_input_artifact(path),
            policy=resource_policy,
        )
        activity("SELECT", f"Manual input candidate is executable: {path.name}", "success")
        return True
    except PatchHarborError as exc:
        activity("SKIP", f"{path.name}: not a valid manual input ({exc})", "detail")
        return False


def discover_directory_candidates(
    directory: Path,
    *,
    resource_policy: ResourcePolicy = DEFAULT_RESOURCE_POLICY,
) -> tuple[DirectoryCandidate, ...]:
    """Return sorted regular files that resolve to a PatchBundle."""
    return tuple(
        candidate
        for candidate in list_directory_entries(directory)
        if _is_directory_candidate(candidate.path, resource_policy)
    )


def _run_selected_candidate(
    candidate: DirectoryCandidate,
    *,
    cwd: Path,
    timeout_seconds: float,
    output: OutputTargets | None = None,
    presentation: ConsolePresentation | None = None,
    resource_policy: ResourcePolicy = DEFAULT_RESOURCE_POLICY,
) -> int:
    if candidate.path.is_symlink() or not candidate.path.is_file():
        raise PatchHarborError(
            f"selected script is no longer available: {candidate.display_name}",
            ExitCode.SOURCE_ERROR,
        )

    return run_input_artifact(
        file_input_artifact(candidate.path),
        cwd=cwd,
        timeout_seconds=timeout_seconds,
        output=output,
        presentation=presentation,
        resource_policy=resource_policy,
    )


def run_script_path(
    path: Path,
    *,
    cwd: Path,
    timeout_seconds: float,
    selection_input: TextIO,
    selection_output: TextIO,
    output: OutputTargets | None = None,
    presentation: ConsolePresentation | None = None,
    resource_policy: ResourcePolicy = DEFAULT_RESOURCE_POLICY,
) -> int:
    """Run a script/ZIP file or select one from a directory."""
    if not path.is_dir():
        return run_input_artifact(
            file_input_artifact(path),
            cwd=cwd,
            timeout_seconds=timeout_seconds,
            output=output,
            presentation=presentation,
            resource_policy=resource_policy,
        )

    candidates = discover_directory_candidates(
        path,
        resource_policy=resource_policy,
    )
    if not candidates:
        raise PatchHarborError(
            f"no PatchHarbor scripts found in directory {path}",
            ExitCode.NO_VALID_SCRIPT,
        )
    selected = select_directory_candidate(
        candidates,
        input_stream=selection_input,
        output_stream=selection_output,
    )
    return _run_selected_candidate(
        selected,
        cwd=cwd,
        timeout_seconds=timeout_seconds,
        output=output,
        presentation=presentation,
        resource_policy=resource_policy,
    )
