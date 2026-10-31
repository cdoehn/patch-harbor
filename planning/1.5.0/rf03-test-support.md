# RF-03: Zuordnung der gemeinsam verwendeten Testhilfen

Basis: bestätigtes Bundle 058, Commit `f959ea054c37977650be43db690909c2d510f29d`.

88 direkte `from tests.test_*`-Importstellen und ein zusätzlicher Modulalias
werden auf fachliche Supportmodule umgestellt. 66 Definitionen werden
verschoben bzw. als explizite gemeinsame Prüflogik herausgelöst; 14 neue
Supportmodule ergänzen zwei bestehende. Kein universelles Hilfsframework.

Testnamen, Parameter, Marker und Fixture-Scopes bleiben erhalten.
Die Windows-ACL-Prüflogik nimmt den Core- bzw. Bootstrap-Adapter explizit
entgegen. Beide ursprünglichen parametrisierten Tests bleiben bestehen.
Damit entfällt das Umschalten eines fremden Testmoduls per Monkeypatch.

Alle übrigen Testfunktionskörper bleiben nach reiner Importumleitung
strukturell identisch. Quellcode, Tools, Skripte, CI-Konfiguration und
eingefrorene Fixtures sind bytegleich zur Basis. Die vollständige parallele
Suite prüft den Zustand; ihre Collection wird vollständig mit Bundle 058
verglichen. Kein Test entfällt und keine neue Testkennung ist vorgesehen.

## Definitionen und Zielmodule

| Ursprung | Definitionen | Ziel |
| --- | --- | --- |
| `tests/test_api_e2e.py` | `write_package` | `tests/apply_support.py` |
| `tests/test_archive_maintenance.py` | `_inputs` | `tests/archive_support.py` |
| `tests/test_captured_reference.py` | `_reference` | `tests/pack_support.py` |
| `tests/test_docker_integration_runner.py` | `ENVIRONMENT_CHECK`, `_environment_check_module` | `tests/runner_support.py` |
| `tests/test_exchange_archive_e2e.py` | `ARCHIVE`, `_world`, `_bundle`, `_advance`, `_scan`, `_committing_patch`, `_rewrite` | `tests/archive_support.py` |
| `tests/test_exchange_e2e.py` | `_configure_user`, `_register_context`, `_manifest`, `_write_package`, `_write_custom_package`, `_exchange_records`, `_identity_record` | `tests/exchange_support.py` |
| `tests/test_exchange_recovery_e2e.py` | `_CRASH`, `_crash`, `_pending`, `_result`, `_edit_record` | `tests/recovery_support.py` |
| `tests/test_exchange_state.py` | `_identity`, `_selection`, `_record` | `tests/exchange_support.py` |
| `tests/test_pack_api.py` | `request_files`, `pack` | `tests/pack_support.py` |
| `tests/test_pack_sources.py` | `SCRIPT` | `tests/pack_support.py` |
| `tests/test_patch_inspection.py` | `MANIFEST`, `SCRIPT`, `write_package` | `tests/patch_inspection_support.py` |
| `tests/test_python_compat.py` | `test_private_windows_creation_never_uses_permissive_acl_on_failure` | `tests/windows_creation_support.py` |
| `tests/test_python_variants.py` | `result_file` | `tests/pyz_variant_support.py` |
| `tests/test_pyz_resources.py` | `provider_for` | `tests/runtime_pyz_support.py` |
| `tests/test_pyz_result_e2e.py` | `installed_producer` | `tests/runtime_installation_support.py` |
| `tests/test_reference_validation.py` | `reference_entries`, `write_reference`, `bound_package`, `edit_document` | `tests/reference_support.py` |
| `tests/test_result_bundle_publication.py` | `_publish` | `tests/result_publication_support.py` |
| `tests/test_result_format2.py` | `canonical` | `tests/legacy_runtime_support.py` |
| `tests/test_result_format3.py` | `canonical`, `format3` | `tests/result_pyz_support.py` |
| `tests/test_result_robustness.py` | `legacy_source` | `tests/legacy_runtime_support.py` |
| `tests/test_result_runtime_writer.py` | `repository`, `package` | `tests/apply_support.py` |
| `tests/test_result_runtime_writer.py` | `artifact` | `tests/result_pyz_support.py` |
| `tests/test_result_verification.py` | `destination`, `sleeps` | `tests/result_publication_support.py` |
| `tests/test_runtime_artifact.py` | `prepared`, `_recipe`, `_capture`, `_rewrite_recipe`, `_provider_tree` | `tests/legacy_runtime_support.py` |
| `tests/test_runtime_packaging.py` | `_run`, `_venv` | `tests/runtime_installation_support.py` |
| `tests/test_runtime_pyz.py` | `inputs`, `prepared` | `tests/runtime_pyz_support.py` |
| `tests/test_test_evidence.py` | `example`, `invoke`, `make_suite` | `tests/runner_support.py` |
| `tests/test_watcher_events.py` | `inotify_record` | `tests/watcher_support.py` |
| `tests/test_watcher_scheduling.py` | `completion`, `target` | `tests/watcher_support.py` |

`UUID` und `prepare_result_bundle_publication` werden von ihren eigentlichen
Bibliotheksmodulen importiert. Supportmodule exportieren diese Namen nicht
als Ersatz für eine direkte Bibliotheksabhängigkeit.

## Vollständige Zuordnung der ursprünglichen Importstellen

Zeilennummern beziehen sich auf die unveränderte Basis von Bundle 058.

| Verbraucher und Zeile | Bisheriger Lieferant | Neue Lieferanten |
| --- | --- | --- |
| `tests/pyz_variant_support.py:9` | `tests.test_reference_validation` | `tests.reference_support` |
| `tests/pyz_variant_support.py:10` | `tests.test_runtime_pyz` | `tests.runtime_pyz_support` |
| `tests/result_pyz_support.py:8` | `tests.test_reference_validation` | `tests.reference_support` |
| `tests/result_runtime_support.py:11` | `tests.test_reference_validation` | `tests.reference_support` |
| `tests/test_archive_maintenance.py:25` | `tests.test_exchange_archive_e2e` | `tests.archive_support` |
| `tests/test_archive_maintenance.py:26` | `tests.test_exchange_e2e` | `tests.exchange_support` |
| `tests/test_bootstrap_python_compat.py:15` | `tests.test_python_compat` | `tests.windows_creation_support` |
| `tests/test_bootstrap_python_compat.py:17` | `tests.test_python_variants` | `tests.pyz_variant_support` |
| `tests/test_bundle_handoff_e2e.py:17` | `tests.test_exchange_e2e` | `tests.exchange_support` |
| `tests/test_bundle_suffix_e2e.py:20` | `tests.test_exchange_e2e` | `tests.exchange_support` |
| `tests/test_captured_reference.py:23` | `tests.test_reference_validation` | `tests.reference_support` |
| `tests/test_captured_reference.py:223` | `tests.test_patch_inspection` | `tests.patch_inspection_support` |
| `tests/test_exchange_archive_e2e.py:11` | `tests.test_exchange_e2e` | `tests.exchange_support` |
| `tests/test_exchange_recovery.py:19` | `tests.test_archive_maintenance` | `tests.archive_support` |
| `tests/test_exchange_recovery.py:20` | `tests.test_exchange_recovery_e2e` | `tests.recovery_support` |
| `tests/test_exchange_recovery.py:21` | `tests.test_exchange_e2e` | `tests.exchange_support` |
| `tests/test_exchange_recovery.py:22` | `tests.test_exchange_state` | `tests.exchange_support` |
| `tests/test_exchange_recovery_e2e.py:18` | `tests.test_exchange_archive_e2e` | `tests.archive_support` |
| `tests/test_exchange_recovery_e2e.py:21` | `tests.test_exchange_e2e` | `tests.exchange_support` |
| `tests/test_pack_api.py:20` | `tests.test_captured_reference` | `tests.pack_support` |
| `tests/test_pack_api.py:21` | `tests.test_pack_sources` | `tests.pack_support` |
| `tests/test_pack_candidate.py:20` | `tests.test_captured_reference` | `tests.pack_support` |
| `tests/test_pack_candidate.py:21` | `tests.test_reference_validation` | `tests.reference_support` |
| `tests/test_pack_cli.py:14` | `tests.test_pack_api` | `tests.pack_support` |
| `tests/test_pack_examples.py:15` | `tests.test_pyz_result_e2e` | `tests.runtime_installation_support` |
| `tests/test_pack_examples.py:16` | `tests.test_runtime_packaging` | `tests.runtime_installation_support` |
| `tests/test_patch_inspection_errors.py:24` | `tests.test_patch_inspection` | `tests.patch_inspection_support` |
| `tests/test_python_compat.py:21` | `tests.test_pack_api` | `tests.pack_support` |
| `tests/test_python_variants.py:23` | `tests.test_reference_validation` | `tests.reference_support` |
| `tests/test_pyz_bootstrap.py:21` | `tests.test_pack_api` | `tests.pack_support` |
| `tests/test_pyz_bootstrap.py:22` | `tests.test_runtime_pyz` | `tests.runtime_pyz_support` |
| `tests/test_pyz_bootstrap.py:23` | `tests.test_reference_validation` | `tests.reference_support` |
| `tests/test_pyz_measurements.py:14` | `tests.test_pack_api` | `tests.pack_support` |
| `tests/test_pyz_resources.py:20` | `tests.test_pack_api` | `tests.pack_support` |
| `tests/test_pyz_resources.py:21` | `tests.test_runtime_pyz` | `tests.runtime_pyz_support` |
| `tests/test_pyz_result_e2e.py:21` | `tests.test_runtime_packaging` | `tests.runtime_installation_support` |
| `tests/test_pyz_result_resources.py:14` | `tests.test_pyz_resources` | `tests.runtime_pyz_support` |
| `tests/test_pyz_result_resources.py:15` | `tests.test_reference_validation` | `tests.reference_support` |
| `tests/test_pyz_result_resources.py:16` | `tests.test_result_runtime_writer` | `tests.apply_support` |
| `tests/test_reference_validation.py:20` | `tests.test_patch_inspection` | `tests.patch_inspection_support` |
| `tests/test_reference_validation_errors.py:17` | `tests.test_reference_validation` | `tests.reference_support` |
| `tests/test_repository_configuration_acceptance.py:16` | `tests.test_api_e2e` | `tests.apply_support` |
| `tests/test_repository_configuration_e2e.py:15` | `tests.test_api_e2e` | `tests.apply_support` |
| `tests/test_repository_validation.py:16` | `tests.test_reference_validation` | `tests.reference_support` |
| `tests/test_repository_validation.py:154` | `tests.test_reference_validation` | `tests.reference_support` |
| `tests/test_result3_embedded_bootstrap.py:13` | `tests.test_pack_api` | `tests.pack_support` |
| `tests/test_result3_embedded_bootstrap.py:14` | `tests.test_reference_validation` | `tests.reference_support` |
| `tests/test_result3_publication_policy.py:10` | `tests.test_result_bundle_publication` | `patchharbor.result_bundle_publication`, `tests.result_publication_support`, `uuid` |
| `tests/test_result3_publication_policy.py:11` | `tests.test_result_runtime_writer` | `tests.result_pyz_support` |
| `tests/test_result_file_handles.py:10` | `tests.test_result_verification` | `tests.result_publication_support` |
| `tests/test_result_file_handles.py:11` | `tests.test_result_bundle_publication` | `tests.result_publication_support` |
| `tests/test_result_file_limits.py:31` | `tests.test_reference_validation` | `tests.reference_support` |
| `tests/test_result_file_limits.py:32` | `tests.test_result_bundle_publication` | `tests.result_publication_support` |
| `tests/test_result_file_limits.py:33` | `tests.test_runtime_pyz` | `tests.runtime_pyz_support` |
| `tests/test_result_format2.py:32` | `tests.test_reference_validation` | `tests.reference_support` |
| `tests/test_result_format2.py:33` | `tests.test_runtime_artifact` | `tests.legacy_runtime_support` |
| `tests/test_result_format2.py:327` | `tests.test_exchange_recovery_e2e` | `tests.recovery_support` |
| `tests/test_result_format2.py:328` | `tests.test_exchange_archive_e2e` | `tests.archive_support` |
| `tests/test_result_format2.py:329` | `tests.test_exchange_e2e` | `tests.exchange_support` |
| `tests/test_result_format3.py:20` | `tests.test_reference_validation` | `tests.reference_support` |
| `tests/test_result_format3.py:21` | `tests.test_runtime_pyz` | `tests.runtime_pyz_support` |
| `tests/test_result_format3_consumers.py:19` | `tests.test_reference_validation` | `tests.reference_support` |
| `tests/test_result_format3_consumers.py:20` | `tests.test_result_format3` | `tests.result_pyz_support` |
| `tests/test_result_format3_consumers.py:21` | `tests.test_result_robustness` | `tests.legacy_runtime_support` |
| `tests/test_result_format3_consumers.py:53` | `tests.test_exchange_archive_e2e` | `tests.archive_support` |
| `tests/test_result_format3_consumers.py:106` | `tests.test_exchange_recovery_e2e` | `tests.recovery_support` |
| `tests/test_result_format3_consumers.py:107` | `tests.test_exchange_archive_e2e` | `tests.archive_support` |
| `tests/test_result_format3_consumers.py:108` | `tests.test_exchange_e2e` | `tests.exchange_support` |
| `tests/test_result_robustness.py:23` | `tests.test_reference_validation` | `tests.reference_support` |
| `tests/test_result_robustness.py:24` | `tests.test_result_format2` | `tests.legacy_runtime_support` |
| `tests/test_result_robustness.py:25` | `tests.test_runtime_artifact` | `tests.legacy_runtime_support` |
| `tests/test_result_robustness.py:91` | `tests.test_patch_inspection` | `tests.patch_inspection_support` |
| `tests/test_result_robustness.py:135` | `tests.test_exchange_archive_e2e` | `tests.archive_support` |
| `tests/test_result_robustness.py:186` | `tests.test_exchange_archive_e2e` | `tests.archive_support` |
| `tests/test_result_robustness.py:187` | `tests.test_exchange_e2e` | `tests.exchange_support` |
| `tests/test_result_runtime_publication.py:19` | `tests.test_result_runtime_writer` | `tests.apply_support`, `tests.result_pyz_support` |
| `tests/test_result_runtime_roundtrip.py:17` | `tests.test_runtime_packaging` | `tests.runtime_installation_support` |
| `tests/test_result_runtime_writer.py:19` | `tests.test_runtime_pyz` | `tests.runtime_pyz_support` |
| `tests/test_result_verification.py:19` | `tests.test_result_bundle_publication` | `patchharbor.result_bundle_publication`, `tests.result_publication_support`, `uuid` |
| `tests/test_result_verification.py:20` | `tests.test_result_runtime_writer` | `tests.apply_support` |
| `tests/test_runtime_bootstrap.py:22` | `tests.test_result_runtime_writer` | `tests.apply_support` |
| `tests/test_runtime_packaging.py:19` | `tests.test_patch_inspection` | `tests.patch_inspection_support` |
| `tests/test_runtime_robustness.py:17` | `tests.test_runtime_artifact` | `tests.legacy_runtime_support` |
| `tests/test_test_isolation.py:96` | `tests.test_docker_integration_runner` | `tests.runner_support` |
| `tests/test_test_mode_verification.py:13` | `tests.test_test_evidence` | `tests.runner_support` |
| `tests/test_watch_targets_e2e.py:23` | `tests.test_api_e2e` | `tests.apply_support` |
| `tests/test_watcher_event_loop_e2e.py:26` | `tests.test_api_e2e` | `tests.apply_support` |
| `tests/test_watcher_event_loop_e2e.py:27` | `tests.test_watcher_scheduling` | `tests.watcher_support` |
| `tests/test_watcher_events_native.py:218` | `tests.test_watcher_events` | `tests.watcher_support` |

RF-04 behandelt anschließend eigenständig überholte Architektur-/Prosatests.
Diese Migration entfernt keine Altformat- oder sonstigen Verhaltenstests.
